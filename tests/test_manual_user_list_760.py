"""#760: проверка read-only выборки живых ручных выдач на SQLite v15."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from db import Database, UserRecord


class ManualUserListTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(str(Path(self.tmp.name) / "bot.sqlite3"))
        await self.db.init()
        for tg_id in range(1, 29):
            await self.db.put(UserRecord(
                telegram_id=tg_id, email=f"person{tg_id}@example.invalid",
                sub_id=f"sample-{tg_id}", expiry_time=0, created_at=tg_id,
            ))
        # Existing ledger: тесту нужны только статус и владельцы, никаких real grants.
        with sqlite3.connect(self.db.path) as conn:
            for tg_id, status in (
                (1, "active"), (2, "unknown"), (3, "in_flight"),
                (4, "superseded"), (5, "failed"), (20, "active"),
                (27, "active"),
            ):
                conn.execute(
                    """INSERT INTO manual_entitlements
                       (telegram_id, plan_id, actor_id, status, started_at,
                        confirmed_at, updated_at, result_code)
                       VALUES (?, 1, 100, ?, 1, 1, 1, '')""",
                    (tg_id, status),
                )
            conn.commit()

    async def asyncTearDown(self):
        self.tmp.cleanup()

    async def test_filter_precedes_paging_and_ignores_legacy_rows(self):
        all_users = await self.db.list_users()
        self.assertEqual(len(all_users), 28)
        manual = await self.db.list_live_manual_users()
        self.assertEqual({u.telegram_id for u in manual}, {1, 2, 3, 20, 27})
        self.assertEqual([u.telegram_id for u in manual], [27, 20, 3, 2, 1])

    async def test_batch_status_lookup_and_unknown_handling(self):
        statuses = await self.db.manual_statuses_for_users(list(range(1, 29)))
        self.assertEqual(statuses, {
            1: "active", 2: "unknown", 3: "in_flight",
            20: "active", 27: "active",
        })
        self.assertEqual(await self.db.manual_statuses_for_users([]), {})
        self.assertEqual(await self.db.manual_statuses_for_users([1, 1, 4]), {1: "active"})
        self.assertEqual(await self.db.manual_statuses_for_users([999]), {})


if __name__ == "__main__":
    unittest.main()
