from __future__ import annotations

from pathlib import Path
import unittest

from admin_privileges import required_role_for_callback


ROOT = Path(__file__).resolve().parents[1]


class V4250UserManagementFoundationTests(unittest.TestCase):
    def test_user_list_search_and_pagination_routes_are_registered(self):
        source = (ROOT / "advanced_users.py").read_text(encoding="utf-8")
        self.assertIn('USER_LIST_PAGE_SIZE = 12', source)
        self.assertIn('F.data.regexp(r"^admin:users:page:\\d+$")', source)
        self.assertIn('F.data == "admin:users:search"', source)
        self.assertIn('await db.search_users(query, limit=40)', source)
        self.assertEqual(required_role_for_callback("admin:users:search"), "read_only")
        self.assertEqual(required_role_for_callback("admin:users:noop"), "read_only")
        self.assertEqual(required_role_for_callback("admin:users:page:2"), "read_only")

    def test_user_list_actions_are_role_aware(self):
        source = (ROOT / "advanced_users.py").read_text(encoding="utf-8")
        self.assertIn('if role in {"support", "admin", "owner"}:', source)
        self.assertIn('callback_data="admin:users:bulk"', source)
        self.assertIn('callback_data="admin:provision:all:ask"', source)

    def test_legacy_attach_all_is_not_visible_or_mutating(self):
        source = (ROOT / "advanced_users.py").read_text(encoding="utf-8")
        self.assertNotIn(
            'InlineKeyboardButton(text="🔄 Синхронизировать всех", callback_data="admin:syncall:ask")',
            source,
        )
        self.assertNotIn(
            'InlineKeyboardButton(text="🔄 Синхронизировать Inbounds", callback_data=f"adminsync:{tg_id}")',
            source,
        )
        legacy_global = source.split(
            '@advanced_users_router.callback_query(F.data == "admin:syncall:ask")',
            1,
        )[1].split('@advanced_users_router.callback_query(F.data == "admin:stats")', 1)[0]
        self.assertNotIn("bulk_attach_clients", legacy_global)
        legacy_user = source.split(
            '@advanced_users_router.callback_query(F.data.startswith("adminsync:"))',
            1,
        )[1].split('@advanced_users_router.callback_query(F.data.startswith("adminextend:"))', 1)[0]
        self.assertNotIn("attach_client", legacy_user)
        self.assertNotIn("bulk_adjust_clients", legacy_user)
        self.assertIn("policy-based «Согласование»", legacy_user)

    def test_bulk_sync_is_replaced_by_safe_reconcile(self):
        source = (ROOT / "advanced_users.py").read_text(encoding="utf-8")
        self.assertIn('callback_data="admin:bulk:ask:reconcile"', source)
        self.assertIn('_bulk_confirmation_keyboard(f"admin:bulk:run:{action}")', source)
        self.assertIn(
            "await provisioner.provision_many(\n                [rec.telegram_id for rec in records],\n                strict=False,",
            source,
        )
        self.assertNotIn(
            'InlineKeyboardButton(text="📡 Синхронизировать Inbounds", callback_data="admin:bulk:run:sync")',
            source,
        )

    def test_bulk_audit_does_not_dump_user_emails(self):
        source = (ROOT / "advanced_users.py").read_text(encoding="utf-8")
        self.assertNotIn("emails={','.join(emails[:20])}", source)
        self.assertIn('details=f"users={len(records)}; {details}; unknown={len(unknown)}"', source)


if __name__ == "__main__":
    unittest.main()
