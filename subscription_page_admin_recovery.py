"""D1b #887: offline sealed backup, verification and staged Fernet rotation.

This module NEVER switches a running instance, publishes credentials, alters the
source roster/database or starts a network listener. Operators must stop every
D1b writer and activate a verified, staged private directory separately.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets
import shutil
import sqlite3
import stat
from dataclasses import dataclass
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from subscription_page_admin import EncryptedDrafts
from subscription_page_admin_vault import EncryptedAdminRoster

# Bound in-memory SQLite snapshots and sealed backup input; reject huge
# or hostile files before loading them. No plaintext snapshot is written.
_MAX_DB_BYTES = 64 * 1024 * 1024
_MAX_BACKUP_BYTES = 96 * 1024 * 1024
_MAX_ROSTER_BYTES = 131072
_FILENAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}")


@dataclass(frozen=True)
class RecoveryResult:
    """Only non-sensitive metadata. Source is never modified."""
    destination: str
    revision: int
    drafts: int
    revoked_sessions: int


def _private_dir(path: Path) -> None:
    if path.is_symlink() or not path.is_dir():
        raise ValueError("Private offline directory missing or symlink")
    info = path.stat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
            or info.st_mode & 0o077):
        raise ValueError("Private directory requires owner-only 0700")


def _private_bytes(path: Path, limit: int) -> bytes:
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or info.st_nlink != 1 or info.st_mode & 0o077
                or info.st_size > limit):
            raise ValueError("Private file security or size check failed")
        with os.fdopen(fd, "rb", closefd=False) as reader:
            data = reader.read(limit + 1)
        if not data or len(data) > limit:
            raise ValueError("Private file empty or too large")
        return data
    finally:
        os.close(fd)


def _write_new_file(path: Path, data: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                 | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        with os.fdopen(fd, "wb", closefd=False) as stream:
            stream.write(data)
            stream.flush()
            os.fsync(fd)
    finally:
        os.close(fd)


def _fsync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _validate_memory(db: sqlite3.Connection, key: bytes) -> int:
    """Fail closed before any backup/restore/rotation write."""
    check = db.execute("PRAGMA quick_check").fetchone()
    if not check or check[0] != "ok":
        raise ValueError("Draft database integrity check failed")
    required = {
        "draft_revisions": {"revision", "content", "digest", "actor", "saved_at"},
        "draft_proposals": {"id", "revision", "digest", "actor", "created_at", "state"},
        "admin_totp_replay": {"username", "last_step"},
        "admin_sessions": {"token_hash", "username", "csrf_ciphertext",
                           "expires_at", "last_seen_at", "account_binding"},
    }
    for table, columns in required.items():
        present = {row[1] for row in db.execute(f"PRAGMA table_info({table})")}
        if not columns <= present:
            raise ValueError("Draft database schema cannot be recovered safely")
    cipher = Fernet(key)
    from subscription_page_config import parse_config
    count = 0
    try:
        for ciphertext, digest in db.execute("SELECT content,digest FROM draft_revisions"):
            original = cipher.decrypt(ciphertext)
            if not isinstance(digest, str) or hashlib.sha256(original).hexdigest() != digest:
                raise ValueError("Encrypted draft digest mismatch")
            parse_config(original)
            count += 1
        for (csrf,) in db.execute("SELECT csrf_ciphertext FROM admin_sessions"):
            cipher.decrypt(csrf).decode("ascii")
    except (InvalidToken, UnicodeError, TypeError) as exc:
        raise ValueError("Draft database encryption key or content invalid") from exc
    return count


def _decode_database(blob: bytes, key: bytes) -> tuple[sqlite3.Connection, int]:
    if not isinstance(blob, bytes) or not blob or len(blob) > _MAX_DB_BYTES:
        raise ValueError("Invalid backup database size")
    db = sqlite3.connect(":memory:")
    try:
        db.deserialize(blob)
        count = _validate_memory(db, key)
    except (sqlite3.Error, ValueError):
        db.close()
        raise ValueError("Encrypted draft database validation failed") from None
    return db, count


def _write_db(path: Path, db: sqlite3.Connection) -> None:
    _write_new_file(path, b"") if False else None  # kept out of the file system
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_EXCL
                 | getattr(os, "O_NOFOLLOW", 0), 0o600)
    os.close(fd)
    out = sqlite3.connect(str(path))
    try:
        db.backup(out)
        out.commit()
    finally:
        out.close()
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class OfflineD1bRecovery:
    """Stages *new* offline bundles; no destructive live in-place operations."""

    def __init__(self, source_dir: str | Path, encryption_key: bytes, *,
                 roster_name: str = "private-accounts.enc",
                 db_name: str = "drafts.sqlite3"):
        self.source_dir = Path(source_dir)
        self.roster_name, self.db_name = roster_name, db_name
        if (any(not isinstance(n, str) or not _FILENAME.fullmatch(n)
                or n in (".", "..") for n in (roster_name, db_name))
                or roster_name == db_name):
            raise ValueError("Invalid offline D1b filenames")
        _private_dir(self.source_dir)
        self.roster_path = self.source_dir / roster_name
        self.db_path = self.source_dir / db_name
        self.key = encryption_key
        self.cipher = Fernet(encryption_key)

    def _snapshot(self) -> tuple[int, list, bytes]:
        """Validate source and capture a consistent SQLite snapshot in memory.

        Operator must already have stopped all D1b writers; SQLite backup only
        ensures DB-local consistency, not roster/DB cross-file atomicity.
        """
        _private_bytes(self.db_path, _MAX_DB_BYTES)
        roster = EncryptedAdminRoster(self.roster_path, self.key)
        revision, accounts = roster.snapshot()
        connection = sqlite3.connect(
            "file:" + str(self.db_path) + "?mode=ro", uri=True, timeout=3)
        memory = sqlite3.connect(":memory:")
        try:
            connection.backup(memory)
            _validate_memory(memory, self.key)
            serialized = memory.serialize()
            if len(serialized) > _MAX_DB_BYTES:
                raise ValueError("Draft snapshot exceeds offline memory bound")
        finally:
            connection.close()
            memory.close()
        return revision, accounts, serialized

    def _create_stage(self, dest: Path, accounts: list,
                      revision: int, db: sqlite3.Connection,
                      key: bytes, drafts: int, sessions: int) -> RecoveryResult:
        # A target is never overwritten. Parent is operator-managed 0700.
        _private_dir(dest.parent)
        if dest.exists() or dest.is_symlink() or dest == self.source_dir:
            raise FileExistsError("Offline stage destination already exists")
        stage = dest.with_name("." + dest.name + "." + secrets.token_hex(12) + ".stage")
        stage.mkdir(mode=0o700)
        published = False
        try:
            staged_roster = EncryptedAdminRoster(stage / self.roster_name, key)
            with staged_roster._lock():
                staged_roster._write(revision, accounts)
            _write_db(stage / self.db_name, db)
            # Independently read back both files with the destination key.
            check_roster = EncryptedAdminRoster(stage / self.roster_name, key)
            if check_roster.snapshot() != (revision, accounts):
                raise ValueError("Staged roster verification failed")
            with sqlite3.connect(str(stage / self.db_name)) as check_db:
                if _validate_memory(check_db, key) != drafts:
                    raise ValueError("Staged draft verification failed")
                if check_db.execute("SELECT COUNT(*) FROM admin_sessions").fetchone()[0]:
                    raise ValueError("Restored sessions must be revoked")
            _fsync_dir(stage)
            if dest.exists() or dest.is_symlink():
                raise FileExistsError("Offline stage destination already exists")
            os.rename(stage, dest)
            published = True
            _fsync_dir(dest.parent)
            return RecoveryResult(str(dest), revision, drafts, sessions)
        finally:
            if not published:
                shutil.rmtree(stage)

    def backup(self, backup_path: str | Path, backup_key: bytes) -> int:
        """Seal a complete snapshot under a separate key, refusing overwrites.

        No raw SQLite or credential plaintext is ever written to backup disk.
        """
        if secrets.compare_digest(self.key, backup_key):
            raise ValueError("Backup must have a different independent key")
        wrapper = Fernet(backup_key)
        revision, accounts, serialized = self._snapshot()
        _private_dir(Path(backup_path).parent)
        # Snapshot roster content under current key, then seal both pieces
        # again under the independent backup key.
        roster_payload = [{
            "username": a.username, "role": a.role,
            "password_hash": a.password_hash, "totp_secret_b32": a.totp_secret_b32,
        } for a in accounts]
        payload = json.dumps({
            "schema": 1, "revision": revision,
            "roster": roster_payload,
            "db_sha256": hashlib.sha256(serialized).hexdigest(),
            "db": base64.b64encode(serialized).decode("ascii"),
            "roster_name": self.roster_name, "db_name": self.db_name,
        }, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        sealed = wrapper.encrypt(payload)
        if len(sealed) > _MAX_BACKUP_BYTES:
            raise ValueError("Sealed backup too large")
        _write_new_file(Path(backup_path), sealed)
        _fsync_dir(Path(backup_path).parent)
        if _private_bytes(Path(backup_path), _MAX_BACKUP_BYTES) != sealed:
            raise ValueError("Sealed backup verification failed")
        return revision

    @staticmethod
    def _read_backup(path: Path, backup_key: bytes,
                     roster_name: str, db_name: str) -> tuple[int, list, bytes]:
        _private_dir(path.parent)
        try:
            payload = Fernet(backup_key).decrypt(_private_bytes(path, _MAX_BACKUP_BYTES))
            if len(payload) > _MAX_BACKUP_BYTES:
                raise ValueError("Sealed backup payload too large")
            obj = json.loads(payload)
            if (not isinstance(obj, dict)
                    or set(obj) != {"schema", "revision", "roster",
                                   "db_sha256", "db", "roster_name", "db_name"}
                    or obj["schema"] != 1 or not isinstance(obj["revision"], int)
                    or isinstance(obj["revision"], bool) or obj["revision"] < 1
                    or obj["roster_name"] != roster_name or obj["db_name"] != db_name
                    or not isinstance(obj["roster"], list)
                    or not isinstance(obj["db"], str)):
                raise ValueError("Unknown sealed backup schema")
            from subscription_page_admin import AdminAccount
            from subscription_page_admin_vault import _valid_accounts
            acc = []
            for x in obj["roster"]:
                if not isinstance(x, dict) or set(x) != {
                        "username", "role", "password_hash", "totp_secret_b32"}:
                    raise ValueError("Invalid backup roster")
                acc.append(AdminAccount(**x))
            _valid_accounts(acc)
            serialized = base64.b64decode(obj["db"], validate=True)
            if (len(serialized) > _MAX_DB_BYTES or
                    hashlib.sha256(serialized).hexdigest() != obj["db_sha256"]):
                raise ValueError("Sealed backup digest invalid")
            return obj["revision"], acc, serialized
        except (InvalidToken, TypeError, KeyError, ValueError, UnicodeError) as exc:
            raise ValueError("Sealed backup invalid, inaccessible or wrong key") from exc

    def restore(self, backup_path: str | Path, backup_key: bytes,
                destination: str | Path) -> RecoveryResult:
        """Offline restore to a NEW 0700 dir; keep original source intact."""
        revision, accounts, serialized = self._read_backup(
            Path(backup_path), backup_key, self.roster_name, self.db_name)
        memory, drafts = _decode_database(serialized, self.key)
        try:
            # Recovered cookie sessions may be compromised, always revoke.
            sessions = memory.execute("SELECT COUNT(*) FROM admin_sessions").fetchone()[0]
            memory.execute("DELETE FROM admin_sessions")
            memory.commit()
            return self._create_stage(Path(destination), accounts, revision, memory,
                                      self.key, drafts, sessions)
        finally:
            memory.close()

    def stage_rotation(self, destination: str | Path,
                       new_key: bytes) -> RecoveryResult:
        """Stage both encrypted stores under a new key without touching source.

        Requires all writers offline and a separately verified sealed backup.
        No automatic deployment/promotion or key-file write.
        """
        if secrets.compare_digest(self.key, new_key):
            raise ValueError("New key must differ from current key")
        new_cipher = Fernet(new_key)
        revision, accounts, serialized = self._snapshot()
        memory, drafts = _decode_database(serialized, self.key)
        try:
            sessions = memory.execute("SELECT COUNT(*) FROM admin_sessions").fetchone()[0]
            memory.execute("BEGIN IMMEDIATE")
            for revision_id, ciphertext in memory.execute(
                    "SELECT revision,content FROM draft_revisions").fetchall():
                plaintext = self.cipher.decrypt(ciphertext)
                memory.execute(
                    "UPDATE draft_revisions SET content=? WHERE revision=?",
                    (new_cipher.encrypt(plaintext), revision_id))
            memory.execute("DELETE FROM admin_sessions")
            memory.commit()
            if _validate_memory(memory, new_key) != drafts:
                raise ValueError("Key rotation verification failed")
            return self._create_stage(Path(destination), accounts, revision, memory,
                                      new_key, drafts, sessions)
        finally:
            memory.close()
