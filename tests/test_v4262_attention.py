from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import unittest

from dashboard_attention import (
    build_attention_summary,
    latest_drain_problem_states,
    latest_job_problem_statuses,
    latest_rollout_problem_states,
)


ROOT = Path(__file__).resolve().parents[1]


@dataclass
class Job:
    id: int
    name: str
    status: str
    details: str = ""


class DashboardAttentionTests(unittest.TestCase):
    def test_calm_state_is_explicit(self):
        summary = build_attention_summary(
            active_alerts=0,
            job_statuses=[],
            infrastructure_states=[],
            rollout_states=[],
            drain_states=[],
        )

        self.assertEqual(summary.total, 0)
        self.assertEqual(summary.lines, ("✅ Требует внимания: нет",))

    def test_latest_job_state_wins_and_fleet_jobs_are_not_double_counted(self):
        runs = [
            Job(9, "backup.daily", "success"),
            Job(8, "backup.daily", "failed", "secret-like detail must not be rendered"),
            Job(7, "deploy.bot", "unknown"),
            Job(6, "host.control", "interrupted"),
            Job(5, "fleet.drain", "failed"),
            Job(4, "fleet.maintenance", "failed"),
        ]

        self.assertEqual(
            latest_job_problem_statuses(runs),
            ("unknown", "interrupted", "failed"),
        )

    def test_latest_rollout_terminal_state_resolves_previous_failure(self):
        plans = [
            {"id": "a", "state": "stopped_failed", "updated_at": 10},
            {"id": "b", "state": "cancelled", "updated_at": 20},
        ]
        self.assertEqual(latest_rollout_problem_states(plans), ("stopped_failed",))

        plans.append({"id": "c", "state": "success", "updated_at": 30})
        self.assertEqual(latest_rollout_problem_states(plans), ())

    def test_latest_drain_state_is_tracked_per_node(self):
        plans = [
            {"id": "a", "node_id": 1, "state": "unknown", "updated_at": 10},
            {"id": "b", "node_id": 1, "state": "review", "updated_at": 20},
            {"id": "c", "node_id": 2, "state": "partial", "updated_at": 15},
            {"id": "d", "node_id": 3, "state": "drained", "updated_at": 12},
        ]
        self.assertEqual(
            latest_drain_problem_states(plans),
            ("unknown", "partial"),
        )

        plans.append({"id": "e", "node_id": 1, "state": "drained", "updated_at": 30})
        self.assertEqual(latest_drain_problem_states(plans), ("partial",))

    def test_summary_has_deterministic_bounded_category_order(self):
        summary = build_attention_summary(
            active_alerts=2,
            job_statuses=["failed", "unknown", "interrupted"],
            infrastructure_states=["offline", "unknown", "degraded"],
            rollout_states=["stopped_unknown"],
            drain_states=["partial", "failed"],
        )

        self.assertEqual(summary.total, 11)
        self.assertEqual(summary.lines[0], "⚠️ Требует внимания: 11")
        self.assertTrue(summary.lines[1].startswith("🚨 Активные оповещения:"))
        self.assertTrue(summary.lines[2].startswith("🔴 Инфраструктура:"))
        self.assertTrue(summary.lines[3].startswith("🔴 Задания:"))
        self.assertTrue(summary.lines[4].startswith("🔴 Операции с нодами:"))
        self.assertLessEqual(len(summary.lines), 5)

    def test_unknown_and_interrupted_are_not_collapsed_into_failure(self):
        summary = build_attention_summary(
            active_alerts=0,
            job_statuses=["unknown", "interrupted"],
            infrastructure_states=["unknown"],
            rollout_states=["interrupted"],
            drain_states=["unknown"],
        )

        text = "\n".join(summary.lines)
        self.assertIn("неизвестно 1", text)
        self.assertIn("прервано 1", text)
        self.assertNotIn("ошибок 1", text)

    def test_unrecognized_states_do_not_inflate_total(self):
        summary = build_attention_summary(
            active_alerts=-3,
            job_statuses=["success", "running", "cancelled"],
            infrastructure_states=["healthy", "maintenance", "drained"],
            rollout_states=["success", "review", "cancelled"],
            drain_states=["drained", "review", "cancelled"],
        )

        self.assertEqual(summary.total, 0)
        self.assertEqual(summary.lines, ("✅ Требует внимания: нет",))

    def test_dashboard_wiring_stays_read_only(self):
        shell = (ROOT / "admin_shell.py").read_text(encoding="utf-8")
        dashboard = shell.split(
            '@admin_shell_router.callback_query(F.data == "admin:dashboard")',
            1,
        )[1].split(
            '@admin_shell_router.callback_query(F.data == "admin:subscriptions")',
            1,
        )[0]

        self.assertIn("build_attention_summary(", dashboard)
        self.assertIn("latest_job_problem_statuses(job_runs, acknowledged_run_ids=acknowledged_run_ids)", dashboard)
        self.assertIn("fleet_attention_states()", dashboard)
        self.assertIn("*attention.lines", dashboard)

        for mutation in (
            "start_job_run(",
            "finish_job_run(",
            "set_alert_",
            "update_alert_state(",
            "xui.start",
            "xui.stop",
            "xui.restart",
        ):
            self.assertNotIn(mutation, dashboard)

    def test_fleet_attention_reads_journals_without_remote_calls(self):
        source = (ROOT / "fleet_operations.py").read_text(encoding="utf-8")
        detail_block = source.split(
            "def fleet_attention_detail_plans()",
            1,
        )[1].split(
            "def fleet_attention_states()",
            1,
        )[0]
        summary_block = source.split(
            "def fleet_attention_states()",
            1,
        )[1].split(
            "def _health_icon",
            1,
        )[0]

        self.assertIn("plan_store.list()", detail_block)
        self.assertIn("drain_store.list()", detail_block)
        self.assertIn("fleet_attention_detail_plans()", summary_block)
        self.assertNotIn("await ", detail_block + summary_block)
        self.assertNotIn("xui.", detail_block + summary_block)


if __name__ == "__main__":
    unittest.main()
