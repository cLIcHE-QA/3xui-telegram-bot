import sqlite3
import tempfile
import unittest
from pathlib import Path

from db import Database
from db_migrations import (
    CURRENT_SCHEMA_VERSION,
    DatabaseMigrationBackupError,
    DatabaseMigrationBlockedError,
    DatabaseMigrationError,
    DatabaseSchemaTooNewError,
    MigrationStep,
    current_schema_version,
    run_migrations,
)


class DatabaseMigrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_fresh_database_reaches_current_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bot.sqlite3"
            database = Database(str(path))

            await database.init()

            self.assertEqual(await current_schema_version(str(path)), CURRENT_SCHEMA_VERSION)
            with sqlite3.connect(path) as conn:
                row = conn.execute(
                    "SELECT version, name, status FROM schema_migrations ORDER BY version DESC LIMIT 1"
                ).fetchone()
                self.assertEqual(row, (1, "baseline_v4_14_2", "success"))
                self.assertEqual(conn.execute("PRAGMA quick_check").fetchone()[0], "ok")

    async def test_legacy_database_without_journal_is_upgraded_in_place(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bot.sqlite3"
            with sqlite3.connect(path) as conn:
                conn.execute(
                    """
                    CREATE TABLE users (
                        telegram_id INTEGER PRIMARY KEY,
                        email TEXT NOT NULL UNIQUE,
                        sub_id TEXT NOT NULL UNIQUE,
                        expiry_time INTEGER NOT NULL,
                        created_at INTEGER NOT NULL
                    )
                    """
                )
                conn.execute(
                    "INSERT INTO users VALUES (?, ?, ?, ?, ?)",
                    (123, "legacy@example.com", "legacy-sub", 456, 789),
                )
                conn.commit()

            await Database(str(path)).init()

            with sqlite3.connect(path) as conn:
                self.assertEqual(
                    conn.execute(
                        "SELECT telegram_id, email, sub_id, expiry_time, created_at FROM users"
                    ).fetchone(),
                    (123, "legacy@example.com", "legacy-sub", 456, 789),
                )
                tables = {
                    row[0]
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                }
                self.assertIn("payments", tables)
                self.assertIn("alert_rules", tables)
                self.assertIn("schema_migrations", tables)
                self.assertEqual(
                    conn.execute(
                        "SELECT status FROM schema_migrations WHERE version = 1"
                    ).fetchone()[0],
                    "success",
                )

    async def test_newer_schema_version_blocks_startup(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bot.sqlite3"
            await Database(str(path)).init()
            with sqlite3.connect(path) as conn:
                conn.execute(
                    """
                    INSERT INTO schema_migrations
                    (version, name, status, requires_backup, backup_path, started_at, finished_at, error)
                    VALUES (?, ?, 'success', 0, '', 1, 1, '')
                    """,
                    (CURRENT_SCHEMA_VERSION + 1, "future_schema"),
                )
                conn.commit()

            with self.assertRaises(DatabaseSchemaTooNewError):
                await Database(str(path)).init()

    async def test_failed_or_running_journal_blocks_replay(self):
        for status in ("running", "failed"):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "bot.sqlite3"
                with sqlite3.connect(path) as conn:
                    conn.execute(
                        """
                        CREATE TABLE schema_migrations (
                            version INTEGER PRIMARY KEY CHECK(version > 0),
                            name TEXT NOT NULL,
                            status TEXT NOT NULL CHECK(status IN ('running', 'success', 'failed')),
                            requires_backup INTEGER NOT NULL DEFAULT 0,
                            backup_path TEXT NOT NULL DEFAULT '',
                            started_at INTEGER NOT NULL,
                            finished_at INTEGER NOT NULL DEFAULT 0,
                            error TEXT NOT NULL DEFAULT ''
                        )
                        """
                    )
                    conn.execute(
                        """
                        INSERT INTO schema_migrations
                        (version, name, status, requires_backup, backup_path, started_at, finished_at, error)
                        VALUES (1, 'baseline_v4_14_2', ?, 0, '', 1, 0, 'previous attempt')
                        """,
                        (status,),
                    )
                    conn.commit()

                with self.assertRaises(DatabaseMigrationBlockedError):
                    await Database(str(path)).init()

                with sqlite3.connect(path) as conn:
                    users = conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
                    ).fetchone()
                    self.assertIsNone(users)

    async def test_dangerous_migration_requires_verified_recovery_copy(self):
        async def migration_1(db):
            await db.execute("CREATE TABLE marker(value TEXT NOT NULL)")
            await db.execute("INSERT INTO marker VALUES ('before')")

        async def migration_2(db):
            await db.execute("INSERT INTO marker VALUES ('after')")

        first = MigrationStep(1, "seed", migration_1)
        dangerous = MigrationStep(2, "dangerous_change", migration_2, requires_backup=True)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bot.sqlite3"
            await run_migrations(str(path), migrations=(first,))

            with self.assertRaises(DatabaseMigrationBackupError):
                await run_migrations(
                    str(path),
                    migrations=(first, dangerous),
                    backup_dir=None,
                )

            with sqlite3.connect(path) as conn:
                self.assertEqual(
                    conn.execute("SELECT value FROM marker ORDER BY rowid").fetchall(),
                    [("before",)],
                )
                self.assertIsNone(
                    conn.execute(
                        "SELECT status FROM schema_migrations WHERE version = 2"
                    ).fetchone()
                )

    async def test_failed_dangerous_migration_rolls_back_and_records_backup(self):
        async def migration_1(db):
            await db.execute("CREATE TABLE marker(value TEXT NOT NULL)")
            await db.execute("INSERT INTO marker VALUES ('before')")

        async def migration_2(db):
            await db.execute("INSERT INTO marker VALUES ('should_rollback')")
            raise RuntimeError("synthetic migration failure")

        steps = (
            MigrationStep(1, "seed", migration_1),
            MigrationStep(2, "dangerous_failure", migration_2, requires_backup=True),
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "bot.sqlite3"
            backup_dir = root / "migration-backups"

            with self.assertRaises(DatabaseMigrationError):
                await run_migrations(
                    str(path),
                    migrations=steps,
                    backup_dir=str(backup_dir),
                )

            with sqlite3.connect(path) as conn:
                self.assertEqual(
                    conn.execute("SELECT value FROM marker ORDER BY rowid").fetchall(),
                    [("before",)],
                )
                status, backup_path, error = conn.execute(
                    "SELECT status, backup_path, error FROM schema_migrations WHERE version = 2"
                ).fetchone()
                self.assertEqual(status, "failed")
                self.assertIn("synthetic migration failure", error)

            recovery = Path(backup_path)
            self.assertTrue(recovery.is_file())
            self.assertEqual(recovery.parent, backup_dir)
            with sqlite3.connect(f"file:{recovery.resolve()}?mode=ro", uri=True) as conn:
                self.assertEqual(conn.execute("PRAGMA quick_check").fetchone()[0], "ok")
                self.assertEqual(
                    conn.execute("SELECT value FROM marker ORDER BY rowid").fetchall(),
                    [("before",)],
                )

            with self.assertRaises(DatabaseMigrationBlockedError):
                await run_migrations(
                    str(path),
                    migrations=steps,
                    backup_dir=str(backup_dir),
                )


if __name__ == "__main__":
    unittest.main()
