from __future__ import annotations

import base64
import io
import json
import shutil
import sqlite3
import tarfile
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backup_manager import BackupManager
from db import Database
from offsite_backup import (
    OffsiteBackupError,
    OffsiteBackupService,
    replicate_with_job,
)
from restore_manager import RestoreManager


def make_sqlite(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE state(value TEXT NOT NULL)")
        db.execute("INSERT INTO state(value) VALUES (?)", (value,))
        db.commit()


class FakeS3:
    def __init__(self):
        self.objects: dict[str, dict] = {}
        self.counter = 0

    def upload_file(self, filename, bucket, key, ExtraArgs=None):
        self.counter += 1
        self.objects[key] = {
            "Body": Path(filename).read_bytes(),
            "Metadata": dict((ExtraArgs or {}).get("Metadata") or {}),
            "ContentType": (ExtraArgs or {}).get("ContentType"),
            "LastModified": datetime.now(timezone.utc) + timedelta(seconds=self.counter),
        }

    def head_object(self, Bucket, Key):
        item = self.objects[Key]
        return {
            "ContentLength": len(item["Body"]),
            "Metadata": dict(item["Metadata"]),
        }

    def download_file(self, bucket, key, filename):
        Path(filename).write_bytes(self.objects[key]["Body"])

    def list_objects_v2(self, Bucket, Prefix, MaxKeys=1000, ContinuationToken=None):
        contents = [
            {
                "Key": key,
                "Size": len(item["Body"]),
                "LastModified": item["LastModified"],
            }
            for key, item in self.objects.items()
            if key.startswith(Prefix)
        ]
        return {"Contents": contents, "IsTruncated": False}

    def delete_object(self, Bucket, Key):
        self.objects.pop(Key, None)


class FailingService:
    def upload_and_verify(self, path):
        raise OffsiteBackupError("synthetic upload failure")


class OffsiteBackupTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db_path = self.root / "data" / "bot.sqlite3"
        make_sqlite(self.db_path, "bot")

        self.backup_dir = self.root / "backups"
        self.manager = BackupManager(str(self.db_path), str(self.backup_dir), keep=10)
        self.manager.sources_root = self.root / "sources"
        make_sqlite(self.manager.sources_root / "x-ui" / "x-ui.db", "xui")
        (self.manager.sources_root / "bot.env").write_text(
            "BOT_TOKEN=test\nPANEL_API_TOKEN=test-panel\n",
            encoding="utf-8",
        )

        self.restore = RestoreManager(str(self.db_path), str(self.backup_dir))
        self.fake = FakeS3()
        self.key_b64 = base64.b64encode(b"k" * 32).decode("ascii")
        self.service = OffsiteBackupService(
            bucket="backup-bucket",
            prefix="prod/master",
            region="eu-test-1",
            endpoint_url="https://s3.example.test",
            access_key_id="access",
            secret_access_key="secret",
            keep=1,
            encryption_key_b64=self.key_b64,
            restore_manager=self.restore,
            client=self.fake,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def create_backup(self):
        return self.manager.create_full_backup(version="4.18.0-test")

    def test_schema2_manifest_covers_every_regular_file_and_tamper_fails(self):
        result = self.create_backup()
        inspected = self.restore.inspect_backup(result.info.path, deep=True)
        self.assertTrue(inspected.valid, inspected.errors)
        self.assertEqual(inspected.manifest["schema"], 2)

        with tarfile.open(result.info.path, "r:gz") as archive:
            names = {
                member.name
                for member in archive.getmembers()
                if member.isfile() and member.name != "manifest.json"
            }
        declared = {
            item["path"]
            for item in inspected.manifest["integrity"]["files"]
        }
        self.assertEqual(declared, names)

        tampered = self.backup_dir / "3xui-bot-backup-20990101-000000.tar.gz"
        with tarfile.open(result.info.path, "r:gz") as source, tarfile.open(tampered, "w:gz") as target:
            for member in source.getmembers():
                if not member.isfile():
                    target.addfile(member)
                    continue
                data = source.extractfile(member).read()
                if member.name == "README-RESTORE.txt":
                    data += b"tampered"
                    member.size = len(data)
                target.addfile(member, io.BytesIO(data))

        checked = self.restore.inspect_backup(tampered, deep=True)
        self.assertFalse(checked.valid)
        self.assertTrue(
            any("Integrity" in error for error in checked.errors),
            checked.errors,
        )

    def test_upload_is_encrypted_round_trip_verified_and_downloadable(self):
        result = self.create_backup()
        uploaded = self.service.upload_and_verify(result.info.path)

        self.assertEqual(uploaded.key, f"prod/master/{result.info.path.name}.enc")
        remote = self.fake.objects[uploaded.key]["Body"]
        self.assertNotIn(b"SQLite format 3", remote)
        self.assertNotEqual(remote, result.info.path.read_bytes())

        destination = self.root / "recovered.tar.gz"
        self.service.download_and_verify(destination)
        self.assertEqual(destination.read_bytes(), result.info.path.read_bytes())
        inspected = self.restore.inspect_backup(destination, deep=True)
        self.assertTrue(inspected.valid, inspected.errors)

    def test_retention_only_keeps_newest_object_under_fixed_prefix(self):
        first = self.create_backup()
        first_copy = self.backup_dir / "3xui-bot-backup-20990101-000001.tar.gz"
        shutil.copy2(first.info.path, first_copy)
        self.service.upload_and_verify(first_copy)

        second_copy = self.backup_dir / "3xui-bot-backup-20990101-000002.tar.gz"
        shutil.copy2(first.info.path, second_copy)
        self.service.upload_and_verify(second_copy)

        keys = sorted(self.fake.objects)
        self.assertEqual(keys, [f"prod/master/{second_copy.name}.enc"])

    def test_noncanonical_source_is_rejected_before_upload(self):
        result = self.create_backup()
        renamed = self.root / "arbitrary.tar.gz"
        shutil.copy2(result.info.path, renamed)
        with self.assertRaisesRegex(OffsiteBackupError, "canonical Full Backup"):
            self.service.upload_and_verify(renamed)
        self.assertEqual(self.fake.objects, {})

    def test_target_boundary_rejects_unsafe_prefix_and_non_https_endpoint(self):
        common = dict(
            bucket="backup-bucket",
            region="eu-test-1",
            access_key_id="access",
            secret_access_key="secret",
            keep=1,
            encryption_key_b64=self.key_b64,
            restore_manager=self.restore,
            client=self.fake,
        )
        with self.assertRaisesRegex(OffsiteBackupError, "prefix"):
            OffsiteBackupService(
                prefix="../escape",
                endpoint_url="https://s3.example.test",
                **common,
            )
        with self.assertRaisesRegex(OffsiteBackupError, "verified HTTPS"):
            OffsiteBackupService(
                prefix="prod/master",
                endpoint_url="http://s3.example.test",
                **common,
            )
        with self.assertRaisesRegex(OffsiteBackupError, "verified HTTPS"):
            OffsiteBackupService(
                prefix="prod/master",
                endpoint_url="https://user:pass@s3.example.test",
                **common,
            )

    async def test_replication_failure_is_recorded_as_separate_failed_job(self):
        db = Database(str(self.root / "jobs.sqlite3"))
        await db.init()
        status, result, detail = await replicate_with_job(
            db,
            FailingService(),
            self.create_backup().info.path,
            trigger="scheduled",
            actor_id=0,
        )

        self.assertEqual(status, "failed")
        self.assertIsNone(result)
        self.assertIn("synthetic upload failure", detail)
        job = await db.last_job_run("backup.offsite")
        self.assertIsNotNone(job)
        self.assertEqual(job.status, "failed")
        self.assertEqual(job.trigger, "scheduled")


if __name__ == "__main__":
    unittest.main()
