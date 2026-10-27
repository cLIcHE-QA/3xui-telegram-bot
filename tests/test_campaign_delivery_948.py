import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from dataclasses import asdict
import sqlite3
import tempfile
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, patch
import uuid

import aiosqlite

from db import Database, UserRecord
from service_campaign_delivery import CampaignDelivery, CampaignEnvelope, CampaignReply, CampaignWorker
from campaign_store import CampaignConflict, CampaignLimit, CampaignNotFound, CampaignOutcomeUnknown, CampaignUnavailable
from service_campaigns import CampaignDenied, CampaignInvalid


class FakeClock:
    def __init__(self):
        self.value = int(datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp())
    def __call__(self):
        return self.value
    def advance(self, seconds):
        self.value += seconds
    def future(self, seconds=60):
        return datetime.fromtimestamp(self.value + seconds, timezone.utc).strftime("%Y-%m-%dT%H:%M")


class FakePolicy:
    def __init__(self):
        self.category = True
        self.denied = set()
    async def allow_category(self, category):
        return self.category
    async def allow_recipient(self, category, telegram_id):
        return telegram_id not in self.denied


class FakeTransport:
    def __init__(self, replies=()):
        self.calls = []
        self.replies = list(replies)
    async def send(self, envelope):
        self.calls.append(envelope)
        if self.replies:
            value = self.replies.pop(0)
            if isinstance(value, Exception):
                raise value
            return value
        return CampaignReply("confirmed", envelope.chat_id, 1)


class CampaignDelivery948Tests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / "synthetic.sqlite3")
        self.db = Database(self.path)
        await self.db.init()
        self.clock = FakeClock()
        self.policy = FakePolicy()
        self.owner = AsyncMock(side_effect=lambda actor: actor in {10, 20})
        self.api = CampaignDelivery(self.db, authorize_owner=self.owner, policy=self.policy,
                                    enabled=True, clock=self.clock)
        for user in (1001, 1002):
            await self.db.put(UserRecord(user, f"user{user}@example.invalid", f"fixture-sub-{user}", 12345, 1))
        await self.observe(1001)

    async def asyncTearDown(self):
        self.tmp.cleanup()

    async def observe(self, actor):
        await self.api.observe_private_update(actor_id=actor, chat_id=actor, chat_type="private", is_bot=False)

    async def prepared(self, *, actor=10, operation=None, **changes):
        draft = await self.api.create_draft(actor, category="technical", subject="Обслуживание",
                                            body="Сервисное сообщение", **changes)
        frozen = await self.api.freeze_draft(actor, draft.id, expected_revision=1)
        job = await self.api.prepare_job(actor, frozen.id, operation_id=operation or str(uuid.uuid4()),
                                         local_time=self.clock.future(), timezone="UTC")
        return job

    async def scheduled(self, **changes):
        job = await self.prepared(**changes)
        return await self.api.confirm_job(10, job.id, expected_snapshot=job.snapshot_sha256)

    def rows(self, sql, params=()):
        with sqlite3.connect(self.path) as conn:
            return conn.execute(sql, params).fetchall()

    async def test_defaults_and_unapproved_policy_never_create_jobs_or_send(self):
        draft = await self.api.create_draft(10, category="service", subject="Новость", body="Обновление бота")
        frozen = await self.api.freeze_draft(10, draft.id, expected_revision=1)
        for kwargs in ({}, {"enabled": True}, {"policy": self.policy}, {"enabled": "true", "policy": self.policy}):
            service = CampaignDelivery(self.db, authorize_owner=self.owner, clock=self.clock, **kwargs)
            with self.assertRaises(CampaignDenied):
                await service.prepare_job(10, frozen.id, operation_id=str(uuid.uuid4()),
                                          local_time=self.clock.future(), timezone="UTC")
            worker = CampaignWorker(service, transport=FakeTransport())
            with patch.object(service._queue, "claim", side_effect=AssertionError("default off must not access queue")):
                self.assertIsNone(await worker.tick())
        self.assertEqual(self.rows("SELECT COUNT(*) FROM service_campaign_jobs"), [(0,)])

    async def test_one_durable_send_after_due_and_double_confirm_has_one_snapshot(self):
        job = await self.prepared()
        a, b = await asyncio.gather(*[self.api.confirm_job(10, job.id, expected_snapshot=job.snapshot_sha256) for _ in range(2)])
        self.assertEqual(a.id, b.id)
        transport = FakeTransport()
        worker = CampaignWorker(self.api, transport=transport)
        self.assertIsNone(await worker.tick())
        self.clock.advance(60)
        result = await worker.tick()
        self.assertEqual(result.state, "completed")
        self.assertEqual(dict(result.counts)["sent"], 1)
        self.assertEqual(len(transport.calls), 1)
        self.assertIsNone(transport.calls[0].parse_mode)
        self.assertFalse(transport.calls[0].link_preview)
        self.assertEqual(self.rows("SELECT state,attempt_no FROM service_campaign_attempts"), [("sent", 1)])
        self.assertEqual(self.rows("SELECT COUNT(*) FROM service_campaign_recipients"), [(1,)])
        self.assertIsNone(await worker.tick())

    async def test_operation_idempotency_and_ownership_cover_all_job_controls(self):
        job = await self.prepared()
        again = await self.api.prepare_job(10, job.revision_id, operation_id=job.operation_id,
                                           local_time=job.local_time, timezone=job.timezone)
        self.assertEqual(job, again)
        with self.assertRaises(CampaignConflict):
            await self.api.prepare_job(10, job.revision_id, operation_id=job.operation_id,
                                       local_time=self.clock.future(120), timezone="UTC")
        for call in (self.api.get_job(20, job.id), self.api.confirm_job(20, job.id, expected_snapshot=job.snapshot_sha256),
                     self.api.pause_job(20, job.id), self.api.cancel_job(20, job.id),
                     self.api.resume_job(20, job.id, local_time=self.clock.future(), timezone="UTC")):
            with self.assertRaises(CampaignNotFound):
                await call
        self.assertEqual((await self.api.list_jobs(20)).total, 0)

    async def test_network_unknown_stops_worker_and_never_replays_after_manual_resume(self):
        job = await self.scheduled()
        transport = FakeTransport([OSError("private-transport-details")])
        worker = CampaignWorker(self.api, transport=transport)
        self.clock.advance(60)
        result = await worker.tick()
        self.assertEqual((result.state, dict(result.counts)["unknown"]), ("paused", 1))
        self.assertIsNone(await worker.tick())
        await self.api.resume_job(10, job.id, local_time=self.clock.future(), timezone="UTC")
        self.clock.advance(60)
        other_transport = FakeTransport()
        other = CampaignWorker(self.api, transport=other_transport)
        result = await other.tick()
        self.assertEqual(result.state, "partial")
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(other_transport.calls, [])

    async def test_generation_bound_snapshot_rejects_deleted_recreated_user(self):
        job = await self.scheduled()
        await self.db.delete(1001)
        await self.db.put(UserRecord(1001, "recreated@example.invalid", "fixture-recreated", 12345, 1))
        await self.observe(1001)
        transport = FakeTransport()
        self.clock.advance(60)
        result = await CampaignWorker(self.api, transport=transport).tick()
        self.assertEqual(result.state, "partial")
        self.assertEqual(dict(result.counts)["skipped"], 1)
        self.assertEqual(transport.calls, [])

    async def test_safe_429_retry_uses_separate_budget_and_bounded_attempts(self):
        await self.scheduled()
        transport = FakeTransport([CampaignReply("rate_limited", 1001, retry_after=1)])
        worker = CampaignWorker(self.api, transport=transport)
        self.clock.advance(60)
        result = await worker.tick()
        self.assertEqual(result.state, "scheduled")
        self.assertIsNone(await worker.tick())
        self.clock.advance(1)
        self.assertIsNone(await worker.tick())
        self.clock.advance(1)
        result = await worker.tick()
        self.assertEqual(result.state, "completed")
        self.assertEqual(len(transport.calls), 2)
        self.assertEqual(self.rows("SELECT state FROM service_campaign_attempts ORDER BY id"), [("rate_limited",), ("sent",)])

    async def test_403_is_terminal_and_private_observation_does_not_unblock(self):
        await self.scheduled()
        transport = FakeTransport([CampaignReply("unavailable", 1001, reason="blocked")])
        self.clock.advance(60)
        result = await CampaignWorker(self.api, transport=transport).tick()
        self.assertEqual(result.state, "partial")
        self.assertEqual(dict(result.counts)["unavailable"], 1)
        await self.observe(1001)
        self.assertGreater(self.rows("SELECT blocked_at FROM service_campaign_contacts")[0][0], 0)
        self.assertEqual(len(transport.calls), 1)

    async def test_concurrent_workers_only_one_can_dispatch(self):
        await self.scheduled()
        a, b = FakeTransport(), FakeTransport()
        workers = (CampaignWorker(self.api, transport=a), CampaignWorker(self.api, transport=b))
        self.clock.advance(60)
        await asyncio.gather(*(worker.tick() for worker in workers))
        self.assertEqual(len(a.calls) + len(b.calls), 1)
        self.assertEqual(self.rows("SELECT COUNT(*) FROM service_campaign_attempts"), [(1,)])

    async def test_restart_recovers_durable_intent_as_unknown_without_dispatch(self):
        job = await self.scheduled()
        self.clock.advance(60)
        token = uuid.uuid4().hex
        await self.api._queue.claim(token, self.clock())
        intent = await self.api._queue.begin_intent(token, job.id, (), (), self.clock())
        self.assertIsNotNone(intent)
        self.clock.advance(31)
        transport = FakeTransport()
        self.assertIsNone(await CampaignWorker(self.api, transport=transport).tick())
        view = await self.api.get_job(10, job.id)
        self.assertEqual((view.state, dict(view.counts)["unknown"]), ("paused", 1))
        self.assertEqual(transport.calls, [])

    async def test_lost_lease_after_response_is_unknown_not_safe_failure(self):
        job = await self.scheduled()
        transport = FakeTransport()
        original = transport.send
        async def delayed(envelope):
            self.clock.advance(31)
            return await original(envelope)
        transport.send = delayed
        self.clock.advance(60)
        with self.assertRaises(CampaignOutcomeUnknown):
            await CampaignWorker(self.api, transport=transport).tick()
        self.assertEqual(len(transport.calls), 1)
        view = await self.api.get_job(10, job.id)
        self.assertEqual(dict(view.counts)["unknown"], 1)
        self.assertEqual(self.rows("SELECT state FROM service_campaign_attempts"), [("unknown",)])

    async def test_unknown_commit_before_transport_never_calls_adapter(self):
        job = await self.scheduled()
        transport = FakeTransport()
        original = aiosqlite.Connection.commit
        raised = False
        async def uncertain(conn):
            nonlocal raised
            await original(conn)
            cur = await conn.execute("SELECT COUNT(*) FROM service_campaign_attempts")
            if (await cur.fetchone())[0] and not raised:
                raised = True
                raise aiosqlite.OperationalError("private-commit-detail")
        self.clock.advance(60)
        with patch.object(aiosqlite.Connection, "commit", uncertain), self.assertRaises(CampaignOutcomeUnknown) as error:
            await CampaignWorker(self.api, transport=transport).tick()
        self.assertNotIn("private-commit", str(error.exception))
        self.assertEqual(transport.calls, [])
        self.assertEqual(dict((await self.api.get_job(10, job.id)).counts)["unknown"], 1)

    async def test_cancel_during_inflight_preserves_receipt_and_stops_remaining(self):
        await self.observe(1002)
        job = await self.scheduled()
        entered, release = asyncio.Event(), asyncio.Event()
        transport = FakeTransport()
        original = transport.send
        async def held(envelope):
            entered.set()
            await release.wait()
            return await original(envelope)
        transport.send = held
        worker = CampaignWorker(self.api, transport=transport)
        self.clock.advance(60)
        running = asyncio.create_task(worker.tick())
        await asyncio.wait_for(entered.wait(), 1)
        await self.api.cancel_job(10, job.id)
        release.set()
        result = await asyncio.wait_for(running, 1)
        self.assertEqual(result.state, "cancelled")
        self.assertEqual((dict(result.counts)["sent"], dict(result.counts)["cancelled"]), (1, 1))
        self.assertIsNone(await worker.tick())
        self.assertEqual(len(transport.calls), 1)

    async def test_graceful_close_waits_for_current_attempt_then_pauses_rest(self):
        await self.observe(1002)
        job = await self.scheduled()
        entered, release = asyncio.Event(), asyncio.Event()
        transport = FakeTransport()
        original = transport.send
        async def held(envelope):
            entered.set()
            await release.wait()
            return await original(envelope)
        transport.send = held
        worker = CampaignWorker(self.api, transport=transport)
        self.clock.advance(60)
        running = asyncio.create_task(worker.tick())
        await asyncio.wait_for(entered.wait(), 1)
        closing = asyncio.create_task(worker.close())
        await asyncio.sleep(0)
        release.set()
        await asyncio.wait_for(running, 1)
        self.assertTrue(await asyncio.wait_for(closing, 1))
        view = await self.api.get_job(10, job.id)
        self.assertEqual((view.state, dict(view.counts)["sent"], dict(view.counts)["pending"]), ("paused", 1, 1))
        self.assertIsNone(await worker.tick())
        self.assertEqual(len(transport.calls), 1)

    async def test_noncooperative_transport_timeout_is_bounded_unknown_and_not_rolled_back(self):
        job = await self.scheduled()
        release = asyncio.Event()
        transport = FakeTransport()
        original = transport.send
        async def ignores_first_cancel(envelope):
            try:
                await release.wait()
            except asyncio.CancelledError:
                await release.wait()
            return await original(envelope)
        transport.send = ignores_first_cancel
        worker = CampaignWorker(self.api, transport=transport)
        self.clock.advance(60)
        with patch("service_campaign_delivery.TRANSPORT_TIMEOUT", 0.01):
            result = await asyncio.wait_for(worker.tick(), 1)
        self.assertEqual((result.state, dict(result.counts)["unknown"]), ("paused", 1))
        self.assertFalse(await worker.close())
        release.set()
        for _ in range(10):
            await asyncio.sleep(0)
            if not worker._pending:
                break
        self.assertTrue(await worker.close())
        self.assertEqual(self.rows("SELECT state FROM service_campaign_attempts"), [("unknown",)])
        self.assertEqual(dict((await self.api.get_job(10, job.id)).counts)["sent"], 0)

    async def test_repeated_safe_429_exhausts_three_intents_without_replay(self):
        await self.scheduled()
        transport = FakeTransport([CampaignReply("rate_limited", 1001, retry_after=1)] * 3)
        worker = CampaignWorker(self.api, transport=transport)
        self.clock.advance(60)
        await worker.tick()
        self.clock.advance(2)
        await worker.tick()
        self.clock.advance(4)
        result = await worker.tick()
        self.assertEqual((result.state, dict(result.counts)["failed"]), ("partial", 1))
        self.clock.advance(3600)
        self.assertIsNone(await worker.tick())
        self.assertEqual(len(transport.calls), 3)

    async def test_policy_owner_and_recipient_revocation_never_dispatch(self):
        job = await self.scheduled()
        transport = FakeTransport()
        self.clock.advance(60)
        self.policy.category = False
        result = await CampaignWorker(self.api, transport=transport).tick()
        self.assertEqual(result.state, "paused")
        self.assertEqual(self.rows("SELECT COUNT(*) FROM service_campaign_attempts"), [(0,)])
        self.policy.category = True
        await self.api.resume_job(10, job.id, local_time=self.clock.future(), timezone="UTC")
        self.clock.advance(60)
        self.owner.side_effect = lambda actor: False
        result = await CampaignWorker(self.api, transport=transport).tick()
        self.assertEqual(result.state, "paused")
        self.owner.side_effect = lambda actor: actor in {10, 20}
        await self.api.resume_job(10, job.id, local_time=self.clock.future(), timezone="UTC")
        self.policy.denied.add(1001)
        self.clock.advance(60)
        result = await CampaignWorker(self.api, transport=transport).tick()
        self.assertEqual((result.state, dict(result.counts)["skipped"]), ("partial", 1))
        self.assertEqual(transport.calls, [])
        self.assertEqual(self.rows("SELECT result_code FROM service_campaign_recipients"), [("recipient_denied",)])

    async def test_deleted_group_and_membership_changes_fail_closed(self):
        group = await self.db.create_user_group(name="Группа")
        await self.db.set_user_group_member(group_id=group, telegram_id=1001, enabled=True)
        job = await self.scheduled(include_groups=(group,))
        await self.db.set_user_group_member(group_id=group, telegram_id=1001, enabled=False)
        self.clock.advance(60)
        transport = FakeTransport()
        result = await CampaignWorker(self.api, transport=transport).tick()
        self.assertEqual((result.state, dict(result.counts)["skipped"]), ("partial", 1))
        self.assertEqual(transport.calls, [])
        await self.db.set_user_group_member(group_id=group, telegram_id=1001, enabled=True)
        second = await self.scheduled(include_groups=(group,))
        await self.db.delete_user_group(group)
        self.clock.advance(60)
        with self.assertRaises(CampaignUnavailable):
            await CampaignWorker(self.api, transport=transport).tick()
        self.assertEqual((await self.api.get_job(10, second.id)).state, "paused")
        self.assertEqual(transport.calls, [])

    async def test_late_confirmation_and_stale_start_are_not_catchup_sends(self):
        job = await self.prepared()
        self.clock.advance(60)
        with self.assertRaises(CampaignConflict):
            await self.api.confirm_job(10, job.id, expected_snapshot=job.snapshot_sha256)
        second = await self.scheduled()
        self.clock.advance(121)
        transport = FakeTransport()
        self.assertIsNone(await CampaignWorker(self.api, transport=transport).tick())
        self.assertEqual((await self.api.get_job(10, second.id)).state, "paused")
        self.assertEqual(transport.calls, [])

    async def test_large_population_limit_rolls_back_entire_snapshot(self):
        with sqlite3.connect(self.path) as conn:
            conn.executemany("INSERT INTO users VALUES (?,?,?,?,?)", [
                (n, f"fixture-{n}@example.invalid", f"fixture-sub-{n}", 0, 1) for n in range(2000, 3200)])
            conn.executemany("INSERT INTO service_campaign_contacts VALUES (?,1,1,'private_update',0)",
                             [(n,) for n in range(2000, 3200)])
        with self.assertRaises(CampaignLimit):
            await self.prepared()
        self.assertEqual(self.rows("SELECT COUNT(*) FROM service_campaign_jobs"), [(0,)])
        self.assertEqual(self.rows("SELECT COUNT(*) FROM service_campaign_recipients"), [(0,)])

    async def test_sql_progress_budget_interrupts_and_rolls_back_snapshot(self):
        with sqlite3.connect(self.path) as conn:
            conn.executemany("INSERT INTO users VALUES (?,?,?,?,?)", [
                (n, f"budget-{n}@example.invalid", f"fixture-sub-{n}", 0, 1) for n in range(2000, 2500)])
            conn.executemany("INSERT INTO service_campaign_contacts VALUES (?,1,1,'private_update',0)",
                             [(n,) for n in range(2000, 2500)])
        with patch("campaign_queue_store.MAX_SQL_OPS", 0), self.assertRaises(CampaignUnavailable):
            await self.prepared()
        self.assertEqual(self.rows("SELECT COUNT(*) FROM service_campaign_jobs"), [(0,)])
        self.assertEqual(self.rows("SELECT COUNT(*) FROM service_campaign_recipients"), [(0,)])

    async def test_snapshot_identity_and_control_constraints_cannot_be_mutated(self):
        job = await self.prepared()
        statements = (("UPDATE service_campaign_jobs SET owner_id=20 WHERE id=?", (job.id,)),
                      ("UPDATE service_campaign_recipients SET telegram_id=1002 WHERE job_id=?", (job.id,)),
                      ("INSERT INTO service_campaign_recipients(job_id,telegram_id,proof_generation,updated_at) VALUES (?,1002,?,1)", (job.id, "0" * 32)),
                      ("DELETE FROM service_campaign_recipients WHERE job_id=?", (job.id,)),
                      ("UPDATE service_campaign_control SET lease_job=?,lease_token=NULL,lease_until=1 WHERE id=1", (job.id,)))
        for sql, params in statements:
            with sqlite3.connect(self.path) as conn, self.assertRaises(sqlite3.IntegrityError):
                conn.execute(sql, params)

    async def test_progress_and_transport_repr_do_not_expose_recipient_or_text(self):
        job = await self.prepared()
        keys = set(asdict(job))
        self.assertFalse(keys & {"owner_id", "telegram_id", "recipients", "subject", "body", "payload_json"})
        envelope = CampaignEnvelope(1001, "Приватная тема", "Приватный текст", job.operation_id)
        self.assertNotIn("Приват", repr(envelope))
        self.assertNotIn("chat_id", repr(envelope))
        self.assertNotIn("message_id", repr(CampaignReply("confirmed", 1001, 99)))
        self.assertNotIn("private-reason", repr(CampaignReply("unknown", reason="private-reason")))

    async def test_invalid_or_mismatched_replies_never_become_safe_retry_or_success(self):
        replies = (CampaignReply("confirmed", 1002, 1), CampaignReply("confirmed", 1001, True),
                   CampaignReply("rate_limited", 1001, retry_after=True),
                   CampaignReply("rate_limited", 1001, retry_after=3601),
                   CampaignReply("unavailable", 1001, reason="unclassified"),
                   CampaignReply("http_500", 1001), object())
        for reply in replies:
            job = await self.scheduled()
            transport = FakeTransport([reply])
            self.clock.advance(60)
            worker = CampaignWorker(self.api, transport=transport)
            result = await worker.tick()
            self.assertEqual((result.state, dict(result.counts)["unknown"]), ("paused", 1))
            self.assertIsNone(await worker.tick())
            self.assertEqual(len(transport.calls), 1)
            self.assertEqual((await self.api.get_job(10, job.id)).state, "paused")

    async def test_clock_is_refreshed_after_write_transaction_acquisition(self):
        original = self.api._queue._foundation._connection
        @asynccontextmanager
        async def delayed(*, write=False):
            async with original(write=write) as conn:
                if write:
                    self.clock.advance(61)
                yield conn
        with patch.object(self.api._queue._foundation, "_connection", delayed):
            with self.assertRaises(CampaignConflict):
                await self.prepared()
        self.assertEqual(self.rows("SELECT COUNT(*) FROM service_campaign_jobs"), [(0,)])

    async def test_clock_regression_never_dispatches_or_rewrites_history(self):
        job = await self.scheduled()
        self.clock.advance(-1)
        transport = FakeTransport()
        with self.assertRaises(CampaignUnavailable):
            await CampaignWorker(self.api, transport=transport).tick()
        self.assertEqual(transport.calls, [])
        self.assertEqual(self.rows("SELECT COUNT(*) FROM service_campaign_attempts"), [(0,)])
        self.assertEqual((await self.api.get_job(10, job.id)).state, "scheduled")

    async def test_category_policy_requires_exact_true_and_errors_are_redacted(self):
        self.policy.category = "approved"
        with self.assertRaises(CampaignDenied):
            await self.prepared()
        with patch.object(self.policy, "allow_category", side_effect=RuntimeError("private-policy-details")):
            with self.assertRaises(CampaignUnavailable) as error:
                await self.prepared()
        self.assertNotIn("private-policy", str(error.exception))
        self.assertEqual(self.rows("SELECT COUNT(*) FROM service_campaign_jobs"), [(0,)])

    async def test_sql_state_machine_rejects_skipped_confirmation_and_receipt(self):
        job = await self.prepared()
        for sql in ("UPDATE service_campaign_jobs SET state='completed' WHERE id=?",
                    "UPDATE service_campaign_jobs SET state='running' WHERE id=?"):
            with sqlite3.connect(self.path) as conn, self.assertRaises(sqlite3.IntegrityError):
                conn.execute(sql, (job.id,))
        with sqlite3.connect(self.path) as conn, self.assertRaises(sqlite3.IntegrityError):
            conn.execute("UPDATE service_campaign_recipients SET state='sent' WHERE job_id=?", (job.id,))

    async def test_delivery_modules_are_not_runtime_or_bot_api_imports(self):
        import ast
        root = Path(__file__).resolve().parents[1]
        for filename in ("service_campaign_delivery.py", "campaign_queue_store.py", "campaign_schedule.py"):
            tree = ast.parse((root / filename).read_text())
            imports = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.update(alias.name.split('.')[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.add(node.module.split('.')[0])
            self.assertFalse(imports & {"aiogram", "aiohttp", "app_runtime", "bot"})
        tree = ast.parse((root / "app_runtime.py").read_text())
        self.assertFalse(any(isinstance(node, ast.ImportFrom) and node.module in
                             {"service_campaign_delivery", "campaign_queue_store"} for node in ast.walk(tree)))
