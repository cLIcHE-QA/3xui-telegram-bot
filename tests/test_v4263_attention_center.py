from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import unittest

import admin_navigation
from admin_privileges import required_role_for_callback
from dashboard_attention import (
    AttentionItem,
    build_attention_items,
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
    started_at: int = 0
    finished_at: int = 0
    details: str = ""


@dataclass
class Alert:
    code: str
    target: str
    active: int = 1
    first_seen: int = 0
    last_seen: int = 0
    last_value: str = ""


def callback_values(markup) -> set[str]:
    return {
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
        if button.callback_data
    }


class AttentionCenterTests(unittest.TestCase):
    def test_detail_count_matches_v4262_summary_sources(self):
        alerts = [
            Alert("node_offline", "Edge-1", last_seen=90),
            Alert("backup_stale", "Master", last_seen=80),
        ]
        jobs = [
            Job(9, "deploy.bot", "unknown", started_at=70),
            Job(8, "backup.daily", "failed", started_at=60),
            Job(7, "fleet.drain", "failed", started_at=50),
        ]
        infra = [
            {"stable_id": "master", "label": "Master", "status": "unknown"},
            {"stable_id": "node:2", "label": "Edge-1 · node_id=2", "status": "offline"},
        ]
        rollout = [{"id": "r1", "state": "stopped_unknown", "updated_at": 40}]
        drain = [{"id": "d1", "node_id": 2, "state": "partial", "updated_at": 30}]

        items = build_attention_items(
            active_alerts=alerts,
            job_runs=jobs,
            infrastructure=infra,
            rollout_plans=rollout,
            drain_plans=drain,
        )
        summary = build_attention_summary(
            active_alerts=len(alerts),
            job_statuses=latest_job_problem_statuses(jobs),
            infrastructure_states=[str(item["status"]) for item in infra],
            rollout_states=latest_rollout_problem_states(rollout),
            drain_states=latest_drain_problem_states(drain),
        )

        self.assertEqual(len(items), summary.total)
        self.assertEqual(summary.total, 8)

    def test_backup_problems_are_grouped_without_changing_count(self):
        items = build_attention_items(
            active_alerts=[Alert("backup_stale", "Master", last_seen=10)],
            job_runs=[Job(1, "backup.offsite", "failed", started_at=9)],
            infrastructure=[],
            rollout_plans=[],
            drain_plans=[],
        )

        self.assertEqual(len(items), 2)
        self.assertEqual({item.category for item in items}, {"backups"})
        self.assertTrue(all("details" not in item.context for item in items))

    def test_resolved_job_disappears_on_refresh_semantics(self):
        runs = [
            Job(3, "deploy.bot", "success", started_at=30),
            Job(2, "deploy.bot", "failed", started_at=20, details="secret-like old error"),
        ]
        items = build_attention_items(
            active_alerts=[],
            job_runs=runs,
            infrastructure=[],
            rollout_plans=[],
            drain_plans=[],
        )
        self.assertEqual(items, ())

    def test_detail_never_copies_job_details_or_alert_value(self):
        secret = "sub_id=secret-value"
        items = build_attention_items(
            active_alerts=[Alert("job_failed", "scheduler", last_seen=10, last_value=secret)],
            job_runs=[Job(5, "host.control", "interrupted", started_at=9, details=secret)],
            infrastructure=[],
            rollout_plans=[],
            drain_plans=[],
        )

        rendered = "\n".join(
            f"{item.stable_id} {item.label} {item.context}"
            for item in items
        )
        self.assertNotIn(secret, rendered)

    def test_navigation_uses_only_existing_canonical_read_only_parents(self):
        callbacks = callback_values(admin_navigation.attention_menu())
        self.assertEqual(
            callbacks,
            {
                "admin:health",
                "admin:jobs",
                "admin:alerts",
                "admin:backups",
                "admin:fleet",
                "admin:attention",
                "admin:dashboard",
            },
        )
        self.assertEqual(required_role_for_callback("admin:attention"), "read_only")
        for callback in callbacks:
            self.assertIsNotNone(required_role_for_callback(callback))

    def test_attention_renderer_is_bounded_and_has_refresh_back(self):
        shell = (ROOT / "admin_shell.py").read_text(encoding="utf-8")
        block = shell.split("def _attention_detail_lines", 1)[1].split(
            '@admin_shell_router.message(Command("admin"))',
            1,
        )[0]
        self.assertIn("selected[:5]", block)
        self.assertIn("… ещё", block)

        menu = admin_navigation.attention_menu()
        labels = {
            button.callback_data: button.text
            for row in menu.inline_keyboard
            for button in row
            if button.callback_data
        }
        self.assertEqual(labels["admin:attention"], "🔄 Обновить")
        self.assertEqual(labels["admin:dashboard"], "⬅ Обзор")

    def test_attention_handler_is_read_only_and_has_no_item_callbacks(self):
        shell = (ROOT / "admin_shell.py").read_text(encoding="utf-8")
        handler = shell.split(
            '@admin_shell_router.callback_query(F.data == "admin:attention")',
            1,
        )[1].split(
            '@admin_shell_router.callback_query(F.data == "admin:subscriptions")',
            1,
        )[0]

        self.assertIn("build_attention_items(", handler)
        self.assertIn("fleet_attention_detail_plans()", handler)
        self.assertIn("attention_menu()", handler)
        for mutation in (
            "start_job_run(",
            "finish_job_run(",
            "update_alert_state(",
            "set_alert_",
            "xui.start",
            "xui.stop",
            "xui.restart",
            "save(",
        ):
            self.assertNotIn(mutation, handler)

        # Items are rendered as text; stale/deleted objects cannot create dead callbacks.
        self.assertNotIn("callback_data=f", handler)

    def test_empty_state_has_no_false_warning(self):
        shell = (ROOT / "admin_shell.py").read_text(encoding="utf-8")
        self.assertIn("✅ Актуальных проблем нет.", shell)
        self.assertIn("⚠️ Требует внимания", shell)


if __name__ == "__main__":
    unittest.main()
