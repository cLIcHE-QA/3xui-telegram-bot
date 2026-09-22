"""Integrity checks for downloaded update rescue copies."""
from __future__ import annotations

from pathlib import Path
import sqlite3
import tempfile

from version_service import UpdateError


def validate_database(body: bytes, filename: str) -> None:
    if body.startswith(b"SQLite format 3\x00"):
        with tempfile.TemporaryDirectory(prefix="update-db-check-") as tmp:
            path = Path(tmp) / "check.sqlite3"
            path.write_bytes(body)
            try:
                with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
                    rows = connection.execute("PRAGMA quick_check").fetchall()
                if not rows or any(row[0] != "ok" for row in rows):
                    raise UpdateError("Downloaded SQLite backup failed quick_check.")
            except sqlite3.Error as exc:
                raise UpdateError("Downloaded SQLite backup is invalid.") from exc
        return
    # Format sanity only, not a claim that pg_restore has been rehearsed.
    if filename.lower().endswith(".dump") and len(body) >= 32 and body.startswith(b"PGDMP"):
        return
    raise UpdateError("Backup is not SQLite or a recognised PostgreSQL custom dump.")
