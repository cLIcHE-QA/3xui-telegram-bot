from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import tarfile
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from version import APP_VERSION


BACKUP_MANIFEST_SCHEMA = 2


def _ensure_private_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, 0o700)


def _prepare_private_file(path: Path) -> None:
    _ensure_private_dir(path.parent)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT, 0o600)
    os.close(fd)
    os.chmod(path, 0o600)


def _tighten_private_tree(root: Path) -> None:
    for path in root.rglob("*"):
        if path.is_symlink():
            continue
        try:
            if path.is_dir():
                os.chmod(path, 0o700)
            elif path.is_file():
                os.chmod(path, 0o600)
        except OSError:
            continue


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _integrity_entries(root: Path) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if relative == "manifest.json":
            continue
        entries.append({
            "path": relative,
            "bytes": path.stat().st_size,
            "sha256": _sha256_path(path),
        })
    return entries


@dataclass(frozen=True)
class BackupInfo:
    path: Path
    created_at: datetime
    size: int


@dataclass(frozen=True)
class BackupResult:
    info: BackupInfo
    included: tuple[str, ...]
    missing: tuple[str, ...]


class BackupManager:
    def __init__(self, db_path: str, backup_dir: str, keep: int = 14):
        self.db_path = Path(db_path)
        self.backup_dir = Path(backup_dir)
        self.keep = max(1, int(keep))
        self.sources_root = Path("/app/backup_sources")

    def _ensure_dir(self) -> None:
        _ensure_private_dir(self.backup_dir)
        _tighten_private_tree(self.backup_dir)

    @staticmethod
    def _sqlite_backup(source: Path, destination: Path) -> None:
        # Do not leave an empty or partial database on failed SQLite backup.
        _prepare_private_file(destination)
        try:
            src_uri = f"file:{source.resolve()}?mode=ro"
            with sqlite3.connect(src_uri, uri=True, timeout=15) as src:
                with sqlite3.connect(destination) as dst:
                    src.backup(dst)
            with sqlite3.connect(f"file:{destination.resolve()}?mode=ro", uri=True) as check:
                if check.execute("PRAGMA quick_check").fetchone() != ("ok",):
                    raise sqlite3.DatabaseError("Snapshot failed SQLite quick_check")
            os.chmod(destination, 0o600)
        except (sqlite3.Error, OSError):
            destination.unlink(missing_ok=True)
            raise

    @staticmethod
    def _copy_file(source: Path, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    @staticmethod
    def _copy_tree(source: Path, destination: Path) -> None:
        shutil.copytree(source, destination, symlinks=True, dirs_exist_ok=True)

    def _timestamp(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    def create_bot_snapshot(self) -> Path:
        self._ensure_dir()
        target = self.backup_dir / f"bot-snapshot-{self._timestamp()}.sqlite3"
        self._sqlite_backup(self.db_path, target)
        return target

    def create_full_backup(
        self,
        extra_files: dict[str, Path] | None = None,
        extra_missing: list[str] | tuple[str, ...] | None = None,
        *,
        version: str = APP_VERSION,
        extra_manifest: dict | None = None,
        master_database: bytes | None = None,
    ) -> BackupResult:
        self._ensure_dir()
        stamp = self._timestamp()
        archive_path = self.backup_dir / f"3xui-bot-backup-{stamp}.tar.gz"
        included: list[str] = []
        missing: list[str] = []

        with tempfile.TemporaryDirectory(prefix="backup-stage-") as tmp:
            stage = Path(tmp) / "backup"
            stage.mkdir(parents=True, exist_ok=True)

            # Bot SQLite: always create a consistent SQLite snapshot.
            self._sqlite_backup(self.db_path, stage / "bot.sqlite3")
            included.append("bot.sqlite3")

            # Production prefers the panel's authenticated database export, which
            # is independent from chmod 0600 on the live WAL/SHM files.
            if master_database is not None:
                snapshot = stage / "x-ui.db"
                if not master_database.startswith(b"SQLite format 3\x00"):
                    raise RuntimeError("Full Backup blocked: Master API returned non-SQLite data")
                _prepare_private_file(snapshot)
                snapshot.write_bytes(master_database)
                try:
                    with sqlite3.connect(f"file:{snapshot.resolve()}?mode=ro", uri=True) as conn:
                        if conn.execute("PRAGMA quick_check").fetchone() != ("ok",):
                            raise sqlite3.DatabaseError("Master API snapshot failed SQLite quick_check")
                except sqlite3.Error as exc:
                    snapshot.unlink(missing_ok=True)
                    raise RuntimeError("Full Backup blocked: invalid Master API SQLite snapshot") from exc
                included.append("x-ui.db")
            else:
                # Legacy/offline source: SQLite backup requires readable WAL/SHM.
                xui_db = self.sources_root / "x-ui" / "x-ui.db"
                if not xui_db.is_file():
                    raise RuntimeError("Full Backup blocked: required Master x-ui.db is missing")
                try:
                    self._sqlite_backup(xui_db, stage / "x-ui.db")
                except (sqlite3.Error, OSError) as exc:
                    raise RuntimeError(
                        f"Full Backup blocked: Master x-ui.db SQLite snapshot failed ({type(exc).__name__})"
                    ) from exc
                included.append("x-ui.db")

            bot_env = self.sources_root / "bot.env"
            if bot_env.is_file():
                self._copy_file(bot_env, stage / "bot.env")
                included.append("bot.env")
            else:
                missing.append("bot.env")

            compose = Path("/app/docker-compose.yml")
            if compose.is_file():
                self._copy_file(compose, stage / "docker-compose.yml")
                included.append("docker-compose.yml")
            else:
                missing.append("docker-compose.yml")

            nginx_dir = self.sources_root / "nginx"
            if nginx_dir.is_dir():
                self._copy_tree(nginx_dir, stage / "nginx")
                included.append("nginx/")
            else:
                missing.append("nginx/")

            # Optional external/node files collected by the caller. Archive names
            # are relative and cannot escape the staging directory.
            for arcname, source in (extra_files or {}).items():
                rel = Path(arcname)
                if rel.is_absolute() or ".." in rel.parts:
                    missing.append(f"{arcname} (unsafe archive path)")
                    continue
                source = Path(source)
                if not source.exists():
                    missing.append(f"{arcname} (source missing)")
                    continue
                destination = stage / rel
                if source.is_dir():
                    self._copy_tree(source, destination)
                else:
                    self._copy_file(source, destination)
                included.append(rel.as_posix() + ("/" if source.is_dir() else ""))

            if extra_missing:
                missing.extend(str(x) for x in extra_missing)

            created = datetime.now(timezone.utc)
            (stage / "README-RESTORE.txt").write_text(
                "3x-ui Telegram bot backup\n"
                "==========================\n\n"
                "Contents may include bot.sqlite3, x-ui.db, bot.env, "
                "docker-compose.yml, nginx configuration and nodes/* backups.\n\n"
                "Restore notes:\n"
                "1. Stop the bot before replacing bot.sqlite3.\n"
                "2. Stop x-ui before replacing /etc/x-ui/x-ui.db.\n"
                "3. Restore x-ui.db to a compatible 3x-ui version, then start x-ui.\n"
                "4. Validate nginx with `nginx -t` before reloading it.\n"
                "5. bot.env contains secrets; protect this archive.\n",
                encoding="utf-8",
            )

            manifest = {
                "schema": BACKUP_MANIFEST_SCHEMA,
                "version": version,
                "created_at_utc": created.isoformat(),
                "included": included,
                "missing": missing,
                "note": "This archive contains secrets. Store it securely.",
            }
            if extra_manifest:
                manifest.update(extra_manifest)
            manifest["schema"] = BACKUP_MANIFEST_SCHEMA
            manifest["integrity"] = {
                "algorithm": "sha256",
                "files": _integrity_entries(stage),
            }
            (stage / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )

            # Create a mode-0600 temporary archive on the same filesystem;
            # never expose partially written backups under the canonical name.
            fd, private_name = tempfile.mkstemp(
                prefix=".backup-pending-", suffix=".tar.gz", dir=self.backup_dir,
            )
            pending = Path(private_name)
            try:
                with os.fdopen(fd, "wb") as output:
                    with tarfile.open(fileobj=output, mode="w:gz") as tar:
                        for item in sorted(stage.iterdir(), key=lambda p: p.name):
                            tar.add(item, arcname=item.name, recursive=True)
                    output.flush()
                    os.fsync(output.fileno())

                # The same deep validator protects off-site upload and restore.
                # Do not publish a local archive that would fail that gate.
                from restore_manager import RestoreManager

                inspection = RestoreManager(
                    str(self.db_path), str(self.backup_dir),
                ).inspect_backup(pending, deep=True)
                if not inspection.valid:
                    raise RuntimeError(
                        "Full Backup blocked: archive failed deep validation ("
                        + "; ".join(inspection.errors[:3]) + ")"
                    )
                os.replace(pending, archive_path)
            finally:
                pending.unlink(missing_ok=True)

        self.prune()
        stat = archive_path.stat()
        return BackupResult(
            info=BackupInfo(path=archive_path, created_at=created, size=stat.st_size),
            included=tuple(included),
            missing=tuple(missing),
        )

    def list_backups(self) -> list[BackupInfo]:
        self._ensure_dir()
        items: list[BackupInfo] = []
        for path in self.backup_dir.glob("3xui-bot-backup-*.tar.gz"):
            try:
                stat = path.stat()
            except OSError:
                continue
            items.append(
                BackupInfo(
                    path=path,
                    created_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                    size=stat.st_size,
                )
            )
        return sorted(items, key=lambda item: item.created_at, reverse=True)

    def latest_backup(self) -> BackupInfo | None:
        items = self.list_backups()
        return items[0] if items else None

    def prune(self) -> None:
        items = self.list_backups()
        for item in items[self.keep:]:
            try:
                item.path.unlink()
            except OSError:
                pass

        # One-off DB snapshots are temporary convenience downloads.
        snapshots = sorted(
            self.backup_dir.glob("bot-snapshot-*.sqlite3"),
            key=lambda p: p.stat().st_mtime if p.exists() else 0,
            reverse=True,
        )
        for path in snapshots[3:]:
            try:
                path.unlink()
            except OSError:
                pass
