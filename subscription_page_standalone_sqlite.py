"""#887 D2b: separate, opt-in SQLite ledger for standalone one-time ownership.

Not the bot database: this ledger has its own private (0700) directory and 0600
file, schema/version and no enrolment, subscription IDs, credentials or keys.
SQLite BEGIN IMMEDIATE serializes operations of independent processes on one
local filesystem. Do NOT mount on shared NFS or deploy without operator review.
All stored challenge, binding and session identifiers are SHA-256 digests.
"""
from __future__ import annotations

import os
import secrets
import sqlite3
import stat
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from aiohttp import web

MAX_PENDING = 128
MAX_SESSIONS = 128
_SCHEMA_VERSION = 1


class StandaloneSQLiteLedger:
    def __init__(self, db_path: str | os.PathLike) -> None:
        path = Path(db_path)
        if not path.is_absolute() or not path.name.endswith(".sqlite3"):
            raise ValueError("A separate absolute .sqlite3 path is required")
        if not path.parent.is_dir() or path.parent.is_symlink():
            raise ValueError("A real private directory is required")
        parent = path.parent.stat()
        if (parent.st_uid != os.getuid() or parent.st_mode & 0o077
                or not stat.S_ISDIR(parent.st_mode)):
            raise ValueError("Owner-only 0700 directory is required")
        # Exclusive, no-follow creation prevents accidental reuse of files.
        flags = os.O_CREAT | os.O_EXCL | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(path, flags, 0o600)
        except FileExistsError:
            if not self._valid_file(path):
                raise ValueError("Unsafe standalone SQLite file") from None
        else:
            os.close(fd)
        self.path = path
        try:
            with self._connect() as con:
                con.execute("BEGIN IMMEDIATE")
                version = con.execute("PRAGMA user_version").fetchone()[0]
                if version not in (0, _SCHEMA_VERSION):
                    raise ValueError("Incompatible standalone ledger version")
                con.execute(
                    "CREATE TABLE IF NOT EXISTS standalone_pending ("
                    "challenge_hash BLOB PRIMARY KEY, binding_hash BLOB NOT NULL, "
                    "issued REAL NOT NULL, expires REAL NOT NULL, "
                    "owner INTEGER)"
                )
                con.execute(
                    "CREATE INDEX IF NOT EXISTS idx_standalone_pending_binding "
                    "ON standalone_pending(binding_hash)"
                )
                con.execute(
                    "CREATE TABLE IF NOT EXISTS standalone_sessions ("
                    "session_hash BLOB PRIMARY KEY, owner INTEGER NOT NULL, "
                    "expires REAL NOT NULL)"
                )
                con.execute("PRAGMA user_version=1")
                check = con.execute("PRAGMA quick_check").fetchone()
                if not check or check[0] != "ok":
                    raise ValueError("Standalone ledger integrity invalid")
                con.execute("COMMIT")
        except sqlite3.Error as exc:
            raise ValueError("Standalone ledger unavailable") from None

    @staticmethod
    def _valid_file(path: Path) -> bool:
        try:
            row = path.lstat()
        except OSError:
            return False
        return (
            stat.S_ISREG(row.st_mode)
            and row.st_uid == os.getuid()
            and not row.st_mode & 0o077
            and row.st_nlink == 1
        )

    def _connect(self) -> sqlite3.Connection:
        if not self._valid_file(self.path):
            raise OSError("Unsafe standalone ledger")
        con = sqlite3.connect(str(self.path), timeout=2, isolation_level=None)
        con.execute("PRAGMA busy_timeout=2000")
        con.execute("PRAGMA synchronous=FULL")
        return con

    @contextmanager
    def _tx(self, current: float) -> Iterator[sqlite3.Connection]:
        """Each read/write is serialized and checks expiry inside the lock."""
        con: sqlite3.Connection | None = None
        try:
            con = self._connect()
            con.execute("BEGIN IMMEDIATE")
            con.execute(
                "DELETE FROM standalone_pending WHERE expires <= ? OR issued > ?",
                (current, current),
            )
            con.execute(
                "DELETE FROM standalone_sessions WHERE expires <= ?",
                (current,),
            )
            yield con
            con.execute("COMMIT")
        except web.HTTPException:
            if con is not None:
                con.execute("ROLLBACK")
            raise
        except (sqlite3.Error, OSError, ValueError) as exc:
            if con is not None:
                try:
                    con.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
            raise web.HTTPServiceUnavailable(
                text="Standalone ledger unavailable"
            ) from None
        finally:
            if con is not None:
                con.close()

    def begin(
        self, challenge_hash: bytes, binding_hash: bytes, *,
        current: float, expires: float, old_binding: bytes | None,
        old_session_hash: bytes | None,
    ) -> bool:
        """Atomically replace pending browser challenge and revoke old session."""
        with self._tx(current) as con:
            if old_binding is not None:
                con.execute(
                    "DELETE FROM standalone_pending WHERE binding_hash=?",
                    (old_binding,),
                )
            if old_session_hash is not None:
                con.execute(
                    "DELETE FROM standalone_sessions WHERE session_hash=?",
                    (old_session_hash,),
                )
            if con.execute(
                "SELECT COUNT(*) FROM standalone_pending"
            ).fetchone()[0] >= MAX_PENDING:
                raise web.HTTPServiceUnavailable(text="Standalone capacity reached")
            try:
                con.execute(
                    "INSERT INTO standalone_pending("
                    "challenge_hash,binding_hash,issued,expires,owner)"
                    " VALUES(?,?,?,?,NULL)",
                    (challenge_hash, binding_hash, current, expires),
                )
            except sqlite3.IntegrityError:
                return False
            return True

    def pending(
        self, challenge_hash: bytes, *, current: float,
    ) -> tuple[bytes, int | None] | None:
        with self._tx(current) as con:
            row = con.execute(
                "SELECT binding_hash,owner FROM standalone_pending"
                " WHERE challenge_hash=?", (challenge_hash,),
            ).fetchone()
            return (bytes(row[0]), row[1]) if row is not None else None

    def approve(
        self, challenge_hash: bytes, owner: int, *, current: float,
    ) -> bool:
        with self._tx(current) as con:
            result = con.execute(
                "UPDATE standalone_pending SET owner=?"
                " WHERE challenge_hash=? AND owner IS NULL",
                (owner, challenge_hash),
            )
            return result.rowcount == 1

    def exchange(
        self, challenge_hash: bytes, binding_hash: bytes,
        owner: int, session_hash: bytes, *, current: float,
        session_ttl: int,
    ) -> bool:
        """Exactly one concurrent worker can consume a challenge and mint a cookie."""
        with self._tx(current) as con:
            row = con.execute(
                "SELECT binding_hash, owner FROM standalone_pending"
                " WHERE challenge_hash=?", (challenge_hash,),
            ).fetchone()
            if row is None or bytes(row[0]) != binding_hash or row[1] != owner:
                return False
            if con.execute(
                "SELECT COUNT(*) FROM standalone_sessions"
            ).fetchone()[0] >= MAX_SESSIONS:
                raise web.HTTPServiceUnavailable(text="Standalone capacity reached")
            con.execute(
                "DELETE FROM standalone_pending WHERE challenge_hash=?",
                (challenge_hash,),
            )
            con.execute(
                "INSERT INTO standalone_sessions(session_hash,owner,expires)"
                " VALUES(?,?,?)",
                (session_hash, owner, current + session_ttl),
            )
            return True

    def session_owner(self, session_hash: bytes, *, current: float) -> int | None:
        with self._tx(current) as con:
            row = con.execute(
                "SELECT owner FROM standalone_sessions WHERE session_hash=?",
                (session_hash,),
            ).fetchone()
            return row[0] if row is not None else None

    def revoke_session(self, session_hash: bytes, *, current: float) -> None:
        with self._tx(current) as con:
            con.execute(
                "DELETE FROM standalone_sessions WHERE session_hash=?",
                (session_hash,),
            )

    def cancel(self, challenge_hash: bytes, binding_hash: bytes, *,
               current: float) -> bool:
        with self._tx(current) as con:
            result = con.execute(
                "DELETE FROM standalone_pending"
                " WHERE challenge_hash=? AND binding_hash=?",
                (challenge_hash, binding_hash),
            )
            return result.rowcount == 1

    def logout(self, *, session_hash: bytes | None,
               binding_hash: bytes | None, current: float) -> None:
        with self._tx(current) as con:
            if session_hash is not None:
                con.execute(
                    "DELETE FROM standalone_sessions WHERE session_hash=?",
                    (session_hash,),
                )
            if binding_hash is not None:
                con.execute(
                    "DELETE FROM standalone_pending WHERE binding_hash=?",
                    (binding_hash,),
                )
