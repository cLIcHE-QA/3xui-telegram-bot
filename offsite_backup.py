from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import boto3
from botocore.config import Config
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from db import Database
from restore_manager import RestoreManager


MAGIC = b"3XUI-OFFSITE-1\n"
NONCE_BYTES = 12
TAG_BYTES = 16
CHUNK_BYTES = 1024 * 1024
AAD = b"3xui-telegram-bot/offsite-backup/v1"


class OffsiteBackupError(RuntimeError):
    pass


@dataclass(frozen=True)
class OffsiteBackupResult:
    key: str
    source_sha256: str
    plaintext_bytes: int
    encrypted_bytes: int
    uploaded_at: datetime
    retained: int
    missing: tuple[str, ...]


class OffsiteBackupService:
    """Encrypted, fixed-target off-site replication for verified Full Backups.

    The service does not accept bucket, prefix, credentials or arbitrary object
    keys from Telegram/UI input. Those values come from local environment
    configuration only.
    """

    def __init__(
        self,
        *,
        bucket: str,
        prefix: str,
        region: str,
        endpoint_url: str,
        access_key_id: str,
        secret_access_key: str,
        keep: int,
        encryption_key_b64: str,
        restore_manager: RestoreManager,
        client: Any | None = None,
    ):
        self.bucket = bucket.strip()
        self.prefix = prefix.strip().strip("/")
        self.region = region.strip() or "us-east-1"
        self.endpoint_url = endpoint_url.strip().rstrip("/")
        self.keep = max(1, int(keep))
        if not self.bucket:
            raise OffsiteBackupError("Off-site bucket must not be empty.")
        if not self.prefix or any(part in {"", ".", ".."} for part in self.prefix.split("/")):
            raise OffsiteBackupError("Off-site prefix must contain safe non-empty path segments.")
        if self.endpoint_url:
            parsed = urlsplit(self.endpoint_url)
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
            ):
                raise OffsiteBackupError(
                    "Custom S3 endpoint must be absolute verified HTTPS without credentials/query/fragment."
                )
        self.restore_manager = restore_manager
        self._key = self._decode_key(encryption_key_b64)
        if client is not None:
            self.client = client
        else:
            config = Config(
                signature_version="s3v4",
                retries={"max_attempts": 3, "mode": "standard"},
                connect_timeout=10,
                read_timeout=120,
                s3={"addressing_style": "path"} if self.endpoint_url else {},
            )
            self.client = boto3.client(
                "s3",
                region_name=self.region,
                endpoint_url=self.endpoint_url or None,
                aws_access_key_id=access_key_id,
                aws_secret_access_key=secret_access_key,
                config=config,
            )

    @staticmethod
    def _decode_key(value: str) -> bytes:
        try:
            key = base64.b64decode(value.strip(), validate=True)
        except Exception as exc:
            raise OffsiteBackupError(
                "OFFSITE_BACKUP_ENCRYPTION_KEY_B64 must be valid base64."
            ) from exc
        if len(key) != 32:
            raise OffsiteBackupError(
                "OFFSITE_BACKUP_ENCRYPTION_KEY_B64 must decode to exactly 32 bytes."
            )
        return key

    def _object_key(self, path: Path) -> str:
        name = Path(path).name
        if not name.startswith("3xui-bot-backup-") or not name.endswith(".tar.gz"):
            raise OffsiteBackupError("Only canonical Full Backup archives can be uploaded.")
        return f"{self.prefix}/{name}.enc"

    @staticmethod
    def _sha256_path(path: Path) -> str:
        digest = hashlib.sha256()
        with Path(path).open("rb") as handle:
            for chunk in iter(lambda: handle.read(CHUNK_BYTES), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _validate_source(self, path: Path):
        inspection = self.restore_manager.inspect_backup(path, deep=True)
        if not inspection.valid:
            raise OffsiteBackupError(
                "Full Backup failed deep validation: "
                + "; ".join(inspection.errors[:5])
            )
        if inspection.manifest.get("schema") != 2:
            raise OffsiteBackupError(
                "Off-site replication requires checksummed Full Backup manifest schema 2."
            )
        if not inspection.has_bot_db or inspection.bot_db_ok is not True:
            raise OffsiteBackupError("Full Backup does not contain a valid bot.sqlite3.")
        if not inspection.has_xui_db or inspection.xui_db_ok is not True:
            raise OffsiteBackupError("Full Backup does not contain a valid x-ui.db.")
        if not inspection.has_bot_env:
            raise OffsiteBackupError("Full Backup does not contain bot.env.")
        missing = inspection.manifest.get("missing")
        return inspection, tuple(str(x) for x in missing) if isinstance(missing, list) else ()

    def _encrypt(self, source: Path, destination: Path) -> tuple[str, int]:
        nonce = os.urandom(NONCE_BYTES)
        encryptor = Cipher(algorithms.AES(self._key), modes.GCM(nonce)).encryptor()
        encryptor.authenticate_additional_data(AAD)
        digest = hashlib.sha256()
        plaintext_bytes = 0

        with Path(source).open("rb") as src, Path(destination).open("wb") as dst:
            dst.write(MAGIC)
            dst.write(nonce)
            while True:
                chunk = src.read(CHUNK_BYTES)
                if not chunk:
                    break
                digest.update(chunk)
                plaintext_bytes += len(chunk)
                dst.write(encryptor.update(chunk))
            dst.write(encryptor.finalize())
            dst.write(encryptor.tag)

        return digest.hexdigest(), plaintext_bytes

    def _decrypt(
        self,
        source: Path,
        destination: Path,
        *,
        expected_sha256: str = "",
        expected_bytes: int | None = None,
    ) -> tuple[str, int]:
        source = Path(source)
        size = source.stat().st_size
        minimum = len(MAGIC) + NONCE_BYTES + TAG_BYTES
        if size < minimum:
            raise OffsiteBackupError("Encrypted off-site object is truncated.")

        with source.open("rb") as src:
            if src.read(len(MAGIC)) != MAGIC:
                raise OffsiteBackupError("Unknown off-site encryption format.")
            nonce = src.read(NONCE_BYTES)
            src.seek(-TAG_BYTES, os.SEEK_END)
            tag = src.read(TAG_BYTES)
            ciphertext_bytes = size - len(MAGIC) - NONCE_BYTES - TAG_BYTES
            src.seek(len(MAGIC) + NONCE_BYTES)

            decryptor = Cipher(
                algorithms.AES(self._key),
                modes.GCM(nonce, tag),
            ).decryptor()
            decryptor.authenticate_additional_data(AAD)
            digest = hashlib.sha256()
            plaintext_bytes = 0
            remaining = ciphertext_bytes

            with Path(destination).open("wb") as dst:
                while remaining:
                    chunk = src.read(min(CHUNK_BYTES, remaining))
                    if not chunk:
                        raise OffsiteBackupError("Encrypted off-site object ended early.")
                    remaining -= len(chunk)
                    plain = decryptor.update(chunk)
                    if plain:
                        digest.update(plain)
                        plaintext_bytes += len(plain)
                        dst.write(plain)
                final = decryptor.finalize()
                if final:
                    digest.update(final)
                    plaintext_bytes += len(final)
                    dst.write(final)

        actual_sha = digest.hexdigest()
        if expected_sha256 and actual_sha != expected_sha256.lower():
            raise OffsiteBackupError("Remote round-trip plaintext SHA-256 mismatch.")
        if expected_bytes is not None and plaintext_bytes != int(expected_bytes):
            raise OffsiteBackupError("Remote round-trip plaintext size mismatch.")
        return actual_sha, plaintext_bytes

    @staticmethod
    def _metadata(
        *,
        source_sha256: str,
        plaintext_bytes: int,
        version: str,
        source_name: str,
    ) -> dict[str, str]:
        return {
            "format": "3xui-offsite-v1",
            "source-sha256": source_sha256,
            "source-bytes": str(int(plaintext_bytes)),
            "backup-version": version[:64],
            "source-name": source_name[:200],
        }

    def _list_objects(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        token: str | None = None
        while True:
            kwargs: dict[str, Any] = {
                "Bucket": self.bucket,
                "Prefix": self.prefix + "/",
                "MaxKeys": 1000,
            }
            if token:
                kwargs["ContinuationToken"] = token
            response = self.client.list_objects_v2(**kwargs)
            for item in response.get("Contents") or []:
                key = str(item.get("Key") or "")
                if key.startswith(self.prefix + "/") and key.endswith(".tar.gz.enc"):
                    items.append(item)
            if not response.get("IsTruncated"):
                break
            token = str(response.get("NextContinuationToken") or "")
            if not token:
                raise OffsiteBackupError("S3 listing is truncated without continuation token.")
        return items

    def _prune(self) -> int:
        items = sorted(
            self._list_objects(),
            key=lambda item: item.get("LastModified") or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        for item in items[self.keep :]:
            self.client.delete_object(Bucket=self.bucket, Key=str(item["Key"]))
        return min(len(items), self.keep)

    def _round_trip_verify(
        self,
        key: str,
        *,
        expected_sha256: str,
        expected_bytes: int,
    ) -> None:
        with tempfile.TemporaryDirectory(prefix="offsite-verify-") as tmp:
            root = Path(tmp)
            encrypted = root / "backup.enc"
            plain = root / "backup.tar.gz"
            self.client.download_file(self.bucket, key, str(encrypted))
            self._decrypt(
                encrypted,
                plain,
                expected_sha256=expected_sha256,
                expected_bytes=expected_bytes,
            )
            inspection = self.restore_manager.inspect_backup(plain, deep=True)
            if not inspection.valid:
                raise OffsiteBackupError(
                    "Downloaded off-site backup failed deep validation: "
                    + "; ".join(inspection.errors[:5])
                )
            if inspection.manifest.get("schema") != 2:
                raise OffsiteBackupError(
                    "Downloaded off-site backup does not have manifest schema 2."
                )

    def upload_and_verify(self, path: Path) -> OffsiteBackupResult:
        path = Path(path)
        inspection, missing = self._validate_source(path)
        key = self._object_key(path)

        with tempfile.TemporaryDirectory(prefix="offsite-upload-") as tmp:
            encrypted = Path(tmp) / "backup.enc"
            source_sha256, plaintext_bytes = self._encrypt(path, encrypted)
            encrypted_bytes = encrypted.stat().st_size
            metadata = self._metadata(
                source_sha256=source_sha256,
                plaintext_bytes=plaintext_bytes,
                version=str(inspection.manifest.get("version") or ""),
                source_name=path.name,
            )
            self.client.upload_file(
                str(encrypted),
                self.bucket,
                key,
                ExtraArgs={
                    "ContentType": "application/octet-stream",
                    "Metadata": metadata,
                },
            )

        head = self.client.head_object(Bucket=self.bucket, Key=key)
        remote_meta = {
            str(k).lower(): str(v)
            for k, v in (head.get("Metadata") or {}).items()
        }
        if int(head.get("ContentLength") or -1) != encrypted_bytes:
            raise OffsiteBackupError("Uploaded off-site object size verification failed.")
        if remote_meta.get("source-sha256") != source_sha256:
            raise OffsiteBackupError("Uploaded off-site object metadata SHA-256 mismatch.")
        if remote_meta.get("source-bytes") != str(plaintext_bytes):
            raise OffsiteBackupError("Uploaded off-site object metadata size mismatch.")

        self._round_trip_verify(
            key,
            expected_sha256=source_sha256,
            expected_bytes=plaintext_bytes,
        )
        retained = self._prune()
        return OffsiteBackupResult(
            key=key,
            source_sha256=source_sha256,
            plaintext_bytes=plaintext_bytes,
            encrypted_bytes=encrypted_bytes,
            uploaded_at=datetime.now(timezone.utc),
            retained=retained,
            missing=missing,
        )

    def latest_key(self) -> str:
        items = sorted(
            self._list_objects(),
            key=lambda item: item.get("LastModified") or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        if not items:
            raise OffsiteBackupError("No off-site backups are available.")
        return str(items[0]["Key"])

    def download_and_verify(self, destination: Path, *, key: str | None = None) -> Path:
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        object_key = key or self.latest_key()
        if not object_key.startswith(self.prefix + "/") or not object_key.endswith(".tar.gz.enc"):
            raise OffsiteBackupError("Object key is outside the configured off-site prefix.")

        head = self.client.head_object(Bucket=self.bucket, Key=object_key)
        metadata = {str(k).lower(): str(v) for k, v in (head.get("Metadata") or {}).items()}
        expected_sha = metadata.get("source-sha256") or ""
        try:
            expected_bytes = int(metadata["source-bytes"])
        except (KeyError, ValueError) as exc:
            raise OffsiteBackupError("Off-site object metadata is incomplete.") from exc

        with tempfile.TemporaryDirectory(prefix="offsite-download-") as tmp:
            encrypted = Path(tmp) / "backup.enc"
            self.client.download_file(self.bucket, object_key, str(encrypted))
            temp_plain = Path(tmp) / "backup.tar.gz"
            self._decrypt(
                encrypted,
                temp_plain,
                expected_sha256=expected_sha,
                expected_bytes=expected_bytes,
            )
            inspection = self.restore_manager.inspect_backup(temp_plain, deep=True)
            if not inspection.valid or inspection.manifest.get("schema") != 2:
                raise OffsiteBackupError(
                    "Downloaded off-site backup failed Full Backup validation."
                )
            shutil.copy2(temp_plain, destination)
        return destination


async def replicate_with_job(
    db: Database,
    service: OffsiteBackupService | None,
    path: Path,
    *,
    trigger: str,
    actor_id: int,
) -> tuple[str, OffsiteBackupResult | None, str]:
    if service is None:
        return "disabled", None, "off-site backup disabled"

    run_id = await db.start_job_run(
        name="backup.offsite",
        trigger=trigger,
        actor_id=actor_id,
    )
    started = datetime.now(timezone.utc)
    try:
        result = await asyncio.to_thread(service.upload_and_verify, path)
        status = "partial" if result.missing else "success"
        details = (
            f"key={result.key}; source_sha256={result.source_sha256}; "
            f"plain={result.plaintext_bytes}; encrypted={result.encrypted_bytes}; "
            f"retained={result.retained}; missing={len(result.missing)}"
        )
        duration_ms = max(
            0,
            int((datetime.now(timezone.utc) - started).total_seconds() * 1000),
        )
        await db.finish_job_run(
            run_id,
            status=status,
            duration_ms=duration_ms,
            details=details,
        )
        return status, result, details
    except Exception as exc:
        duration_ms = max(
            0,
            int((datetime.now(timezone.utc) - started).total_seconds() * 1000),
        )
        details = f"{type(exc).__name__}: {exc}"
        await db.finish_job_run(
            run_id,
            status="failed",
            duration_ms=duration_ms,
            details=details,
        )
        return "failed", None, details


def service_from_settings(settings: Any, restore_manager: RestoreManager) -> OffsiteBackupService | None:
    if not settings.offsite_backup_enabled:
        return None
    return OffsiteBackupService(
        bucket=settings.offsite_backup_bucket,
        prefix=settings.offsite_backup_prefix,
        region=settings.offsite_backup_region,
        endpoint_url=settings.offsite_backup_endpoint_url,
        access_key_id=settings.offsite_backup_access_key_id,
        secret_access_key=settings.offsite_backup_secret_access_key,
        keep=settings.offsite_backup_keep,
        encryption_key_b64=settings.offsite_backup_encryption_key_b64,
        restore_manager=restore_manager,
    )
