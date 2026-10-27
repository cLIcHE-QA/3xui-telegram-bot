import sqlite3
import tempfile
from pathlib import Path
import unittest

from campaign_queue_schema import QUEUE_SCHEMA
from db import Database, UserRecord
from db_migrations import (
    DatabaseMigrationBlockedError, DatabaseMigrationError, DatabaseSchemaTooNewError,
    MIGRATIONS, MigrationStep, current_schema_version, run_migrations,
)


class CampaignQueueMigration948Tests(unittest.IsolatedAsyncioTestCase):
    async def legacy(self, path):
        await run_migrations(path, migrations=MIGRATIONS[:16])
        db = Database(path)
        for actor in (1001, 1002):
            await db.put(UserRecord(actor, f"legacy-{actor}@example.invalid", f"fixture-{actor}", 123, 1))
        # A synthetic pre-existing v16 proof, never evidence about a real chat.
        with sqlite3.connect(path) as conn:
            conn.execute("INSERT INTO service_campaign_contacts VALUES (1001,1,1,'private_update',0)")

    async def test_v16_to_v17_preserves_data_and_only_generates_existing_private_proofs(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "legacy.sqlite3")
            await self.legacy(path)
            await Database(path).init()
            with sqlite3.connect(path) as conn:
                proof = conn.execute("SELECT telegram_id,generation FROM service_campaign_contact_generations").fetchall()
                self.assertEqual(len(proof), 1)
                self.assertEqual(proof[0][0], 1001)
                self.assertEqual(len(proof[0][1]), 32)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM users").fetchone()[0], 2)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM service_campaign_jobs").fetchone()[0], 0)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM service_campaign_attempts").fetchone()[0], 0)
                self.assertEqual(conn.execute("PRAGMA quick_check").fetchone()[0], "ok")
            await Database(path).init()
            with sqlite3.connect(path) as conn:
                self.assertEqual(conn.execute("SELECT telegram_id,generation FROM service_campaign_contact_generations").fetchall(), proof)
            self.assertEqual(await current_schema_version(path), 17)
            with self.assertRaises(DatabaseSchemaTooNewError):
                await run_migrations(path, migrations=MIGRATIONS[:16])

    async def test_failed_v17_rolls_back_every_new_object_and_never_replays(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "failed.sqlite3")
            await self.legacy(path)
            async def broken(conn):
                await MIGRATIONS[16].apply(conn)
                raise RuntimeError("synthetic queue migration failure")
            steps = (*MIGRATIONS[:16], MigrationStep(17, MIGRATIONS[16].name, broken))
            with self.assertRaises(DatabaseMigrationError):
                await run_migrations(path, migrations=steps)
            with sqlite3.connect(path) as conn:
                for name in QUEUE_SCHEMA:
                    self.assertIsNone(conn.execute("SELECT 1 FROM sqlite_master WHERE name=?", (name,)).fetchone())
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM users").fetchone()[0], 2)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM service_campaign_contacts").fetchone()[0], 1)
                self.assertEqual(conn.execute("SELECT status FROM schema_migrations WHERE version=17").fetchone()[0], "failed")
            with self.assertRaises(DatabaseMigrationBlockedError):
                await Database(path).init()

    async def test_missing_or_tampered_queue_trigger_blocks_startup(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "tampered.sqlite3")
            await Database(path).init()
            with sqlite3.connect(path) as conn:
                conn.execute("DROP TRIGGER service_campaign_recipients_identity")
            with self.assertRaisesRegex(DatabaseMigrationError, "Campaign delivery schema mismatch"):
                await Database(path).init()

    async def test_missing_control_row_is_not_automatically_recreated(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "control.sqlite3")
            await Database(path).init()
            with sqlite3.connect(path) as conn:
                conn.execute("DROP TRIGGER service_campaign_control_no_delete")
                conn.execute("DELETE FROM service_campaign_control")
                conn.execute(QUEUE_SCHEMA["service_campaign_control_no_delete"])
            with self.assertRaisesRegex(DatabaseMigrationError, "Campaign delivery schema mismatch"):
                await Database(path).init()

    async def test_unjournaled_queue_is_never_adopted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "unjournaled.sqlite3")
            await self.legacy(path)
            with sqlite3.connect(path) as conn:
                conn.execute("CREATE TABLE service_campaign_jobs(id INTEGER)")
            with self.assertRaisesRegex(DatabaseMigrationError, "Unjournaled campaign delivery"):
                await Database(path).init()
            with sqlite3.connect(path) as conn:
                self.assertEqual(conn.execute("PRAGMA table_info(service_campaign_jobs)").fetchall()[0][1], "id")
                self.assertIsNone(conn.execute("SELECT 1 FROM sqlite_master WHERE name='service_campaign_control'").fetchone())

    async def test_missing_proof_generation_is_not_backfilled_during_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "proof.sqlite3")
            await self.legacy(path)
            await Database(path).init()
            with sqlite3.connect(path) as conn:
                conn.execute("DELETE FROM service_campaign_contact_generations")
            with self.assertRaisesRegex(DatabaseMigrationError, "Campaign delivery schema mismatch"):
                await Database(path).init()
