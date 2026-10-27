"""#947: source-only migration/drafts/candidate projection, no Telegram calls."""
import asyncio
import ast
from dataclasses import asdict
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

import aiosqlite

from audience import audience_matches_group_ids
from campaign_store import CampaignConflict, CampaignLimit, CampaignNotFound, CampaignOutcomeUnknown, CampaignUnavailable
from db import Database, UserRecord
from db_migrations import (
    DatabaseMigrationBlockedError, DatabaseMigrationError, DatabaseSchemaTooNewError,
    CURRENT_SCHEMA_VERSION, MIGRATIONS, MigrationStep, current_schema_version, run_migrations,
)
from service_campaigns import CampaignDenied, CampaignInvalid, ServiceCampaigns


class CampaignFoundation947Tests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "campaign.sqlite3"
        self.db = Database(str(self.path))
        await self.db.init()
        for actor in (1001, 1002):
            await self.db.put(UserRecord(actor, f"person-{actor}@example.invalid", f"private-sub-{actor}", 0, 1))
        self.auth = AsyncMock(side_effect=lambda actor: actor in {10, 20})
        self.api = ServiceCampaigns(self.db, authorize_owner=self.auth, clock=lambda: 1000)

    async def asyncTearDown(self):
        self.tmp.cleanup()

    async def draft(self, actor=10, **changes):
        values = dict(category="technical", subject="Технические работы", body="Плановое обслуживание сервиса")
        values.update(changes)
        return await self.api.create_draft(actor, **values)

    async def observe(self, actor=1001, **changes):
        values = dict(actor_id=actor, chat_id=actor, chat_type="private", is_bot=False)
        values.update(changes)
        return await self.api.observe_private_update(**values)

    async def test_default_authorization_denies_and_role_strings_do_not_grant_access(self):
        for api in (ServiceCampaigns(self.db), ServiceCampaigns(self.db, authorize_owner=AsyncMock(return_value="owner"))):
            with self.assertRaises(CampaignDenied):
                await api.list_drafts(10)
        with self.assertRaises(CampaignDenied):
            await self.draft(actor=1001)
        self.auth.side_effect = RuntimeError("private-authorization-details")
        with self.assertRaises(CampaignUnavailable) as error:
            await self.api.list_drafts(10)
        self.assertNotIn("private-authorization", str(error.exception))

    async def test_ownership_applies_to_every_draft_and_frozen_projection(self):
        draft = await self.draft()
        frozen = await self.api.freeze_draft(10, draft.id, expected_revision=1)
        for call in (
            self.api.get_draft(20, draft.id), self.api.get_revision(20, frozen.id),
            self.api.freeze_draft(20, draft.id, expected_revision=1),
            self.api.dry_run(20, draft.id, expected_revision=1),
            self.api.edit_draft(20, draft.id, expected_revision=1, category="technical", subject="Изменение", body="Новый текст"),
        ):
            with self.assertRaises(CampaignNotFound):
                await call
        self.assertEqual((await self.api.list_drafts(20)).total, 0)
        self.assertNotIn("owner_id", asdict(await self.api.get_draft(10, draft.id)))

    async def test_stale_concurrent_edits_and_freezes_are_atomic(self):
        draft = await self.draft()
        frozen = await asyncio.gather(*[self.api.freeze_draft(10, draft.id, expected_revision=1) for _ in range(2)])
        self.assertEqual(frozen[0], frozen[1])
        results = await asyncio.gather(*[
            self.api.edit_draft(10, draft.id, expected_revision=1, category="technical", subject="Изменение", body=body)
            for body in ("Первый вариант", "Второй вариант")
        ], return_exceptions=True)
        self.assertEqual(sum(isinstance(r, CampaignConflict) for r in results), 1)
        current = await self.api.get_draft(10, draft.id)
        self.assertEqual(current.revision, 2)
        old = await self.api.get_revision(10, frozen[0].id)
        self.assertEqual(old.content.body, draft.body)
        self.assertNotIn(draft.body, repr(old))
        self.assertNotIn(draft.subject, repr(current))
        with self.assertRaises(CampaignConflict):
            await self.api.dry_run(10, draft.id, expected_revision=1)
        with self.assertRaises(CampaignConflict):
            await self.api.freeze_draft(10, draft.id, expected_revision=1)
        with sqlite3.connect(self.path) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM service_campaign_revisions").fetchone()[0], 1)

    async def test_sqlite_revision_immutability_and_wrong_owner_are_enforced(self):
        draft = await self.draft()
        frozen = await self.api.freeze_draft(10, draft.id, expected_revision=1)
        for sql in ("UPDATE service_campaign_revisions SET owner_id=20 WHERE id=?",
                    "DELETE FROM service_campaign_revisions WHERE id=?"):
            with sqlite3.connect(self.path) as conn, self.assertRaises(sqlite3.IntegrityError):
                conn.execute(sql, (frozen.id,))
        with sqlite3.connect(self.path) as conn, self.assertRaises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO service_campaign_revisions(draft_id,owner_id,revision,payload_json,payload_sha256,created_at) "
                "VALUES (?,20,1,'{}',?,1000)", (draft.id, "0" * 64),
            )
        with sqlite3.connect(self.path) as conn, self.assertRaises(sqlite3.IntegrityError):
            conn.execute("UPDATE service_campaign_drafts SET owner_id=20 WHERE id=?", (draft.id,))

    async def test_clock_failure_and_negative_time_are_not_stored_or_exposed(self):
        for value in (0, -1, float('nan'), float('inf'), True):
            api = ServiceCampaigns(self.db, authorize_owner=self.auth, clock=lambda: value)
            with self.assertRaises(CampaignUnavailable):
                await api.create_draft(10, category="technical", subject="Работы", body="Обслуживание")
        api = ServiceCampaigns(self.db, authorize_owner=self.auth,
                               clock=lambda: (_ for _ in ()).throw(RuntimeError("private-clock-details")))
        with self.assertRaises(CampaignUnavailable) as error:
            await api.create_draft(10, category="technical", subject="Работы", body="Обслуживание")
        self.assertNotIn("private-clock-details", str(error.exception))
        self.assertEqual((await self.api.list_drafts(10)).total, 0)

    async def test_no_contact_backfill_and_private_binding_checks_without_ingress(self):
        draft = await self.draft()
        self.assertEqual((await self.api.dry_run(10, draft.id, expected_revision=1)).candidates, 0)
        for args in (dict(chat_type="group"), dict(chat_id=1002), dict(is_bot=True), dict(is_bot=None)):
            self.assertFalse(await self.observe(**args))
        self.assertFalse(await self.observe(actor=9999))
        self.assertIsNone(await self.db.get(9999))
        self.assertTrue(await self.observe())
        self.assertTrue(await self.observe())
        value = await self.api.dry_run(10, draft.id, expected_revision=1)
        self.assertEqual(value.candidates, 1)
        self.assertEqual(value.deliverable, 0)
        self.assertEqual(value.policy_status, "unapproved")
        with sqlite3.connect(self.path) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM service_campaign_contacts").fetchone()[0], 1)

    async def test_deleted_blocked_and_recreated_accounts_do_not_gain_candidates(self):
        draft = await self.draft()
        await self.observe()
        await self.observe(actor=1002)
        with sqlite3.connect(self.path) as conn:
            conn.execute("UPDATE service_campaign_contacts SET blocked_at=900 WHERE telegram_id=1002")
        await self.observe(actor=1002)  # Incoming observation never silently clears blocked state.
        await self.db.delete(1001)
        await self.db.put(UserRecord(1001, "new@example.invalid", "new-private-sub", 0, 2))
        result = await self.api.dry_run(10, draft.id, expected_revision=1)
        self.assertEqual(result.candidates, 0)
        with sqlite3.connect(self.path) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM service_campaign_contacts WHERE telegram_id=1001").fetchone()[0], 0)

    async def test_group_deny_semantics_match_canonical_audience_and_missing_group_fails_closed(self):
        group1 = await self.db.create_user_group(name="Первая")
        group2 = await self.db.create_user_group(name="Вторая")
        with sqlite3.connect(self.path) as conn:
            conn.execute("INSERT INTO user_group_members(group_id,telegram_id,created_at) VALUES (?,?,1)", (group1, 1001))
            conn.execute("INSERT INTO user_group_members(group_id,telegram_id,created_at) VALUES (?,?,1)", (group2, 1001))
            conn.execute("INSERT INTO user_group_members(group_id,telegram_id,created_at) VALUES (?,?,1)", (group1, 1002))
        await self.observe(); await self.observe(actor=1002)
        for include, exclude in (((), ()), ((group1,), ()), ((group2,), ()), ((group1,), (group2,)), ((), (group1,))):
            draft = await self.draft(include_groups=include, exclude_groups=exclude)
            estimate = await self.api.dry_run(10, draft.id, expected_revision=1)
            expected = sum(audience_matches_group_ids(groups, include_group_ids=include, exclude_group_ids=exclude)
                           for groups in ({group1, group2}, {group1}))
            self.assertEqual(estimate.candidates, expected)
        draft = await self.draft(include_groups=(group2,))
        await self.db.delete_user_group(group2)
        with self.assertRaises(CampaignUnavailable):
            await self.api.dry_run(10, draft.id, expected_revision=1)
        with self.assertRaises(CampaignUnavailable):
            await self.draft(include_groups=(99999,))

    async def test_large_candidate_count_is_capped_aggregated_and_read_only(self):
        with sqlite3.connect(self.path) as conn:
            conn.executemany("INSERT INTO users VALUES (?,?,?,?,?)", [
                (n, f"fixture-{n}@example.invalid", f"fixture-sub-{n}", 0, 1) for n in range(2000, 3200)
            ])
            conn.executemany("INSERT INTO service_campaign_contacts VALUES (?,1,1,'private_update',0)",
                             [(n,) for n in range(2000, 3200)])
        draft = await self.draft()
        before = self.path.read_bytes()
        result = await self.api.dry_run(10, draft.id, expected_revision=1)
        self.assertEqual((result.candidates, result.truncated, result.deliverable), (1000, True, 0))
        self.assertEqual(set(asdict(result)), {"revision", "candidates", "truncated", "deliverable", "policy_status"})
        self.assertEqual(self.path.read_bytes(), before)

    async def test_every_category_remains_unapproved_and_has_no_transport(self):
        await self.observe()
        for category in ("technical", "service", "tariff"):
            draft = await self.draft(category=category)
            estimate = await self.api.dry_run(10, draft.id, expected_revision=1)
            self.assertEqual((estimate.deliverable, estimate.policy_status), (0, "unapproved"))
        for method in ("send", "start", "schedule", "run_worker"):
            self.assertFalse(hasattr(self.api, method))
        root = Path(__file__).resolve().parents[1]
        for name in ("campaign_store.py", "service_campaigns.py"):
            tree = ast.parse((root / name).read_text())
            imports = {node.module.split('.')[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
            self.assertFalse(imports & {"aiogram", "aiohttp", "requests", "socket", "subprocess", "app_runtime"})

    async def test_pages_limits_and_invalid_identity_do_not_expand_work(self):
        for n in range(10):
            await self.draft(subject=f"Новость {n}")
        page = await self.api.list_drafts(10)
        self.assertEqual((page.page, page.total, len(page.items)), (0, 10, 8))
        self.assertFalse(hasattr(page.items[0], "body"))
        last = await self.api.list_drafts(10, page=10**40)
        self.assertEqual((last.page, len(last.items)), (1, 2))
        self.assertGreater(page.items[0].id, last.items[0].id)
        for value in (True, -1, 2**80, "10"):
            with self.assertRaises(CampaignInvalid):
                await self.api.get_draft(value, 1)
        with patch("campaign_store.MAX_DRAFTS", 10), self.assertRaises(CampaignLimit):
            await self.draft()
        draft = await self.draft(actor=20)
        await self.api.freeze_draft(20, draft.id, expected_revision=1)
        await self.api.edit_draft(20, draft.id, expected_revision=1, category="technical", subject="Изменение", body="Следующий текст")
        with patch("campaign_store.MAX_FROZEN_REVISIONS", 1), self.assertRaises(CampaignLimit):
            await self.api.freeze_draft(20, draft.id, expected_revision=2)

    async def test_control_markup_urls_and_credential_shapes_never_enter_storage(self):
        for body in ("<b>Новость</b>", "[текст](https://example.invalid)", "https://example.invalid/private",
                     "happ://private", "www.example.invalid", "t.me/example", "example.invalid/path",
                     "пример.рф", "mailto:test@example.invalid", "tg:resolve", "адрес 192.0.2.1",
                     "BOT_TOKEN=offline", "Bearer opaque", "A" * 40, "новость\u202e", "новость\x00"):
            with self.subTest(body=body), self.assertRaises(CampaignInvalid) as error:
                await self.draft(body=body)
            self.assertNotIn(body, str(error.exception))
        for changes in (dict(category="promo"), dict(body=""), dict(body="x " * 1800),
                        dict(subject="x" * 121), dict(include_groups=(True,)), dict(include_groups=tuple(range(1, 52)))):
            with self.assertRaises(CampaignInvalid):
                await self.draft(**changes)
        self.assertEqual((await self.api.list_drafts(10)).total, 0)

    async def test_lost_commit_result_is_unknown_and_owner_readback_recovers(self):
        original = aiosqlite.Connection.commit
        async def uncertain(conn):
            await original(conn)
            raise aiosqlite.OperationalError("private-commit-detail")
        with patch.object(aiosqlite.Connection, "commit", uncertain):
            with self.assertRaises(CampaignOutcomeUnknown) as error:
                await self.draft()
        self.assertNotIn("private-commit", str(error.exception))
        # No automatic replay: the first mutation actually committed once.
        page = await self.api.list_drafts(10)
        self.assertEqual(page.total, 1)

    async def test_failed_future_journal_entry_blocks_api_without_startup_bypass(self):
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            row = dict(conn.execute("SELECT * FROM schema_migrations WHERE version=16").fetchone())
            row.update(version=CURRENT_SCHEMA_VERSION + 1, name="future_fixture", status="failed")
            conn.execute(f"INSERT INTO schema_migrations({','.join(row)}) VALUES ({','.join('?' for _ in row)})", tuple(row.values()))
        with self.assertRaises(CampaignUnavailable):
            await self.api.list_drafts(10)

    async def test_corrupt_payload_and_missing_database_fail_closed_without_creation(self):
        draft = await self.draft()
        for raw in ("{}", "[" * 1200 + "0" + "]" * 1200):
            with sqlite3.connect(self.path) as conn:
                conn.execute("UPDATE service_campaign_drafts SET payload_json=? WHERE id=?", (raw, draft.id))
            for action in (self.api.get_draft(10, draft.id), self.api.freeze_draft(10, draft.id, expected_revision=1)):
                with self.assertRaises(CampaignUnavailable):
                    await action
        absent = Path(self.tmp.name) / "absent.sqlite3"
        api = ServiceCampaigns(Database(str(absent)), authorize_owner=self.auth)
        with self.assertRaises(CampaignUnavailable):
            await api.list_drafts(10)
        self.assertFalse(absent.exists())


class CampaignMigration947Tests(unittest.IsolatedAsyncioTestCase):
    async def test_v15_upgrade_preserves_data_and_creates_empty_ledgers_idempotently(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "legacy.sqlite3")
            await run_migrations(path, migrations=MIGRATIONS[:15])
            db = Database(path)
            await db.put(UserRecord(1001, "legacy@example.invalid", "private-legacy-sub", 12345, 1))
            denied = ServiceCampaigns(db, authorize_owner=AsyncMock(return_value=True))
            with self.assertRaises(CampaignUnavailable):
                await denied.list_drafts(10)
            await run_migrations(path, migrations=MIGRATIONS[:16])
            await run_migrations(path, migrations=MIGRATIONS[:16])
            self.assertEqual(await current_schema_version(path), 16)
            self.assertEqual((await db.get(1001)).expiry_time, 12345)
            with sqlite3.connect(path) as conn:
                for table in ("service_campaign_drafts", "service_campaign_revisions", "service_campaign_contacts"):
                    self.assertEqual(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], 0)
                self.assertEqual(conn.execute("PRAGMA quick_check").fetchone()[0], "ok")
            with self.assertRaises(DatabaseSchemaTooNewError):
                await run_migrations(path, migrations=MIGRATIONS[:15])

    async def test_failed_v16_rolls_back_ddl_and_preserves_user_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "failure.sqlite3")
            await run_migrations(path, migrations=MIGRATIONS[:15])
            await Database(path).put(UserRecord(1001, "legacy@example.invalid", "legacy-sub", 123, 1))
            async def broken(conn):
                await MIGRATIONS[15].apply(conn)
                raise RuntimeError("synthetic rollback")
            steps = (*MIGRATIONS[:15], MigrationStep(16, MIGRATIONS[15].name, broken))
            with self.assertRaises(DatabaseMigrationError):
                await run_migrations(path, migrations=steps)
            with sqlite3.connect(path) as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE name LIKE 'service_campaign_%'").fetchone()[0], 0)
                self.assertEqual(conn.execute("SELECT expiry_time FROM users").fetchone()[0], 123)
                self.assertEqual(conn.execute("SELECT status FROM schema_migrations WHERE version=16").fetchone()[0], "failed")
            with self.assertRaises(DatabaseMigrationBlockedError):
                await run_migrations(path)

    async def test_missing_or_tampered_immutability_objects_block_startup(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "damage.sqlite3")
            await Database(path).init()
            with sqlite3.connect(path) as conn:
                conn.execute("DROP TRIGGER service_campaign_revision_no_update")
            with self.assertRaisesRegex(DatabaseMigrationError, "Campaign schema mismatch"):
                await Database(path).init()

    async def test_unjournaled_contact_table_is_never_adopted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "unjournaled.sqlite3")
            await run_migrations(path, migrations=MIGRATIONS[:15])
            with sqlite3.connect(path) as conn:
                conn.execute("CREATE TABLE service_campaign_contacts(telegram_id INTEGER)")
                conn.execute("INSERT INTO service_campaign_contacts VALUES (1001)")
            with self.assertRaisesRegex(DatabaseMigrationError, "Unjournaled campaign"):
                await Database(path).init()


if __name__ == "__main__":
    unittest.main()
