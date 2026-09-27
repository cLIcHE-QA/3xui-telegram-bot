from __future__ import annotations

import sqlite3
import tempfile
import time
import unittest
from pathlib import Path

from audience import audience_matches, audience_matches_group_ids
from db import Database, UserRecord
from db_migrations import CURRENT_SCHEMA_VERSION


class UserAudienceGroupsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "bot.sqlite3"
        self.db = Database(str(self.path))
        await self.db.init()
        now = int(time.time())
        await self.db.put(UserRecord(101, "ivan@example.com", "sub-101", 0, now))
        await self.db.put(UserRecord(202, "anna@example.com", "sub-202", 0, now + 1))
        await self.db.set_user_display_name(101, "Иван Петров")
        await self.db.set_user_display_name(202, "Анна")

    async def asyncTearDown(self):
        self.tmp.cleanup()

    async def test_schema_v3_contains_group_tables_and_index(self):
        self.assertEqual(CURRENT_SCHEMA_VERSION, 3)
        with sqlite3.connect(self.path) as conn:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            indexes = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='index'"
                ).fetchall()
            }
        self.assertIn("user_groups", tables)
        self.assertIn("user_group_members", tables)
        self.assertIn("idx_user_group_members_user", indexes)

    async def test_membership_is_many_to_many_and_bound_to_telegram_id(self):
        beta = await self.db.create_user_group(name="Beta", description="Тест")
        premium = await self.db.create_user_group(name="Premium")
        await self.db.set_user_group_member(beta, 101, True)
        await self.db.set_user_group_member(premium, 101, True)
        await self.db.set_user_group_member(beta, 202, True)

        self.assertEqual(
            await self.db.list_user_group_ids_for_user(101),
            {beta, premium},
        )
        self.assertEqual(
            await self.db.list_user_group_member_ids(beta),
            {101, 202},
        )

    async def test_search_supports_telegram_id_email_and_display_name(self):
        by_id = await self.db.search_users("101")
        by_email = await self.db.search_users("anna@example.com")
        by_name = await self.db.search_users("Петров")

        self.assertEqual([item.telegram_id for item in by_id], [101])
        self.assertEqual([item.telegram_id for item in by_email], [202])
        self.assertEqual([item.telegram_id for item in by_name], [101])

    async def test_delete_group_removes_membership_but_not_users(self):
        group_id = await self.db.create_user_group(name="Temporary")
        await self.db.set_user_group_member(group_id, 101, True)
        await self.db.delete_user_group(group_id)

        self.assertIsNone(await self.db.get_user_group(group_id))
        self.assertIsNotNone(await self.db.get(101))
        self.assertEqual(await self.db.list_user_group_ids_for_user(101), set())

    async def test_delete_user_cleans_memberships(self):
        group_id = await self.db.create_user_group(name="Cleanup")
        await self.db.set_user_group_member(group_id, 101, True)
        await self.db.delete(101)

        self.assertIsNone(await self.db.get(101))
        self.assertEqual(await self.db.list_user_group_member_ids(group_id), set())

    async def test_group_names_are_case_insensitive_unique(self):
        await self.db.create_user_group(name="Beta")
        with self.assertRaises(sqlite3.IntegrityError):
            await self.db.create_user_group(name="beta")

    async def test_audience_matcher_exclude_wins_and_empty_rules_allow(self):
        self.assertTrue(audience_matches_group_ids({1, 2}))
        self.assertTrue(
            audience_matches_group_ids({1, 2}, include_group_ids={2, 3})
        )
        self.assertFalse(
            audience_matches_group_ids({1, 2}, include_group_ids={3})
        )
        self.assertFalse(
            audience_matches_group_ids(
                {1, 2},
                include_group_ids={2},
                exclude_group_ids={1},
            )
        )

    async def test_async_matcher_uses_current_membership(self):
        allowed = await self.db.create_user_group(name="Allowed")
        denied = await self.db.create_user_group(name="Denied")
        await self.db.set_user_group_member(allowed, 101, True)

        self.assertTrue(
            await audience_matches(
                self.db,
                101,
                include_group_ids={allowed},
                exclude_group_ids={denied},
            )
        )
        await self.db.set_user_group_member(denied, 101, True)
        self.assertFalse(
            await audience_matches(
                self.db,
                101,
                include_group_ids={allowed},
                exclude_group_ids={denied},
            )
        )

    def test_admin_ui_keeps_audience_groups_separate_from_provisioning(self):
        source = (
            Path(__file__).resolve().parents[1] / "user_groups_admin.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("ProvisioningEngine", source)
        self.assertNotIn("set_user_server_group", source)
        self.assertIn("VPN-доступ не измен", source)
        self.assertIn('"user_group.member.add"', source)
        self.assertIn('"user_group.member.remove"', source)
        self.assertIn('"user_group.delete"', source)


if __name__ == "__main__":
    unittest.main()
