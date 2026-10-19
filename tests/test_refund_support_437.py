"""#437: read-only Support справочник и fail-closed legal publication gate."""
from __future__ import annotations

from datetime import datetime, timezone
import importlib
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from admin_privileges import required_role_for_callback
from refund_support_policy import TERMS_URL, PublishedTerms, get_published_terms


NOW = datetime(2026, 10, 19, 20, 0, tzinfo=timezone.utc)


def valid_record():
    return {
        "schema": 1,
        "terms": {
            "publication_state": "published",
            "revision": "v1.0",
            "effective_at": "2026-10-16",
            "content_sha256": "a" * 64,
            "verified_at": "2026-10-19T12:00:00Z",
            "url": TERMS_URL,
        },
    }


class PublishedTermsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "publication.json"

    def tearDown(self):
        self.tmp.cleanup()

    def load(self, record):
        self.path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        return get_published_terms(self.path, now=NOW)

    def test_repository_current_state_is_unpublished(self):
        self.assertIsNone(get_published_terms(now=NOW))

    def test_complete_publication_record(self):
        result = self.load(valid_record())
        self.assertIsNotNone(result)
        self.assertEqual(result.revision, "v1.0")
        self.assertEqual(result.url, TERMS_URL)
        self.assertEqual(result.effective_at.isoformat(), "2026-10-16")

    def test_unverified_or_malformed_manifest_fails_closed(self):
        for name, value in (
            ("publication_state", "unpublished"),
            ("revision", None),
            ("revision", "<script>"),
            ("effective_at", "2026-13-16"),
            ("effective_at", "2026-10-20"),
            ("content_sha256", "invalid"),
            ("verified_at", None),
            ("verified_at", "2026-10-20T12:00:00Z"),
            ("url", "https://attacker.example.invalid/terms"),
        ):
            with self.subTest(name=name, value=value):
                data = valid_record()
                data["terms"][name] = value
                self.assertIsNone(self.load(data))

        self.path.write_text("{ broken json", encoding="utf-8")
        self.assertIsNone(get_published_terms(self.path, now=NOW))
        self.path.unlink()
        self.assertIsNone(get_published_terms(self.path, now=NOW))
        self.assertIsNone(self.load({"schema": 1, "terms": []}))
        self.assertIsNone(self.load({"schema": 99, "terms": valid_record()["terms"]}))


class RefundPolicyRoutingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        with patch.dict(os.environ, {
            "BOT_TOKEN": "123456789:offline-tests",
            "PANEL_URL": "https://panel.example.invalid/base",
            "PANEL_API_TOKEN": "offline-token",
            "SUBSCRIPTION_URL_TEMPLATE": "https://sub.example.invalid/{sub_id}",
            "ALLOWED_TELEGRAM_IDS": "1",
            "ADMIN_TELEGRAM_IDS": "1",
            "DB_PATH": "/tmp/refund-guide-offline-tests.sqlite3",
        }):
            self.module = importlib.import_module("business_admin")

    async def render(self, callback, *, permitted=True, publication=None):
        call = SimpleNamespace(data=callback, answer=AsyncMock())
        renderer = AsyncMock()
        with (
            patch.object(self.module, "guard", new=AsyncMock(return_value=permitted)) as guard,
            patch.object(self.module, "render_callback", new=renderer),
            patch.object(self.module, "get_published_terms", return_value=publication),
            patch.object(self.module, "db") as fake_db,
        ):
            await self.module.refund_policy_guide(call)
            guard.assert_awaited_once_with(call)
            fake_db.assert_not_called()
        if not permitted:
            renderer.assert_not_awaited()
            call.answer.assert_not_awaited()
            return None, []
        renderer.assert_awaited_once()
        call.answer.assert_awaited_once()
        args, kwargs = renderer.await_args
        buttons = [b for row in kwargs["reply_markup"].inline_keyboard for b in row]
        return args[1], buttons

    async def test_entry_and_back_navigation_are_read_only(self):
        for callback in (
            "admin:refundpolicy", "admin:refundpolicy:check",
            "admin:refundpolicy:issues", "admin:refundpolicy:terms",
            "admin:refundpolicy:owner",
        ):
            with self.subTest(callback=callback):
                self.assertEqual(required_role_for_callback(callback), "read_only")
                content, buttons = await self.render(callback)
                self.assertIn("возврат", content.lower())
                destinations = {button.callback_data for button in buttons}
                self.assertIn("admin:payments", destinations)
                self.assertFalse(any(
                    dest and ("refund:run" in dest or "payment:status:" in dest)
                    for dest in destinations
                ))
                self.assertFalse(any(button.url for button in buttons))
        _, buttons = await self.render("admin:refundpolicy")
        self.assertIn("admin:refundpolicy:check", {b.callback_data for b in buttons})
        self.assertIn("admin:refundpolicy:owner", {b.callback_data for b in buttons})

    async def test_terms_are_only_linked_when_manifest_is_published(self):
        pending, buttons = await self.render("admin:refundpolicy:terms")
        self.assertIn("не опубликована", pending)
        self.assertFalse(any(button.url for button in buttons))
        published = PublishedTerms(
            revision="v1.0", effective_at=NOW.date(),
            content_sha256="a" * 64, verified_at=NOW, url=TERMS_URL,
        )
        active, buttons = await self.render("admin:refundpolicy:terms", publication=published)
        self.assertIn("v1.0", active)
        self.assertIn("2026-10-19", active)
        self.assertEqual([b.url for b in buttons if b.url], [TERMS_URL])

    async def test_no_refund_operations_or_14_day_program(self):
        for callback in ("admin:refundpolicy:check", "admin:refundpolicy:issues",
                         "admin:refundpolicy:owner"):
            content, _ = await self.render(callback)
            self.assertNotIn("14 дней", content)
            self.assertNotIn("автоматически вернуть", content)
        for callback in ("admin:starsrefund:ask:7", "admin:starsrefund:run:7",
                         "admin:payment:status:7:refunded"):
            self.assertEqual(required_role_for_callback(callback), "admin")

    async def test_denied_guard_never_renders(self):
        await self.render("admin:refundpolicy", permitted=False)

    def test_unknown_callback_is_denied(self):
        for callback in (
            "admin:refundpolicy:refund:7", "admin:refundpolicy:edit",
            "admin:refundpolicy:run:1",
        ):
            self.assertIsNone(required_role_for_callback(callback))
