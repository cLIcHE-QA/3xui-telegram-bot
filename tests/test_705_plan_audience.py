"""#705: миграция и защита платёжных entrypoints по аудитории."""
from __future__ import annotations
import sqlite3
import tempfile
import unittest
from pathlib import Path

from commerce import CommerceService
from customer_service import CustomerPortalService
from db import Database
from db_migrations import CURRENT_SCHEMA_VERSION, MIGRATIONS, run_migrations


class CatalogAudienceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / "bot.sqlite3")
        self.db = Database(self.path)
        await self.db.init()
        self.commerce = CommerceService(self.db)
        self.svc = CustomerPortalService(self.db, self.commerce, provider=None, subscription_url_template="https://example.invalid/{sub_id}")

    async def asyncTearDown(self):
        self.tmp.cleanup()

    async def test_additive_schema_and_default_legacy_visibility(self):
        self.assertEqual(CURRENT_SCHEMA_VERSION, 14)
        self.assertEqual(await self.db.create_plan(name="legacy", duration_days=30, traffic_gb=0,
                            ip_limit=0, price_minor=20000, currency="RUB", stars_price=30), 1)
        plan = await self.db.get_plan(1)
        self.assertEqual((plan.visibility, plan.rub_price_enabled), ("all", 1))
        self.assertEqual((plan.price_minor, plan.stars_price), (20000, 30))
        with sqlite3.connect(self.path) as conn:
            self.assertEqual(conn.execute("PRAGMA quick_check").fetchone()[0], "ok")

    async def test_groups_fail_closed_and_admin_only(self):
        gid = await self.db.create_user_group(name="Друзья")
        plan_id = await self.db.create_plan(name="limited", duration_days=30, traffic_gb=0,
                                ip_limit=0, price_minor=0, currency="RUB", stars_price=15)
        await self.db.update_plan_catalog(plan_id, visibility="groups", include_group_ids=[gid])
        self.assertIsNone(await self.svc.active_plan(plan_id, telegram_id=52))
        await self.db.update_plan_catalog(plan_id, visibility="admin_only")
        self.assertIsNone(await self.svc.active_plan(plan_id, telegram_id=52))
        await self.db.update_plan_catalog(plan_id, visibility="groups")
        await self.db.delete_user_group(gid)
        self.assertIsNone(await self.svc.active_plan(plan_id, telegram_id=52))
        with self.assertRaises(ValueError):
            await self.db.update_plan_catalog(plan_id, include_group_ids=[gid])

    async def test_no_public_invoice_for_rub_only_or_hidden(self):
        pid = await self.db.create_plan(name="rub-only", duration_days=30, traffic_gb=0,
                  ip_limit=0, price_minor=54000, currency="RUB", stars_price=0)
        plan = await self.db.get_plan(pid)
        self.assertIsNone(await self.svc.active_plan(pid, telegram_id=51))
        with self.assertRaises(ValueError):
            await self.svc.get_or_create_stars_order(telegram_id=51, plan=plan)
        await self.db.set_plan_stars_price(pid, 100)
        await self.db.update_plan_catalog(pid, visibility="admin_only")
        plan = await self.db.get_plan(pid)
        self.assertIsNone(await self.svc.active_plan(pid, telegram_id=51))
        with self.assertRaises(ValueError):
            await self.svc.get_or_create_stars_order(telegram_id=51, plan=plan)

    async def test_invalid_audience_rules_fail_closed(self):
        gid = await self.db.create_user_group(name="Группа")
        pid = await self.db.create_plan(name="protected", duration_days=30, traffic_gb=0,
                     ip_limit=0, price_minor=0, currency="RUB", stars_price=10)
        await self.db.update_plan_catalog(pid, visibility="groups", include_group_ids=[gid])
        with self.assertRaises(ValueError):
            await self.db.update_plan_catalog(pid, include_group_ids=[999999])
        with self.assertRaises(ValueError):
            await self.db.update_plan_catalog(pid, visibility="invalid")
        # Даже повреждённый JSON не делает hidden/groups тариф публичным.
        with sqlite3.connect(self.path) as conn:
            conn.execute("UPDATE plans SET include_group_ids=? WHERE id=?", ("[bad", pid))
            conn.commit()
        self.assertIsNone(await self.svc.active_plan(pid, telegram_id=51))

    async def test_no_free_stars_invoice(self):
        pid = await self.db.create_plan(name="manual", duration_days=0,
                     traffic_gb=0, ip_limit=0, price_minor=0, currency="RUB",
                     stars_price=0, rub_price_enabled=False, visibility="admin_only")
        plan = await self.db.get_plan(pid)
        self.assertEqual((plan.duration_days, plan.traffic_gb, plan.ip_limit), (0, 0, 0))
        with self.assertRaises(ValueError):
            await self.svc.get_or_create_stars_order(telegram_id=1, plan=plan)
        with self.assertRaises(ValueError):
            await self.db.create_plan(name="EUR",duration_days=30,traffic_gb=0,ip_limit=0,
                  price_minor=100,currency="EUR")

    async def test_upgrade_v13_preserves_snapshot(self):
        with tempfile.TemporaryDirectory() as temp:
            path = str(Path(temp) / "legacy.sqlite3")
            await run_migrations(path, migrations=MIGRATIONS[:13])
            with sqlite3.connect(path) as conn:
                conn.execute("INSERT INTO plans(name,duration_days,traffic_gb,ip_limit,price_minor,currency,active,created_at,stars_price) VALUES ('old',90,1,2,54000,'EUR',1,1,10)")
                conn.commit()
            await run_migrations(path)
            with sqlite3.connect(path) as conn:
                row=conn.execute("SELECT price_minor,currency,stars_price,visibility,rub_price_enabled FROM plans WHERE name='old'").fetchone()
                self.assertEqual(row,(54000,"EUR",10,"all",1))
                self.assertEqual(conn.execute("PRAGMA quick_check").fetchone()[0],"ok")


if __name__ == "__main__":
    unittest.main()
