"""#564: hidden legacy entrypoints retain real guards and read-only redirects."""
import importlib
import os
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from client_flags import FeatureSnapshot
from client_rate_limit import SlidingWindowRateLimiter
from customer_service import CustomerProfile


class LegacyCommands564Tests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        env = {
            "BOT_TOKEN": "123456789:offline-tests", "PANEL_URL": "https://panel.example.invalid/base",
            "PANEL_API_TOKEN": "offline-token", "SUBSCRIPTION_URL_TEMPLATE": "https://sub.example.invalid/{sub_id}",
            "ALLOWED_TELEGRAM_IDS": "1", "ADMIN_TELEGRAM_IDS": "1",
        }
        with patch.dict(os.environ, env, clear=False):
            self.ui = importlib.import_module("client_access")
        self.settings = SimpleNamespace(allowed_telegram_ids={1001}, admin_telegram_ids={2001})

    async def invoke(self, payload, *, callback=False, actor=1001, snapshot=None, flags_present=True, limiter=None):
        event = SimpleNamespace(
            data=payload, text=payload,
            from_user=SimpleNamespace(id=actor) if actor is not None else None,
            answer=AsyncMock(),
        )
        flags = SimpleNamespace(snapshot=AsyncMock(return_value=snapshot or FeatureSnapshot(True, True, False)))
        # Only profile reads exist on this fake; any attempted mutation fails.
        service = SimpleNamespace(profile=AsyncMock(return_value=CustomerProfile(exists=False)))
        render = AsyncMock()
        with patch.object(self.ui, "settings", self.settings), \
                patch.object(self.ui, "feature_flags", flags if flags_present else None), \
                patch.object(self.ui, "client_rate_limiter", limiter or SlidingWindowRateLimiter(limit=30, window_seconds=60)), \
                patch.object(self.ui, "customer_service", service), \
                patch.object(self.ui, "render_callback", new=render):
            handler = self.ui.legacy_client_callback if callback else self.ui.legacy_client_command
            await handler(event)
        return event, service, render

    async def test_both_legacy_slash_commands_recommend_start_without_service_calls(self):
        for payload in ("/create", "/inbounds"):
            event, service, render = await self.invoke(payload)
            event.answer.assert_awaited_once()
            text = event.answer.await_args.args[0]
            self.assertIn("/start", text)
            self.assertNotIn(payload, text)
            self.assertIn("reply_markup", event.answer.await_args.kwargs)
            service.profile.assert_not_awaited()
            render.assert_not_awaited()

    async def test_all_saved_legacy_callbacks_render_home_with_only_profile_read(self):
        for payload in ("create", "inbounds", "subscription"):
            event, service, render = await self.invoke(payload, callback=True)
            service.profile.assert_awaited_once_with(1001)
            render.assert_awaited_once()
            self.assertIn("Личный кабинет", render.await_args.args[1])
            self.assertIn("reply_markup", render.await_args.kwargs)
            event.answer.assert_awaited_once()

    async def assert_denied(self, **options):
        for callback, payloads in ((False, ("/create", "/inbounds")), (True, ("create", "inbounds", "subscription"))):
            for payload in payloads:
                event, service, render = await self.invoke(payload, callback=callback, **options)
                event.answer.assert_awaited_once()
                self.assertNotIn("reply_markup", event.answer.await_args.kwargs)
                service.profile.assert_not_awaited()
                render.assert_not_awaited()

    async def test_outside_allowlist_and_missing_actor_are_denied(self):
        await self.assert_denied(actor=1002)
        await self.assert_denied(actor=None)

    async def test_env_portal_veto_cannot_be_overridden(self):
        await self.assert_denied(snapshot=FeatureSnapshot(True, False, True, db_portal=True))

    async def test_db_off_unavailable_and_absent_flags_fail_closed(self):
        await self.assert_denied(snapshot=FeatureSnapshot(True, True, True, db_portal=False))
        await self.assert_denied(snapshot=FeatureSnapshot(False, True, True))
        await self.assert_denied(flags_present=False)

    async def test_existing_admin_allowlist_access_is_preserved(self):
        event, service, render = await self.invoke("create", callback=True, actor=2001)
        service.profile.assert_awaited_once_with(2001)
        render.assert_awaited_once()
        event.answer.assert_awaited_once()

    async def test_legacy_routes_still_share_rate_limiting(self):
        limiter = SlidingWindowRateLimiter(limit=1, window_seconds=60)
        await self.invoke("/create", limiter=limiter)
        event, service, render = await self.invoke("inbounds", callback=True, limiter=limiter)
        self.assertIn("Слишком много запросов", event.answer.await_args.args[0])
        service.profile.assert_not_awaited()
        render.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
