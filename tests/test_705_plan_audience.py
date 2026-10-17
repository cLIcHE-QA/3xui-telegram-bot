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
        self.assertEqual(CURRENT_SCHEMA_VERSION, 15)
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

    async def test_group_member_add_remove_and_exclude_override(self):
        gid = await self.db.create_user_group(name="Выбранные")
        denied = await self.db.create_user_group(name="Запрет")
        pid = await self.db.create_plan(name="pilot", duration_days=30, traffic_gb=0,
                         ip_limit=0, price_minor=20000, currency="RUB", stars_price=30)
        await self.db.update_plan_catalog(pid, visibility="groups",
                                          include_group_ids=[gid], exclude_group_ids=[denied])
        with sqlite3.connect(self.path) as conn:
            conn.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?)",
                         (11001, "pilot@example.invalid", "sub-11001", 0, 123))
            conn.commit()
        self.assertIsNone(await self.svc.active_plan(pid, telegram_id=11001))
        await self.db.set_user_group_member(gid, 11001, True)
        self.assertIsNotNone(await self.svc.active_plan(pid, telegram_id=11001))
        await self.db.set_user_group_member(denied, 11001, True)
        self.assertIsNone(await self.svc.active_plan(pid, telegram_id=11001))
        await self.db.set_user_group_member(denied, 11001, False)
        self.assertIsNotNone(await self.svc.active_plan(pid, telegram_id=11001))
        await self.db.set_user_group_member(gid, 11001, False)
        self.assertIsNone(await self.svc.active_plan(pid, telegram_id=11001))

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

    async def test_four_price_combinations_and_purchase_channel(self):
        cases = [(20000, 0, True, False), (0, 50, False, True),
                 (20000, 50, True, True), (0, 0, False, False)]
        for i, (rub, stars, rub_enabled, purchase_stars) in enumerate(cases):
            pid = await self.db.create_plan(
                name=f"matrix-{i}", duration_days=30, traffic_gb=0, ip_limit=0,
                price_minor=rub, currency="RUB", stars_price=stars,
                rub_price_enabled=rub_enabled,
                visibility="all" if (rub or stars) else "admin_only",
            )
            plan = await self.db.get_plan(pid)
            self.assertEqual((plan.price_minor, plan.stars_price), (rub, stars))
            self.assertEqual(bool(plan.rub_price_enabled), rub_enabled)
            self.assertEqual(bool(await self.svc.active_plan(pid, telegram_id=55)),
                             purchase_stars)

    async def test_group_revocation_blocks_existing_order_precheckout(self):
        from db import UserRecord
        await self.db.put(UserRecord(telegram_id=55, email="user@example.invalid",
                                     sub_id="one", expiry_time=0, created_at=1))
        gid = await self.db.create_user_group(name="Пилот")
        await self.db.set_user_group_member(gid, 55, True)
        pid = await self.db.create_plan(
            name="pilot-paid", duration_days=30, traffic_gb=0, ip_limit=0,
            price_minor=0, currency="RUB", stars_price=40,
        )
        await self.db.update_plan_catalog(pid, visibility="groups", include_group_ids=[gid])
        plan = await self.db.get_plan(pid)
        order, _ = await self.svc.get_or_create_stars_order(telegram_id=55, plan=plan)
        await self.db.set_user_group_member(gid, 55, False)
        self.assertFalse(await self.svc.validate_stars_precheckout(
            telegram_id=55, order_id=order.id, amount=40,
        ))
        with sqlite3.connect(self.path) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM commerce_payments").fetchone()[0], 0)

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
