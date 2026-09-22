from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import sqlite3
import tarfile
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MAX_ARCHIVE_MEMBERS = 5000
MAX_MEMBER_BYTES = 512 * 1024 * 1024
MAX_TOTAL_BYTES = 2 * 1024 * 1024 * 1024


@dataclass(frozen=True)
class NodeBackupComponent:
    name: str
    member_name: str
    database_filename: str
    source_panel_url: str


@dataclass(frozen=True)
class BackupInspection:
    path: Path
    backup_id: str
    created_at: datetime
    size: int
    valid: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    manifest: dict[str, Any]
    members: tuple[str, ...]
    has_bot_db: bool
    has_xui_db: bool
    has_bot_env: bool
    nginx_files: int
    nodes: tuple[NodeBackupComponent, ...]
    bot_db_ok: bool | None
    xui_db_ok: bool | None
    panel_token_matches: bool | None


class RestoreError(RuntimeError):
    pass


class RestoreManager:
    def __init__(self, db_path: str, backup_dir: str):
        self.db_path = Path(db_path)
        self.backup_dir = Path(backup_dir)
        self.restore_root = self.db_path.parent / "restore"
        self.rescue_root = self.backup_dir / "rescue"
        self.export_root = self.restore_root / "exports"
        self.pending_root = self.restore_root / "pending"
        self.result_path = self.restore_root / "result.json"
        self.history_path = self.restore_root / "restore-history.jsonl"

    @staticmethod
    def backup_id(path: Path) -> str:
        name = path.name
        prefix = "3xui-bot-backup-"
        suffix = ".tar.gz"
        if name.startswith(prefix) and name.endswith(suffix):
            return name[len(prefix):-len(suffix)]
        return hashlib.sha256(name.encode("utf-8")).hexdigest()[:16]

    def list_backups(self) -> list[Path]:
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        return sorted(
            self.backup_dir.glob("3xui-bot-backup-*.tar.gz"),
            key=lambda p: p.stat().st_mtime if p.exists() else 0,
            reverse=True,
        )

    def find_backup(self, backup_id: str) -> Path:
        needle = (backup_id or "").strip()
        for path in self.list_backups():
            if self.backup_id(path) == needle:
                return path
        raise RestoreError("Backup не найден или уже удалён политикой retention.")

    @staticmethod
    def _safe_member_name(name: str) -> bool:
        if not name or name.startswith(("/", "\\")):
            return False
        normalized = name.replace("\\", "/")
        parts = Path(normalized).parts
        return all(part not in {"", ".", ".."} for part in parts)

    @classmethod
    def _checked_members(cls, tar: tarfile.TarFile) -> list[tarfile.TarInfo]:
        members = tar.getmembers()
        if len(members) > MAX_ARCHIVE_MEMBERS:
            raise RestoreError(f"Слишком много файлов в архиве: {len(members)}")
        total = 0
        for member in members:
            if not cls._safe_member_name(member.name):
                raise RestoreError(f"Небезопасный путь в архиве: {member.name!r}")
            if member.issym() or member.islnk() or member.isdev() or member.isfifo():
                raise RestoreError(f"Неподдерживаемый тип файла: {member.name}")
            if member.isfile():
                if member.size < 0 or member.size > MAX_MEMBER_BYTES:
                    raise RestoreError(f"Слишком большой файл в архиве: {member.name}")
                total += int(member.size)
                if total > MAX_TOTAL_BYTES:
                    raise RestoreError("Распакованный архив превышает безопасный лимит.")
        return members

    @staticmethod
    def _read_tar_member(tar: tarfile.TarFile, member: tarfile.TarInfo) -> bytes:
        if not member.isfile():
            raise RestoreError(f"{member.name} не является обычным файлом")
        src = tar.extractfile(member)
        if src is None:
            raise RestoreError(f"Не удалось прочитать {member.name}")
        data = src.read(MAX_MEMBER_BYTES + 1)
        if len(data) > MAX_MEMBER_BYTES:
            raise RestoreError(f"Файл слишком большой: {member.name}")
        return data

    @staticmethod
    def _sqlite_check_bytes(data: bytes) -> tuple[bool, str]:
        if not data.startswith(b"SQLite format 3\x00"):
            return False, "not SQLite3"
        with tempfile.TemporaryDirectory(prefix="restore-sqlite-") as tmp:
            path = Path(tmp) / "db.sqlite3"
            path.write_bytes(data)
            try:
                uri = f"file:{path.resolve()}?mode=ro"
                with sqlite3.connect(uri, uri=True, timeout=10) as conn:
                    rows = conn.execute("PRAGMA quick_check").fetchall()
                values = [str(row[0]) for row in rows]
                ok = bool(values) and all(v.lower() == "ok" for v in values)
                return ok, "; ".join(values[:10])
            except sqlite3.Error as exc:
                return False, str(exc)

    @staticmethod
    def _parse_env_value(text: str, key: str) -> str | None:
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, value = line.split("=", 1)
            if k.strip() != key:
                continue
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                value = value[1:-1]
            return value
        return None

    def inspect_backup(
        self,
        path: Path,
        *,
        deep: bool = False,
        current_panel_token: str | None = None,
    ) -> BackupInspection:
        path = Path(path)
        if not path.is_file():
            raise RestoreError("Backup-файл не найден.")
        errors: list[str] = []
        warnings: list[str] = []
        manifest: dict[str, Any] = {}
        member_names: list[str] = []
        nodes: list[NodeBackupComponent] = []
        bot_db_ok: bool | None = None
        xui_db_ok: bool | None = None
        token_match: bool | None = None
        has_bot_db = False
        has_xui_db = False
        has_bot_env = False
        nginx_files = 0

        try:
            with tarfile.open(path, "r:gz") as tar:
                members = self._checked_members(tar)
                by_name = {m.name: m for m in members}
                member_names = sorted(by_name)
                has_bot_db = "bot.sqlite3" in by_name
                has_xui_db = "x-ui.db" in by_name
                has_bot_env = "bot.env" in by_name
                nginx_files = sum(1 for n, m in by_name.items() if n.startswith("nginx/") and m.isfile())

                manifest_member = by_name.get("manifest.json")
                if manifest_member and manifest_member.isfile():
                    try:
                        raw = self._read_tar_member(tar, manifest_member)
                        parsed = json.loads(raw.decode("utf-8"))
                        if isinstance(parsed, dict):
                            manifest = parsed
                        else:
                            warnings.append("manifest.json имеет неожиданный формат")
                    except Exception as exc:
                        warnings.append(f"manifest.json не прочитан: {type(exc).__name__}: {exc}")
                else:
                    warnings.append("manifest.json отсутствует")

                # Discover node backups from node.json metadata. A node backup without
                # metadata is deliberately not auto-restorable.
                for name, member in sorted(by_name.items()):
                    if not (name.startswith("nodes/") and name.endswith("/node.json") and member.isfile()):
                        continue
                    try:
                        meta = json.loads(self._read_tar_member(tar, member).decode("utf-8"))
                        if not isinstance(meta, dict):
                            raise ValueError("metadata is not an object")
                        node_name = str(meta.get("node_name") or "").strip()
                        db_file = Path(str(meta.get("database_file") or "")).name
                        source_url = str(meta.get("source_panel_url") or "").strip()
                        if not node_name or not db_file:
                            raise ValueError("missing node_name/database_file")
                        base = name.rsplit("/", 1)[0]
                        db_member = f"{base}/{db_file}"
                        if db_member not in by_name or not by_name[db_member].isfile():
                            raise ValueError(f"database file missing: {db_member}")
                        nodes.append(NodeBackupComponent(
                            name=node_name,
                            member_name=db_member,
                            database_filename=db_file,
                            source_panel_url=source_url,
                        ))
                    except Exception as exc:
                        warnings.append(f"Node metadata {name}: {type(exc).__name__}: {exc}")

                if deep and has_bot_db:
                    bot_db_ok, detail = self._sqlite_check_bytes(
                        self._read_tar_member(tar, by_name["bot.sqlite3"])
                    )
                    if not bot_db_ok:
                        errors.append(f"bot.sqlite3: {detail}")

                if deep and has_xui_db:
                    xui_data = self._read_tar_member(tar, by_name["x-ui.db"])
                    # Full backups produced by this project store SQLite here.
                    xui_db_ok, detail = self._sqlite_check_bytes(xui_data)
                    if not xui_db_ok:
                        errors.append(f"x-ui.db: {detail}")

                if has_bot_env and current_panel_token is not None:
                    try:
                        env_text = self._read_tar_member(tar, by_name["bot.env"]).decode("utf-8", errors="replace")
                        archived_token = self._parse_env_value(env_text, "PANEL_API_TOKEN")
                        token_match = archived_token == current_panel_token if archived_token is not None else None
                        if archived_token is None:
                            warnings.append("В bot.env нет PANEL_API_TOKEN; совместимость токена не проверена")
                    except Exception as exc:
                        warnings.append(f"Не удалось проверить PANEL_API_TOKEN: {type(exc).__name__}: {exc}")

                if not has_bot_db:
                    warnings.append("bot.sqlite3 отсутствует")
                if not has_xui_db:
                    warnings.append("x-ui.db отсутствует")
        except (tarfile.TarError, OSError, RestoreError) as exc:
            errors.append(f"Архив не прошёл проверку: {type(exc).__name__}: {exc}")

        try:
            stat = path.stat()
            created_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
            size = stat.st_size
        except OSError:
            created_at = datetime.now(timezone.utc)
            size = 0

        return BackupInspection(
            path=path,
            backup_id=self.backup_id(path),
            created_at=created_at,
            size=size,
            valid=not errors,
            errors=tuple(errors),
            warnings=tuple(warnings),
            manifest=manifest,
            members=tuple(member_names),
            has_bot_db=has_bot_db,
            has_xui_db=has_xui_db,
            has_bot_env=has_bot_env,
            nginx_files=nginx_files,
            nodes=tuple(nodes),
            bot_db_ok=bot_db_ok,
            xui_db_ok=xui_db_ok,
            panel_token_matches=token_match,
        )

    def read_member(self, path: Path, member_name: str) -> bytes:
        with tarfile.open(path, "r:gz") as tar:
            members = self._checked_members(tar)
            by_name = {m.name: m for m in members}
            member = by_name.get(member_name)
            if member is None:
                raise RestoreError(f"В backup нет {member_name}")
            return self._read_tar_member(tar, member)

    def export_member(self, path: Path, member_name: str, *, filename: str | None = None) -> Path:
        data = self.read_member(path, member_name)
        self.export_root.mkdir(parents=True, exist_ok=True)
        safe = Path(filename or Path(member_name).name).name
        if not safe or safe in {".", ".."}:
            safe = "restore-export.bin"
        out = self.export_root / f"{self.backup_id(path)}-{safe}"
        out.write_bytes(data)
        return out

    def export_nginx_bundle(self, path: Path) -> Path:
        self.export_root.mkdir(parents=True, exist_ok=True)
        out = self.export_root / f"{self.backup_id(path)}-nginx.tar.gz"
        with tarfile.open(path, "r:gz") as src, tarfile.open(out, "w:gz") as dst:
            members = self._checked_members(src)
            selected = [m for m in members if m.name.startswith("nginx/") and (m.isfile() or m.isdir())]
            if not selected:
                raise RestoreError("В backup нет nginx/.")
            for member in selected:
                if member.isdir():
                    info = tarfile.TarInfo(member.name)
                    info.type = tarfile.DIRTYPE
                    info.mode = member.mode
                    info.mtime = member.mtime
                    dst.addfile(info)
                    continue
                data = self._read_tar_member(src, member)
                info = tarfile.TarInfo(member.name)
                info.size = len(data)
                info.mode = member.mode
                info.mtime = member.mtime
                dst.addfile(info, io.BytesIO(data))
        return out

    @staticmethod
    def _sqlite_backup(source: Path, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        src_uri = f"file:{source.resolve()}?mode=ro"
        with sqlite3.connect(src_uri, uri=True, timeout=15) as src:
            with sqlite3.connect(destination) as dst:
                src.backup(dst)

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as fh:
            while True:
                chunk = fh.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest()

    def append_history(self, event: dict[str, Any]) -> None:
        self.restore_root.mkdir(parents=True, exist_ok=True)
        payload = dict(event)
        payload.setdefault("at_utc", datetime.now(timezone.utc).isoformat())
        with self.history_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")

    def recent_history(self, limit: int = 10) -> list[dict[str, Any]]:
        if not self.history_path.is_file():
            return []
        try:
            lines = self.history_path.read_text(encoding="utf-8").splitlines()[-max(1, limit):]
        except OSError:
            return []
        out: list[dict[str, Any]] = []
        for line in reversed(lines):
            try:
                item = json.loads(line)
                if isinstance(item, dict):
                    out.append(item)
            except json.JSONDecodeError:
                continue
        return out

    def pending_bot_restore(self) -> bool:
        return (self.pending_root / "pending.json").is_file()

    def stage_bot_restore(self, backup_path: Path, *, actor_id: int) -> dict[str, Any]:
        if self.pending_bot_restore():
            raise RestoreError("Уже есть ожидающее восстановление bot.sqlite3.")
        inspection = self.inspect_backup(backup_path, deep=True)
        if not inspection.valid or inspection.bot_db_ok is not True:
            raise RestoreError("bot.sqlite3 не прошёл preflight/SQLite quick_check.")

        self.pending_root.mkdir(parents=True, exist_ok=True)
        self.rescue_root.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

        # Rescue snapshot of the live database before scheduling the restart.
        rescue = self.rescue_root / f"pre-restore-bot-{stamp}.sqlite3"
        self._sqlite_backup(self.db_path, rescue)

        staged = self.pending_root / "bot.sqlite3"
        staged.write_bytes(self.read_member(backup_path, "bot.sqlite3"))
        ok, detail = self._sqlite_check_bytes(staged.read_bytes())
        if not ok:
            staged.unlink(missing_ok=True)
            raise RestoreError(f"Staged bot.sqlite3 invalid: {detail}")

        marker = {
            "kind": "bot.sqlite3",
            "backup_id": inspection.backup_id,
            "backup_name": backup_path.name,
            "actor_id": int(actor_id),
            "requested_at_utc": datetime.now(timezone.utc).isoformat(),
            "staged_path": str(staged),
            "staged_sha256": self._sha256(staged),
            "db_path": str(self.db_path),
            "rescue_path": str(rescue),
        }
        marker_path = self.pending_root / "pending.json"
        marker_path.write_text(json.dumps(marker, ensure_ascii=False, indent=2), encoding="utf-8")
        self.append_history({
            "status": "scheduled",
            "kind": "bot.sqlite3",
            "backup_id": inspection.backup_id,
            "actor_id": int(actor_id),
            "rescue": str(rescue),
        })
        return marker

    def perform_pending_bot_restore(self) -> dict[str, Any] | None:
        marker_path = self.pending_root / "pending.json"
        if not marker_path.is_file():
            return None
        self.restore_root.mkdir(parents=True, exist_ok=True)
        result: dict[str, Any]
        try:
            marker = json.loads(marker_path.read_text(encoding="utf-8"))
            if not isinstance(marker, dict) or marker.get("kind") != "bot.sqlite3":
                raise RestoreError("Invalid pending restore marker")
            # Do not trust filesystem paths from the marker even though it is bot-generated.
            # The bootstrap only ever restores the configured bot DB from its fixed staging path.
            staged = self.pending_root / "bot.sqlite3"
            target = self.db_path
            expected_hash = str(marker.get("staged_sha256") or "")
            if not staged.is_file():
                raise RestoreError("Staged bot.sqlite3 is missing")
            if expected_hash and self._sha256(staged) != expected_hash:
                raise RestoreError("Staged bot.sqlite3 SHA-256 mismatch")
            ok, detail = self._sqlite_check_bytes(staged.read_bytes())
            if not ok:
                raise RestoreError(f"Staged bot.sqlite3 failed quick_check: {detail}")

            stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            rescue = self.rescue_root / f"pre-restore-bot-bootstrap-{stamp}.sqlite3"
            if target.is_file():
                self._sqlite_backup(target, rescue)

            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.parent / f".{target.name}.restore-{os.getpid()}"
            shutil.copy2(staged, tmp)
            with tmp.open("rb+") as fh:
                os.fsync(fh.fileno())
            os.replace(tmp, target)
            for suffix in ("-wal", "-shm"):
                try:
                    Path(str(target) + suffix).unlink()
                except FileNotFoundError:
                    pass

            result = {
                "status": "success",
                "kind": "bot.sqlite3",
                "backup_id": marker.get("backup_id"),
                "backup_name": marker.get("backup_name"),
                "actor_id": marker.get("actor_id", 0),
                "at_utc": datetime.now(timezone.utc).isoformat(),
                "rescue": str(rescue),
            }
            staged.unlink(missing_ok=True)
            marker_path.unlink(missing_ok=True)
        except Exception as exc:
            result = {
                "status": "failed",
                "kind": "bot.sqlite3",
                "error": f"{type(exc).__name__}: {exc}",
                "at_utc": datetime.now(timezone.utc).isoformat(),
            }
            # Do not loop forever on container restart after a broken restore request.
            try:
                failed = self.pending_root / f"failed-{int(time.time())}.json"
                marker_path.replace(failed)
            except OSError:
                try:
                    marker_path.unlink(missing_ok=True)
                except OSError:
                    pass

        self.result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        self.append_history(result)
        return result

    def consume_boot_result(self) -> dict[str, Any] | None:
        if not self.result_path.is_file():
            return None
        try:
            data = json.loads(self.result_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else None
        finally:
            try:
                self.result_path.unlink()
            except OSError:
                pass

    def save_rescue_blob(self, scope: str, filename: str, body: bytes) -> Path:
        safe_scope = "".join(ch if ch.isalnum() or ch in "._-" else "-" for ch in scope).strip("-._") or "target"
        safe_name = Path(filename).name or "database.bin"
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        out_dir = self.rescue_root / safe_scope
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"pre-restore-{stamp}-{safe_name}"
        path.write_bytes(body)
        return path
