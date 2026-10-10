from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from admin_privileges import required_role_for_callback
from dashboard_attention import build_attention_items, latest_job_problem_statuses
from db import Database
from db_migrations import CURRENT_SCHEMA_VERSION, MIGRATIONS, run_migrations
from deploy_control import DeployControlError, DeployOperation, DeployStatus
from job_update_ack import REASON_LABELS, correlate_deploy


class HistoricalUnknownAckTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "bot.sqlite3"
        self.db = Database(str(self.path))
        await self.db.init()

    async def asyncTearDown(self):
        self.temp.cleanup()

    async def _job(self, name="bot.update", status="unknown", details=""):
        run_id = await self.db.start_job_run(name=name, trigger="admin", actor_id=1, details=details)
        await self.db.finish_job_run(run_id, status=status, duration_ms=0, details=details)
        return run_id

    @staticmethod
    def _evidence(code="journal_missing"):
        return SimpleNamespace(
            code=code, operation_id="a" * 32,
            requested_release="v4.26.7", agent_state="unknown", target_sha="",
            current_release="v4.26.8", current_sha="", postcondition="not_proven",
        )

    async def test_v11_upgrade_preserves_unknown_and_adds_append_only_table(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "legacy.sqlite3"
            await run_migrations(str(path), migrations=MIGRATIONS[:11])
            with sqlite3.connect(path) as conn:
                conn.execute(
                    "INSERT INTO job_runs(name, trigger, status, started_at) "
                    "VALUES ('bot.update', 'admin', 'unknown', 123)"
                )
                conn.commit()
                old_id = conn.execute("SELECT id FROM job_runs").fetchone()[0]
            await Database(str(path)).init()
            with sqlite3.connect(path) as conn:
                self.assertEqual(CURRENT_SCHEMA_VERSION, 13)
                self.assertEqual(conn.execute(
                    "SELECT status FROM job_runs WHERE id=?", (old_id,)
                ).fetchone()[0], "unknown")
                self.assertEqual(conn.execute(
                    "SELECT count(*) FROM bot_update_acknowledgments"
                ).fetchone()[0], 0)
                self.assertEqual(conn.execute("PRAGMA quick_check").fetchone()[0], "ok")

    async def test_atomic_audit_duplicate_restart_and_immutable_row(self):
        job_id = await self._job(details="operation_id=" + "a"*32 + "; release=v4.26.7")
        result = await self.db.acknowledge_bot_update_unknown(
            job_id, actor_id=501, actor_username="owner", reason_code="reviewed",
            evidence=self._evidence(),
        )
        self.assertTrue(result)
        self.assertFalse(await self.db.acknowledge_bot_update_unknown(
            job_id, actor_id=502, actor_username="other", reason_code="recovered",
            evidence=self._evidence(),
        ))
        reopened = Database(str(self.path))
        await reopened.init()
        record = await reopened.get_bot_update_acknowledgment(job_id)
        self.assertIsNotNone(record)
        self.assertEqual(record.actor_id, 501)
        self.assertEqual(record.reason_code, "reviewed")
        self.assertEqual((await reopened.get_job_run(job_id)).status, "unknown")
        with sqlite3.connect(self.path) as conn:
            self.assertEqual(conn.execute(
                "SELECT count(*) FROM audit_log "
                "WHERE action = 'bot.update.unknown.acknowledged' AND target_id = ?",
                (str(job_id),),
            ).fetchone()[0], 1)
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute(
                    "UPDATE bot_update_acknowledgments SET reason_code='recovered' "
                    "WHERE job_run_id=?", (job_id,)
                )
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute(
                    "DELETE FROM bot_update_acknowledgments WHERE job_run_id=?", (job_id,)
                )

    async def test_invalid_target_status_actor_or_reason_does_not_suppress(self):
        for name, status in [
            ("bot.update", "success"), ("backup.daily", "unknown"),
            ("bot.update", "failed"),
        ]:
            run_id = await self._job(name, status)
            with self.assertRaises(ValueError):
                await self.db.acknowledge_bot_update_unknown(
                    run_id, actor_id=501, actor_username="", reason_code="reviewed",
                    evidence=self._evidence(),
                )
        run_id = await self._job()
        for actor_id, reason in [(0, "reviewed"), (10, "arbitrary")]:
            with self.assertRaises(ValueError):
                await self.db.acknowledge_bot_update_unknown(
                    run_id, actor_id=actor_id, actor_username="", reason_code=reason,
                    evidence=self._evidence(),
                )
        self.assertIsNone(await self.db.get_bot_update_acknowledgment(run_id))

    async def test_new_failed_or_unknown_runs_remain_visible(self):
        old = await self._job()
        await self.db.acknowledge_bot_update_unknown(
            old, actor_id=501, actor_username="owner", reason_code="insufficient",
            evidence=self._evidence(),
        )
        for fresh_status in ("failed", "unknown"):
            fresh = await self._job(status=fresh_status)
            jobs = await self.db.list_job_runs()
            suppressed = await self.db.list_bot_update_acknowledged_run_ids(
                [j.id for j in jobs]
            )
            item = build_attention_items(
                active_alerts=[], job_runs=jobs, acknowledged_run_ids=suppressed,
                infrastructure=[], rollout_plans=[], drain_plans=[],
            )
            self.assertEqual(len(item), 1)
            self.assertEqual(item[0].stable_id, f"job:bot.update:{fresh}")
            self.assertEqual(latest_job_problem_statuses(
                jobs, acknowledged_run_ids=suppressed
            ), (fresh_status,))

    async def test_agent_missing_or_unreachable_evidence_is_not_success(self):
        run_id = await self._job(details="operation_id=" + "a"*32 + "; release=v4.26.7")
        job = await self.db.get_job_run(run_id)
        self.assertEqual((await correlate_deploy(job, None)).code, "agent_unconfigured")
        client = SimpleNamespace(
            get_operation=AsyncMock(side_effect=DeployControlError("offline", code="network_error"))
        )
        self.assertEqual((await correlate_deploy(job, client)).code, "journal_unavailable")
        client.get_operation = AsyncMock(return_value=None)
        self.assertEqual((await correlate_deploy(job, client)).code, "journal_missing")

    async def test_agent_read_only_correlation_never_proves_old_unknown_by_current_health(self):
        run_id = await self._job(details="operation_id=" + "a"*32 + "; release=v4.26.7")
        job = await self.db.get_job_run(run_id)
        agent = SimpleNamespace(
            get_operation=AsyncMock(return_value=DeployOperation(
                operation_id="a"*32, release="v4.26.7", allow_downgrade=False,
                state="unknown", current_release="v4.26.8",
                target_sha="b"*40, error_code="", created_at="", updated_at="", finished_at="",
            )),
            status=AsyncMock(return_value=DeployStatus(
                current_release="v4.26.8", current_sha="c"*40, bot_version="4.26.8",
                health="ok", db="ok", connectivity="ok",
                active_operation="", agent_version="test",
            )),
        )
        result = await correlate_deploy(job, agent)
        self.assertEqual(result.code, "journal_found")
        self.assertEqual(result.postcondition, "not_proven")
        agent.get_operation.assert_awaited_once_with("a"*32)
        agent.status.assert_awaited_once()
        self.assertFalse(hasattr(agent, "deploy"))

    async def test_owner_only_callback_catalog(self):
        for suffix in ("", ":reviewed", ":reviewed:confirm"):
            self.assertEqual(
                required_role_for_callback("admin:botupd:ack:80" + suffix), "owner"
            )
        self.assertIsNone(required_role_for_callback("admin:botupd:ack:80:unsafe"))
        self.assertEqual(set(REASON_LABELS), {"reviewed", "recovered", "insufficient"})


if __name__ == "__main__":
    unittest.main()
