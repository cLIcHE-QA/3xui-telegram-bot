"""#887 D3e: isolated SQLite one-use proof ledger for one local filesystem.

No bearer subscription URLs, raw cookies, Telegram IDs or provider data are stored.
BEGIN IMMEDIATE serializes writers from distinct processes on *one host*; shared
NFS/multi-host deployments remain unsupported. Never use the bot production DB.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import sqlite3
import stat
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from urllib.parse import urlsplit

SCHEMA_VERSION = 1
MAX_PENDING = 128
MAX_RATE_ROWS = 2048
RATE_WINDOW = 60
ISSUE_LIMIT = 4
CONSUME_LIMIT = 8


class ImportSQLiteLedger:
    def __init__(self, db_path: str | os.PathLike[str], *, https_origin: str) -> None:
        url = urlsplit(https_origin)
        if (url.scheme != "https" or not url.netloc or not url.hostname
                or url.username or url.password or url.path or url.query
                or url.fragment or url.hostname.endswith(".") or
                https_origin != f"https://{url.netloc}"):
            raise ValueError("Canonical HTTPS origin required")
        self.https_origin = https_origin
        self.origin_hash = hashlib.sha256(https_origin.encode("utf-8")).digest()
        path = Path(db_path)
        if not path.is_absolute() or not path.name.endswith(".sqlite3"):
            raise ValueError("Separate absolute .sqlite3 path required")
        if not path.parent.is_dir() or path.parent.is_symlink():
            raise ValueError("Private directory required")
        parent = path.parent.stat()
        if (not stat.S_ISDIR(parent.st_mode) or parent.st_uid != os.getuid()
                or parent.st_mode & 0o077):
            raise ValueError("Owner-only directory required")
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_RDWR |
                         getattr(os, "O_NOFOLLOW", 0), 0o600)
        except FileExistsError:
            if not self._valid_file(path):
                raise ValueError("Unsafe import ledger") from None
        else:
            os.close(fd)
        self.path = path
        try:
            with self._connection() as conn:
                conn.execute("BEGIN IMMEDIATE")
                version = conn.execute("PRAGMA user_version").fetchone()[0]
                if version not in (0, SCHEMA_VERSION):
                    raise ValueError("Incompatible import ledger version")
                conn.execute("CREATE TABLE IF NOT EXISTS import_origin ("
                             "id INTEGER PRIMARY KEY CHECK(id=1), hash BLOB NOT NULL)")
                origin = conn.execute("SELECT hash FROM import_origin WHERE id=1").fetchone()
                if origin is None:
                    conn.execute("INSERT INTO import_origin(id,hash) VALUES(1,?)",
                                 (self.origin_hash,))
                elif not hmac.compare_digest(bytes(origin[0]), self.origin_hash):
                    raise ValueError("Import ledger origin mismatch")
                conn.execute("CREATE TABLE IF NOT EXISTS import_grants ("
                             "proof_hash BLOB PRIMARY KEY, owner_key BLOB NOT NULL,"
                             "session_key BLOB NOT NULL, mode TEXT NOT NULL,"
                             "issued REAL NOT NULL, expires REAL NOT NULL)")
                conn.execute("CREATE TABLE IF NOT EXISTS import_rates ("
                             "session_key BLOB NOT NULL, operation TEXT NOT NULL,"
                             "stamp REAL NOT NULL)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_import_rates ON "
                             "import_rates(session_key, operation, stamp)")
                conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
                check = conn.execute("PRAGMA quick_check").fetchone()
                if not check or check[0] != "ok":
                    raise ValueError("Import ledger integrity invalid")
                conn.execute("COMMIT")
        except sqlite3.Error:
            raise ValueError("Import ledger unavailable") from None

    @staticmethod
    def _valid_file(path: Path) -> bool:
        try:
            row = path.lstat()
        except OSError:
            return False
        return (stat.S_ISREG(row.st_mode) and row.st_uid == os.getuid()
                and row.st_nlink == 1 and not row.st_mode & 0o077)

    def _connection(self) -> sqlite3.Connection:
        if not self._valid_file(self.path):
            raise ValueError("Import ledger unavailable")
        conn = sqlite3.connect(str(self.path), timeout=2, isolation_level=None)
        conn.execute("PRAGMA busy_timeout=2000")
        conn.execute("PRAGMA synchronous=FULL")
        return conn

    @contextmanager
    def _transaction(self, current: float) -> Iterator[sqlite3.Connection]:
        conn: sqlite3.Connection | None = None
        try:
            conn = self._connection()
            conn.execute("BEGIN IMMEDIATE")
            record = conn.execute("SELECT hash FROM import_origin WHERE id=1").fetchone()
            if record is None or not hmac.compare_digest(bytes(record[0]), self.origin_hash):
                raise ValueError("Import ledger origin changed")
            conn.execute("DELETE FROM import_grants WHERE expires<=? OR issued>?",
                         (current, current))
            conn.execute("DELETE FROM import_rates WHERE stamp<=? OR stamp>?",
                         (current - RATE_WINDOW, current))
            yield conn
            conn.execute("COMMIT")
        except (sqlite3.Error, OSError, ValueError):
            if conn is not None:
                try:
                    conn.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
            raise ValueError("Import ledger unavailable") from None
        finally:
            if conn is not None:
                conn.close()

    @staticmethod
    def _digest(value: object) -> bool:
        return isinstance(value, bytes) and len(value) == 32

    def reserve(self, session_key: bytes, operation: str, *, current: float) -> bool:
        if not self._digest(session_key) or operation not in ("issue", "consume"):
            return False
        limit = ISSUE_LIMIT if operation == "issue" else CONSUME_LIMIT
        with self._transaction(current) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM import_rates WHERE session_key=? AND operation=?",
                (session_key, operation),
            ).fetchone()[0]
            if count >= limit or conn.execute("SELECT COUNT(*) FROM import_rates").fetchone()[0] >= MAX_RATE_ROWS:
                return False
            conn.execute("INSERT INTO import_rates(session_key,operation,stamp) VALUES(?,?,?)",
                         (session_key, operation, current))
            return True

    def issue(self, proof_hash: bytes, owner_key: bytes, session_key: bytes,
              mode: str, *, issued: float, expires: float) -> bool:
        if not all(map(self._digest, (proof_hash, owner_key, session_key))):
            return False
        if mode not in ("telegram-mini-app", "standalone") or not issued < expires <= issued + 60:
            return False
        with self._transaction(issued) as conn:
            if conn.execute("SELECT COUNT(*) FROM import_grants").fetchone()[0] >= MAX_PENDING:
                return False
            try:
                conn.execute("INSERT INTO import_grants(proof_hash,owner_key,session_key,mode,issued,expires)"
                             " VALUES(?,?,?,?,?,?)",
                             (proof_hash, owner_key, session_key, mode, issued, expires))
            except sqlite3.IntegrityError:
                return False
            return True

    def consume(self, proof_hash: bytes, owner_key: bytes, session_key: bytes,
                mode: str, *, current: float) -> bool:
        if not all(map(self._digest, (proof_hash, owner_key, session_key))):
            return False
        with self._transaction(current) as conn:
            row = conn.execute("SELECT owner_key,session_key,mode,issued,expires "
                               "FROM import_grants WHERE proof_hash=?", (proof_hash,)).fetchone()
            if row is None:
                return False
            # Burn known proof atomically even for a wrong owner/mode/session.
            conn.execute("DELETE FROM import_grants WHERE proof_hash=?", (proof_hash,))
            return (hmac.compare_digest(bytes(row[0]), owner_key)
                    and hmac.compare_digest(bytes(row[1]), session_key)
                    and row[2] == mode and row[3] <= current < row[4])
