"""Owner-only, in-process client limiter reset (#345). No live Telegram/provider calls."""
import time
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import advanced_users
from admin_privileges import required_role_for_callback
from client_rate_limit import SlidingWindowRateLimiter


def callback(data, actor=900):
    return SimpleNamespace(
        data=data,
        from_user=SimpleNamespace(id=actor, username="owner"),
        answer=AsyncMock(),
    )


class ClientSessionResetTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        advanced_users._session_reset_challenges.clear()
        self.limiter = SlidingWindowRateLimiter(limit=1, window_seconds=60)
        self.assertTrue(self.limiter.allow(111))
        self.assertTrue(self.limiter.allow(222))
        self.limiter_patch = patch.object(advanced_users, "client_rate_limiter", self.limiter)
        self.limiter_patch.start()
        self.guard = patch.object(
            advanced_users, "guard", new_callable=AsyncMock, return_value=True
        )
        self.find = patch.object(
            advanced_users.db, "get", new_callable=AsyncMock, return_value=object()
        )
        self.audit = patch.object(
            advanced_users, "audit_from_call", new_callable=AsyncMock
        )
        self.render = patch.object(
            advanced_users, "render_callback", new_callable=AsyncMock
        )
        self.mock_guard = self.guard.start()
        self.mock_find = self.find.start()
        self.mock_audit = self.audit.start()
        self.mock_render = self.render.start()

    async def asyncTearDown(self):
        self.render.stop()
        self.audit.stop()
        self.find.stop()
        self.guard.stop()
        self.limiter_patch.stop()
        advanced_users._session_reset_challenges.clear()

    async def ask(self, target=111, actor=900):
        cb = callback(f"admin:u:sessionreset:ask:{target}", actor)
        await advanced_users.user_session_reset_ask(cb)
        return cb

    async def run_reset(self, target, nonce, actor=900):
        cb = callback(f"admin:u:sessionreset:run:{target}:{nonce}", actor)
        await advanced_users.user_session_reset_run(cb)
        return cb

    async def test_only_target_bucket_cleared_and_replay_rejected(self):
        await self.ask()
        nonce = advanced_users._session_reset_challenges[900][1]
        await self.run_reset(111, nonce)
        self.assertFalse(self.limiter.has_bucket(111))
        self.assertTrue(self.limiter.has_bucket(222))
        self.assertTrue(self.limiter.allow(111))
        self.assertFalse(self.limiter.allow(222))
        self.mock_audit.assert_awaited()
        self.mock_audit.reset_mock()
        await self.run_reset(111, nonce)
        self.assertTrue(self.limiter.has_bucket(111))
        self.assertTrue(self.limiter.has_bucket(222))
        self.assertTrue(any("stale_or_mismatched" in str(c) for c in self.mock_audit.await_args_list))

    async def test_foreign_actor_and_foreign_target_rejected(self):
        await self.ask()
        nonce = advanced_users._session_reset_challenges[900][1]
        await self.run_reset(111, nonce, actor=901)
        self.assertTrue(self.limiter.has_bucket(111))
        await self.run_reset(222, nonce, actor=900)
        self.assertTrue(self.limiter.has_bucket(111))
        self.assertTrue(self.limiter.has_bucket(222))

    async def test_expired_challenge_rejected(self):
        await self.ask()
        target, nonce, _ = advanced_users._session_reset_challenges[900]
        advanced_users._session_reset_challenges[900] = (
            target, nonce, time.monotonic() - 1,
        )
        await self.run_reset(target, nonce)
        self.assertTrue(self.limiter.has_bucket(target))

    async def test_no_active_bucket_no_confirmation(self):
        self.limiter.reset(111)
        await self.ask()
        self.assertNotIn(900, advanced_users._session_reset_challenges)
        self.mock_render.assert_not_awaited()

    async def test_acl_declared_owner_only(self):
        self.assertEqual(
            required_role_for_callback("admin:u:sessionreset:ask:111"), "owner"
        )
        self.assertEqual(
            required_role_for_callback("admin:u:sessionreset:run:111:0123456789abcdef"),
            "owner",
        )
        self.assertIsNone(
            required_role_for_callback("admin:u:sessionreset:run:111:bad")
        )

    async def test_denied_guard_does_not_reset(self):
        self.mock_guard.return_value = False
        await self.ask()
        self.assertNotIn(900, advanced_users._session_reset_challenges)
        await self.run_reset(111, "0123456789abcdef")
        self.assertTrue(self.limiter.has_bucket(111))
        self.mock_audit.assert_not_awaited()

    async def test_target_deleted_before_confirm_is_denied(self):
        await self.ask()
        nonce = advanced_users._session_reset_challenges[900][1]
        self.mock_find.return_value = None
        await self.run_reset(111, nonce)
        self.assertTrue(self.limiter.has_bucket(111))
        self.assertTrue(any("user_missing" in str(c) for c in self.mock_audit.await_args_list))


if __name__ == "__main__":
    unittest.main()
