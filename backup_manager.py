from __future__ import annotations

import json
import shutil
import sqlite3
import tarfile
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


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
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _sqlite_backup(source: Path, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        src_uri = f"file:{source.resolve()}?mode=ro"
        with sqlite3.connect(src_uri, uri=True, timeout=15) as src:
            with sqlite3.connect(destination) as dst:
                src.backup(dst)

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

    def create_full_backup(self) -> BackupResult:
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

            # 3x-ui SQLite: directory mount lets SQLite see possible -wal/-shm files.
            xui_db = self.sources_root / "x-ui" / "x-ui.db"
            if xui_db.is_file():
                try:
                    self._sqlite_backup(xui_db, stage / "x-ui.db")
                    included.append("x-ui.db")
                except sqlite3.Error:
                    missing.append("x-ui.db (SQLite backup failed)")
            else:
                missing.append("x-ui.db")

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

            created = datetime.now(timezone.utc)
            manifest = {
                "version": "3.6.0",
                "created_at_utc": created.isoformat(),
                "included": included,
                "missing": missing,
                "note": "This archive contains secrets. Store it securely.",
            }
            (stage / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            (stage / "README-RESTORE.txt").write_text(
                "3x-ui Telegram bot backup\n"
                "==========================\n\n"
                "Contents may include bot.sqlite3, x-ui.db, bot.env, "
                "docker-compose.yml and nginx configuration.\n\n"
                "Restore notes:\n"
                "1. Stop the bot before replacing bot.sqlite3.\n"
                "2. Stop x-ui before replacing /etc/x-ui/x-ui.db.\n"
                "3. Restore x-ui.db to a compatible 3x-ui version, then start x-ui.\n"
                "4. Validate nginx with `nginx -t` before reloading it.\n"
                "5. bot.env contains secrets; protect this archive.\n",
                encoding="utf-8",
            )

            with tarfile.open(archive_path, "w:gz") as tar:
                for item in sorted(stage.iterdir(), key=lambda p: p.name):
                    tar.add(item, arcname=item.name, recursive=True)

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
