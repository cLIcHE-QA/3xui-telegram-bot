from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import sqlite3
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from backup_manager import BackupManager
from config import HostControlTarget, NodeBackupTarget
from host_control import HostControlError
from system_backup import SystemBackupService


def nginx_bundle(host_id: str = "fi", *, complete: bool = True) -> bytes:
    payloads = {
        "nginx.conf": b"events {}\nhttp {}\n",
        "conf.d/site.conf": b"server { listen 443; }\n",
    }
    files = [
        {
            "path": name,
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
        for name, data in payloads.items()
    ]
    metadata = {
        "schema": 1,
        "host_id": host_id,
        "component": "nginx",
        "created_at_utc": "2026-09-24T11:00:00Z",
        "complete": complete,
        "files": files,
        "skipped": [] if complete else [{"path": "modules/x.so", "reason": "external_symlink"}],
    }
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode="w:gz") as archive:
        for name, data in payloads.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
        raw = json.dumps(metadata).encode("utf-8")
        info = tarfile.TarInfo("_snapshot.json")
        info.size = len(raw)
        archive.addfile(info, io.BytesIO(raw))
    return out.getvalue()


class FakeXUIClient:
    def __init__(self, *args, **kwargs):
        pass

    async def download_database(self):
        return b"node-sqlite-backup", "remote-x-ui.db"

    async def get_panel_update_info(self):
        return {"currentVersion": "3.8.6"}

    async def server_status(self):
        return {"xray": {"version": "25.9.15", "state": "running"}}


class FakeHostControlClient:
    bundle = nginx_bundle()
    error: HostControlError | None = None

    def __init__(self, _url, _token, expected_host_id, **_kwargs):
        self.expected_host_id = expected_host_id

    async def download_nginx_snapshot(self):
        if self.error is not None:
            raise self.error
        return self.bundle


class ExtendedNodeBackupTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.db_path = root / "bot.sqlite3"
        with sqlite3.connect(self.db_path) as connection:
            connection.execute("CREATE TABLE sample(id INTEGER PRIMARY KEY)")
        self.manager = BackupManager(str(self.db_path), str(root / "backups"), keep=3)
        self.node = NodeBackupTarget(
            key="FI",
            node_name="Finland",
            node_id=2,
            panel_url="https://fi-panel.example.invalid",
            api_token="p" * 43,
            verify_tls=True,
        )
        self.host = HostControlTarget(
            key="FI",
            name="Finland",
            node_id=2,
            host_id="fi",
            url="https://fi-host.example.invalid",
            token="h" * 43,
            verify_tls=True,
        )
        FakeHostControlClient.bundle = nginx_bundle()
        FakeHostControlClient.error = None

    def patched(self):
        return (
            patch("system_backup.XUIClient", FakeXUIClient),
            patch("system_backup.HostControlClient", FakeHostControlClient),
        )

    async def test_manual_snapshot_has_required_structure_and_checksums(self):
        service = SystemBackupService(self.manager, (self.node,), (self.host,))
        xui_patch, host_patch = self.patched()
        with xui_patch, host_patch:
            result = await service.create_node_snapshot("Renamed Finland", 2)

        self.assertTrue(result.complete)
        self.assertEqual(result.missing, ())
        self.assertTrue(result.path.name.startswith("node-snapshot-"))

        with tarfile.open(result.path, "r:gz") as archive:
            names = set(archive.getnames())
            prefix = "nodes/Finland/"
            for required in [
                "x-ui.db",
                "node.json",
                "manifest.json",
                "nginx/nginx.conf",
                "nginx/conf.d/site.conf",
            ]:
                self.assertIn(prefix + required, names)

            node_meta = json.load(archive.extractfile(prefix + "node.json"))
            manifest = json.load(archive.extractfile(prefix + "manifest.json"))
            self.assertEqual(node_meta["node_id"], 2)
            self.assertEqual(node_meta["host_id"], "fi")
            self.assertEqual(node_meta["database_file"], "x-ui.db")
            self.assertEqual(node_meta["versions"]["panel"], "3.8.6")
            self.assertEqual(node_meta["versions"]["xray"], "25.9.15")
            self.assertTrue(manifest["complete"])
            self.assertEqual(manifest["components"]["database"]["status"], "ok")
            self.assertEqual(manifest["components"]["nginx"]["status"], "ok")

            for item in manifest["files"]:
                raw = archive.extractfile(prefix + item["path"]).read()
                self.assertEqual(len(raw), item["bytes"])
                self.assertEqual(hashlib.sha256(raw).hexdigest(), item["sha256"])

    async def test_missing_host_control_target_is_explicitly_degraded(self):
        service = SystemBackupService(self.manager, (self.node,), ())
        with patch("system_backup.XUIClient", FakeXUIClient):
            result = await service.create_node_snapshot("Finland", 2)

        self.assertFalse(result.complete)
        self.assertTrue(any("Host Control target not configured" in item for item in result.missing))
        with tarfile.open(result.path, "r:gz") as archive:
            manifest = json.load(archive.extractfile("nodes/Finland/manifest.json"))
            self.assertEqual(manifest["components"]["database"]["status"], "ok")
            self.assertEqual(manifest["components"]["nginx"]["status"], "missing")
            self.assertFalse(manifest["complete"])

    async def test_unconfigured_agent_nginx_source_is_explicitly_degraded(self):
        service = SystemBackupService(self.manager, (self.node,), (self.host,))
        FakeHostControlClient.error = HostControlError(
            "not configured", code="nginx_snapshot_unconfigured"
        )
        xui_patch, host_patch = self.patched()
        with xui_patch, host_patch:
            result = await service.create_node_snapshot("Finland", 2)

        self.assertFalse(result.complete)
        self.assertTrue(any("nginx_snapshot_unconfigured" in item for item in result.missing))
        with tarfile.open(result.path, "r:gz") as archive:
            manifest = json.load(archive.extractfile("nodes/Finland/manifest.json"))
            self.assertEqual(
                manifest["components"]["nginx"]["reason"],
                "nginx_snapshot_unconfigured",
            )

    async def test_agent_reported_partial_nginx_snapshot_is_degraded(self):
        service = SystemBackupService(self.manager, (self.node,), (self.host,))
        FakeHostControlClient.bundle = nginx_bundle(complete=False)
        xui_patch, host_patch = self.patched()
        with xui_patch, host_patch:
            result = await service.create_node_snapshot("Finland", 2)

        self.assertFalse(result.complete)
        self.assertTrue(any("degraded snapshot" in item for item in result.missing))
        with tarfile.open(result.path, "r:gz") as archive:
            manifest = json.load(archive.extractfile("nodes/Finland/manifest.json"))
            self.assertEqual(manifest["components"]["nginx"]["status"], "degraded")
            self.assertEqual(manifest["components"]["nginx"]["skipped"], 1)

    def test_nginx_bundle_path_traversal_is_rejected(self):
        metadata = {
            "schema": 1,
            "host_id": "fi",
            "component": "nginx",
            "complete": True,
            "files": [
                {
                    "path": "../secret",
                    "bytes": 1,
                    "sha256": hashlib.sha256(b"x").hexdigest(),
                }
            ],
            "skipped": [],
        }
        out = io.BytesIO()
        with tarfile.open(fileobj=out, mode="w:gz") as archive:
            data = b"x"
            info = tarfile.TarInfo("../secret")
            info.size = 1
            archive.addfile(info, io.BytesIO(data))
            raw = json.dumps(metadata).encode()
            info = tarfile.TarInfo("_snapshot.json")
            info.size = len(raw)
            archive.addfile(info, io.BytesIO(raw))

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                SystemBackupService._extract_nginx_bundle(
                    out.getvalue(),
                    Path(tmp),
                    expected_host_id="fi",
                )

    async def test_full_backup_embeds_node_snapshot_contract(self):
        service = SystemBackupService(self.manager, (self.node,), (self.host,))
        xui_patch, host_patch = self.patched()
        with xui_patch, host_patch:
            result = await service.create_full_backup()

        with tarfile.open(result.info.path, "r:gz") as archive:
            names = set(archive.getnames())
            self.assertIn("nodes/Finland/x-ui.db", names)
            self.assertIn("nodes/Finland/nginx/nginx.conf", names)
            self.assertIn("nodes/Finland/node.json", names)
            self.assertIn("nodes/Finland/manifest.json", names)
            global_manifest = json.load(archive.extractfile("manifest.json"))
            integrity_paths = {
                item["path"] for item in global_manifest["integrity"]["files"]
            }
            self.assertIn("nodes/Finland/manifest.json", integrity_paths)
            node = global_manifest["nodes"][0]
            self.assertEqual(node["node_id"], 2)
            self.assertTrue(node["ok"])
            self.assertTrue(node["complete"])


if __name__ == "__main__":
    unittest.main()
