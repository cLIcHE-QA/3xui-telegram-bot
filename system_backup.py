from __future__ import annotations

import asyncio
from dataclasses import dataclass
import hashlib
import io
import json
import re
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from version import APP_VERSION
from backup_manager import BackupManager, BackupResult
from config import HostControlTarget, NodeBackupTarget
from host_control import HostControlClient, HostControlError
from xui import XUIClient


NODE_SNAPSHOT_SCHEMA = 1
MAX_NGINX_EXTRACT_BYTES = 8 * 1024 * 1024
MAX_NGINX_EXTRACT_FILES = 512


def _safe_segment(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-._")
    return cleaned or "node"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class NodeSnapshotResult:
    path: Path
    included: tuple[str, ...]
    missing: tuple[str, ...]
    complete: bool


class SystemBackupService:
    """Build master backups and direct-node recovery snapshots.

    x-ui.db is downloaded through the existing dedicated direct-admin API token.
    nginx configuration is read only through the restricted Host Control Agent
    snapshot endpoint. The endpoint accepts no filesystem path; its source is
    configured locally on the target host.
    """

    def __init__(
        self,
        manager: BackupManager,
        targets: tuple[NodeBackupTarget, ...],
        host_targets: tuple[HostControlTarget, ...] = (),
    ):
        self.manager = manager
        self.targets = targets
        self.host_targets = host_targets

    def configured_node_names(self) -> tuple[str, ...]:
        return tuple(t.node_name for t in self.targets)

    def target_for(self, node_name: str, node_id: int | None = None) -> NodeBackupTarget | None:
        if node_id is not None:
            for target in self.targets:
                if target.node_id == node_id:
                    return target
        needle = node_name.strip().casefold()
        for target in self.targets:
            if node_id is not None and target.node_id is not None:
                continue
            if target.node_name.strip().casefold() == needle:
                return target
        return None

    def host_target_for(self, node_name: str, node_id: int | None = None) -> HostControlTarget | None:
        if node_id is not None:
            for target in self.host_targets:
                if target.node_id == node_id:
                    return target
        needle = node_name.strip().casefold()
        for target in self.host_targets:
            if node_id is not None and target.node_id is not None:
                continue
            if target.name.strip().casefold() == needle:
                return target
        return None

    def has_target_for(self, node_name: str, node_id: int | None = None) -> bool:
        return self.target_for(node_name, node_id) is not None

    @staticmethod
    def _extract_nginx_bundle(
        bundle: bytes,
        destination: Path,
        *,
        expected_host_id: str,
    ) -> dict[str, object]:
        destination.mkdir(parents=True, exist_ok=True)
        try:
            archive = tarfile.open(fileobj=io.BytesIO(bundle), mode="r:gz")
        except tarfile.TarError as exc:
            raise ValueError("invalid nginx snapshot archive") from exc

        with archive:
            members = archive.getmembers()
            meta_members = [member for member in members if member.name == "_snapshot.json"]
            if len(meta_members) != 1 or not meta_members[0].isfile():
                raise ValueError("nginx snapshot metadata is missing")
            if meta_members[0].size > 1024 * 1024:
                raise ValueError("nginx snapshot metadata is too large")
            meta_file = archive.extractfile(meta_members[0])
            if meta_file is None:
                raise ValueError("nginx snapshot metadata cannot be read")
            try:
                metadata = json.loads(meta_file.read().decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError("invalid nginx snapshot metadata") from exc
            if not isinstance(metadata, dict):
                raise ValueError("invalid nginx snapshot metadata shape")
            if metadata.get("schema") != 1:
                raise ValueError("nginx snapshot schema mismatch")
            if metadata.get("host_id") != expected_host_id:
                raise ValueError("nginx snapshot host identity mismatch")
            if metadata.get("component") != "nginx":
                raise ValueError("nginx snapshot component mismatch")

            raw_files = metadata.get("files")
            if not isinstance(raw_files, list):
                raise ValueError("nginx snapshot file manifest is invalid")
            expected: dict[str, tuple[int, str]] = {}
            for item in raw_files:
                if not isinstance(item, dict):
                    raise ValueError("nginx snapshot file manifest is invalid")
                name = str(item.get("path") or "")
                rel = Path(name)
                digest = str(item.get("sha256") or "").lower()
                try:
                    size = int(item.get("bytes"))
                except (TypeError, ValueError) as exc:
                    raise ValueError("nginx snapshot file size is invalid") from exc
                if (
                    not name
                    or rel.is_absolute()
                    or ".." in rel.parts
                    or name == "_snapshot.json"
                    or not re.fullmatch(r"[0-9a-f]{64}", digest)
                    or size < 0
                ):
                    raise ValueError("nginx snapshot file manifest is unsafe")
                if name in expected:
                    raise ValueError("nginx snapshot contains duplicate file metadata")
                expected[name] = (size, digest)

            if len(expected) > MAX_NGINX_EXTRACT_FILES:
                raise ValueError("nginx snapshot contains too many files")

            extracted: set[str] = set()
            total = 0
            for member in members:
                if member.name == "_snapshot.json":
                    continue
                rel = Path(member.name)
                if rel.is_absolute() or ".." in rel.parts:
                    raise ValueError("unsafe nginx snapshot path")
                if member.isdir():
                    continue
                if not member.isfile():
                    raise ValueError("nginx snapshot contains non-regular entry")
                name = rel.as_posix()
                if name not in expected:
                    raise ValueError("nginx snapshot file is absent from metadata")
                if name in extracted:
                    raise ValueError("nginx snapshot contains duplicate file")
                expected_size, expected_digest = expected[name]
                if member.size != expected_size:
                    raise ValueError("nginx snapshot file size mismatch")
                total += member.size
                if total > MAX_NGINX_EXTRACT_BYTES:
                    raise ValueError("nginx snapshot expanded size is too large")
                source = archive.extractfile(member)
                if source is None:
                    raise ValueError("nginx snapshot file cannot be read")
                data = source.read()
                if len(data) != expected_size or _sha256_bytes(data) != expected_digest:
                    raise ValueError("nginx snapshot file checksum mismatch")
                target = destination / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                extracted.add(name)

            if extracted != set(expected):
                raise ValueError("nginx snapshot is missing declared files")
            return metadata

    async def _version_metadata(self, client: XUIClient) -> dict[str, str]:
        versions: dict[str, str] = {}
        try:
            panel = await client.get_panel_update_info()
            current = str(panel.get("currentVersion") or "").strip()
            if current:
                versions["panel"] = current
        except Exception:
            pass
        try:
            status = await client.server_status()
            xray = status.get("xray") if isinstance(status, dict) else None
            if isinstance(xray, dict):
                current = str(xray.get("version") or "").strip()
                if current:
                    versions["xray"] = current
        except Exception:
            pass
        return versions

    async def _collect_target(self, target: NodeBackupTarget, root: Path) -> dict[str, object]:
        client = XUIClient(target.panel_url, target.api_token, target.verify_tls)
        body, remote_filename = await client.download_database()

        node_dir_name = _safe_segment(target.node_name)
        node_dir = root / node_dir_name
        node_dir.mkdir(parents=True, exist_ok=True)

        db_path = node_dir / "x-ui.db"
        await asyncio.to_thread(db_path.write_bytes, body)

        created_at = datetime.now(timezone.utc).isoformat()
        host_target = self.host_target_for(target.node_name, target.node_id)
        versions = await self._version_metadata(client)
        node_meta = {
            "node_name": target.node_name,
            "node_id": target.node_id,
            "backup_key": target.key,
            "host_id": host_target.host_id if host_target else None,
            "source_panel_url": target.panel_url,
            "created_at_utc": created_at,
            "database_file": "x-ui.db",
            "source_database_filename": remote_filename,
            "versions": versions,
            "note": "API and Host Control tokens are intentionally not stored in this metadata.",
        }
        meta_path = node_dir / "node.json"
        await asyncio.to_thread(
            meta_path.write_text,
            json.dumps(node_meta, ensure_ascii=False, indent=2, sort_keys=True),
            "utf-8",
        )

        missing: list[str] = []
        nginx_component: dict[str, object]
        if host_target is None:
            nginx_component = {
                "status": "missing",
                "reason": "host_control_target_not_configured",
            }
            missing.append("nginx/ (Host Control target not configured)")
        else:
            host_client = HostControlClient(
                host_target.url,
                host_target.token,
                host_target.host_id,
                verify_tls=host_target.verify_tls,
            )
            try:
                bundle = await host_client.download_nginx_snapshot()
                nginx_dir = node_dir / "nginx"
                metadata = await asyncio.to_thread(
                    self._extract_nginx_bundle,
                    bundle,
                    nginx_dir,
                    expected_host_id=host_target.host_id,
                )
                skipped = metadata.get("skipped")
                skipped_count = len(skipped) if isinstance(skipped, list) else 0
                complete = bool(metadata.get("complete"))
                nginx_component = {
                    "status": "ok" if complete else "degraded",
                    "host_id": host_target.host_id,
                    "files": len(metadata.get("files") or []),
                    "skipped": skipped_count,
                }
                if not complete:
                    reason = (
                        f"nginx/ (degraded snapshot; skipped={skipped_count})"
                        if skipped_count
                        else "nginx/ (degraded or empty snapshot)"
                    )
                    missing.append(reason)
            except (HostControlError, ValueError, tarfile.TarError, OSError) as exc:
                code = exc.code if isinstance(exc, HostControlError) and exc.code else type(exc).__name__
                nginx_component = {
                    "status": "missing",
                    "host_id": host_target.host_id,
                    "reason": code,
                }
                missing.append(f"nginx/ ({code})")

        file_entries: list[dict[str, object]] = []
        for path in sorted(node_dir.rglob("*"), key=lambda item: item.as_posix()):
            if not path.is_file() or path.name == "manifest.json":
                continue
            rel = path.relative_to(node_dir).as_posix()
            file_entries.append(
                {
                    "path": rel,
                    "bytes": path.stat().st_size,
                    "sha256": await asyncio.to_thread(_sha256_path, path),
                }
            )

        manifest = {
            "schema": NODE_SNAPSHOT_SCHEMA,
            "created_at_utc": created_at,
            "node": {
                "name": target.node_name,
                "node_id": target.node_id,
                "backup_key": target.key,
                "host_id": host_target.host_id if host_target else None,
            },
            "versions": versions,
            "components": {
                "database": {
                    "status": "ok",
                    "file": "x-ui.db",
                    "source": "3x-ui direct admin backup API",
                },
                "nginx": nginx_component,
            },
            "files": file_entries,
            "missing": missing,
            "complete": not missing,
        }
        manifest_path = node_dir / "manifest.json"
        await asyncio.to_thread(
            manifest_path.write_text,
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
            "utf-8",
        )

        included = [
            path.relative_to(node_dir).as_posix()
            for path in sorted(node_dir.rglob("*"), key=lambda item: item.as_posix())
            if path.is_file()
        ]
        return {
            "target": target,
            "node_dir_name": node_dir_name,
            "node_dir": node_dir,
            "included": included,
            "missing": missing,
            "manifest": manifest,
        }

    async def create_node_snapshot(
        self,
        node_name: str,
        node_id: int | None = None,
    ) -> NodeSnapshotResult:
        target = self.target_for(node_name, node_id)
        if target is None:
            raise ValueError(f"Backup target is not configured for node: {node_name}")

        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        safe_node = _safe_segment(target.node_name)
        out_dir = self.manager.backup_dir / "nodes" / safe_node
        await asyncio.to_thread(out_dir.mkdir, parents=True, exist_ok=True)
        path = out_dir / f"node-snapshot-{stamp}.tar.gz"

        with tempfile.TemporaryDirectory(prefix="node-snapshot-stage-") as tmp:
            collected = await self._collect_target(target, Path(tmp))
            node_dir = Path(collected["node_dir"])
            await asyncio.to_thread(
                self._write_node_archive,
                path,
                node_dir,
                safe_node,
            )

        def _prune() -> None:
            items = sorted(
                [*out_dir.glob("node-snapshot-*.tar.gz"), *out_dir.glob("node-backup-*")],
                key=lambda item: item.stat().st_mtime if item.exists() else 0,
                reverse=True,
            )
            for old in items[5:]:
                try:
                    old.unlink()
                except OSError:
                    pass

        await asyncio.to_thread(_prune)
        included = tuple(f"nodes/{safe_node}/{name}" for name in collected["included"])
        missing = tuple(f"nodes/{safe_node}/{name}" for name in collected["missing"])
        return NodeSnapshotResult(path, included, missing, not missing)

    @staticmethod
    def _write_node_archive(path: Path, node_dir: Path, safe_node: str) -> None:
        with tarfile.open(path, "w:gz") as archive:
            archive.add(node_dir, arcname=f"nodes/{safe_node}", recursive=True)

    def direct_client_for(self, node_name: str, node_id: int | None = None) -> XUIClient | None:
        target = self.target_for(node_name, node_id)
        if target is None:
            return None
        return XUIClient(target.panel_url, target.api_token, target.verify_tls)

    async def create_full_backup(self) -> BackupResult:
        extra_files: dict[str, Path] = {}
        extra_missing: list[str] = []
        node_results: list[dict[str, object]] = []

        with tempfile.TemporaryDirectory(prefix="node-backup-stage-") as tmp:
            root = Path(tmp)

            if self.targets:
                results = await asyncio.gather(
                    *(self._collect_target(target, root) for target in self.targets),
                    return_exceptions=True,
                )
                for target, result in zip(self.targets, results):
                    safe_node = _safe_segment(target.node_name)
                    if isinstance(result, Exception):
                        error = f"{type(result).__name__}: {result}"
                        extra_missing.append(f"nodes/{safe_node}/ ({error})")
                        node_results.append(
                            {
                                "name": target.node_name,
                                "node_id": target.node_id,
                                "ok": False,
                                "complete": False,
                                "error": error,
                            }
                        )
                        continue

                    node_dir = Path(result["node_dir"])
                    extra_files[f"nodes/{safe_node}"] = node_dir
                    for item in result["missing"]:
                        extra_missing.append(f"nodes/{safe_node}/{item}")
                    manifest = result["manifest"]
                    node_results.append(
                        {
                            "name": target.node_name,
                            "node_id": target.node_id,
                            "ok": True,
                            "complete": bool(manifest.get("complete")),
                            "database_file": "x-ui.db",
                            "nginx": manifest.get("components", {}).get("nginx"),
                        }
                    )

            return await asyncio.to_thread(
                self.manager.create_full_backup,
                extra_files,
                extra_missing,
                version=APP_VERSION,
                extra_manifest={"nodes": node_results},
            )
