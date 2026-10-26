"""#887 D3d: synthetic D2a/D2b session-bound one-use preflight proof tests.

No Bot API, network ingress, real subscription URL or live acceptance.
Existing D2a/D2b tests independently exercise their login exchanges.
"""
from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from subscription_page_customer import MiniAppSessions, VerifiedMiniAppIdentity
from subscription_page_import_grants import (
    MAX_ISSUES_PER_WINDOW, MAX_PENDING_GRANTS, MAX_REDEEMS_PER_WINDOW,
    PROOF_TTL_MAX, SessionImportProofs,
)
from subscription_page_standalone import StandalonePilot

NOW = 1_800_000_000.0
OWNER = 100001
OTHER = 100002
STANDALONE_COOKIE = "S" * 43
STANDALONE_OTHER_COOKIE = "T" * 43


class SessionImportProofTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.clock = NOW
        self.profile = SimpleNamespace(
            exists=True, access_status="active", period_status="active",
            sub_id="SENSITIVE_ID", email="sensitive@example.invalid",
        )
        self.service = SimpleNamespace(profile=AsyncMock(return_value=self.profile))
        self.flags = SimpleNamespace(
            snapshot=AsyncMock(return_value=SimpleNamespace(portal_enabled=True)),
        )
        self.mini = MiniAppSessions(ttl=120)
        self.mini_cookie = self.mini.issue(
            VerifiedMiniAppIdentity(OWNER, int(NOW), b"synthetic-login-1"), NOW,
        )
        self.mini_second = self.mini.issue(
            VerifiedMiniAppIdentity(OWNER, int(NOW), b"synthetic-login-2"), NOW,
        )
        self.mini_other = self.mini.issue(
            VerifiedMiniAppIdentity(OTHER, int(NOW), b"synthetic-login-other"), NOW,
        )
        self.standalone = StandalonePilot(
            https_origin="https://web.example.invalid",
            customer_service=self.service, feature_flags=self.flags,
            pilot_ids=frozenset({OWNER, OTHER}), now=lambda: self.clock,
        )
        # Seed only the existing D2b *server-side session store*;
        # login approval itself has separate end-to-end D2b regression tests.
        self.standalone.sessions[self.standalone._hash(STANDALONE_COOKIE)] = (
            OWNER, NOW + 120,
        )
        self.standalone.sessions[self.standalone._hash(STANDALONE_OTHER_COOKIE)] = (
            OTHER, NOW + 120,
        )
        self.broker = self.make_broker()

    def make_broker(self, **overrides):
        args = dict(
            mini_sessions=self.mini, standalone=self.standalone,
            customer_service=self.service, feature_flags=self.flags,
            pilot_ids=frozenset({OWNER}),
            explicitly_enabled=True, now=lambda: self.clock,
            proof_ttl=45,
        )
        args.update(overrides)
        return SessionImportProofs(**args)

    async def issue(self, cookie=None, mode="telegram-mini-app", broker=None):
        return await (broker or self.broker).issue(
            mode=mode,
            session_cookie=self.mini_cookie if cookie is None else cookie,
        )

    async def consume(self, proof, cookie=None, mode="telegram-mini-app", broker=None):
        return await (broker or self.broker).consume(
            mode=mode,
            session_cookie=self.mini_cookie if cookie is None else cookie,
            proof=proof,
        )

    async def test_default_off_and_untrusted_session_fail_closed(self):
        off = self.make_broker(explicitly_enabled=False)
        self.assertFalse((await self.issue(broker=off)).approved)
        self.assertFalse((await self.issue(cookie="not-a-session")).approved)
        self.assertFalse((await self.issue(cookie=self.mini_other)).approved)
        self.assertFalse((await self.issue(mode="unknown-mode")).approved)
        self.assertFalse((await self.issue(cookie=STANDALONE_OTHER_COOKIE,
                                           mode="standalone")).approved)
        with self.assertRaises(TypeError):
            await self.broker.issue(authenticated_owner=OWNER,
                                    mode="telegram-mini-app",
                                    session_cookie=self.mini_cookie)

    async def test_single_use_owner_and_exact_cookie_bound(self):
        offer = await self.issue()
        self.assertTrue(offer.approved)
        self.assertEqual(len(offer.proof), 43)
        self.assertNotIn("SENSITIVE_ID", repr(offer))
        self.assertNotIn("sensitive@example.invalid", repr(offer))
        # Even a new authenticated session for the same owner cannot redeem it.
        self.assertFalse(await self.consume(offer.proof, cookie=self.mini_second))
        self.assertFalse(await self.consume(offer.proof))
        fresh = await self.issue()
        self.assertTrue(await self.consume(fresh.proof))
        self.assertFalse(await self.consume(fresh.proof))
        self.service.profile.assert_awaited_with(OWNER)

    async def test_cross_mode_and_cross_owner_attempts_burn_proof(self):
        offer = await self.issue()
        self.assertFalse(await self.consume(offer.proof, mode="standalone",
                                            cookie=STANDALONE_COOKIE))
        self.assertFalse(await self.consume(offer.proof))
        other = await self.issue(mode="standalone", cookie=STANDALONE_COOKIE)
        self.assertTrue(other.approved)
        self.assertFalse(await self.consume(other.proof, cookie=self.mini_other))
        self.assertFalse(await self.consume(other.proof, mode="standalone",
                                            cookie=STANDALONE_COOKIE))
        fresh = await self.issue(mode="standalone", cookie=STANDALONE_COOKIE)
        self.assertTrue(await self.consume(fresh.proof, mode="standalone",
                                           cookie=STANDALONE_COOKIE))

    async def test_standalone_session_bound_and_revocation(self):
        offer = await self.issue(mode="standalone", cookie=STANDALONE_COOKIE)
        self.assertTrue(offer.approved)
        self.assertTrue(await self.consume(offer.proof, mode="standalone",
                                           cookie=STANDALONE_COOKIE))
        second = await self.issue(mode="standalone", cookie=STANDALONE_COOKIE)
        self.standalone.sessions.pop(self.standalone._hash(STANDALONE_COOKIE))
        self.assertFalse(await self.consume(second.proof, mode="standalone",
                                            cookie=STANDALONE_COOKIE))

    async def test_expiry_boundary_and_expired_session(self):
        offer = await self.issue()
        self.clock += 45
        self.assertFalse(await self.consume(offer.proof))
        fresh = await self.issue()
        self.clock += 76
        self.assertFalse(await self.consume(fresh.proof))
        self.assertFalse((await self.issue()).approved)

    async def test_feature_owner_or_provider_veto_after_issue(self):
        offer = await self.issue()
        self.flags.snapshot.return_value = SimpleNamespace(portal_enabled=False)
        self.assertFalse(await self.consume(offer.proof))
        self.flags.snapshot.return_value = SimpleNamespace(portal_enabled=True)
        self.assertFalse(await self.consume(offer.proof))
        offer2 = await self.issue()
        self.profile.period_status = "expired"
        self.assertFalse(await self.consume(offer2.proof))
        self.profile.period_status = "active"
        self.service.profile.side_effect = RuntimeError("private upstream details")
        self.assertFalse((await self.issue()).approved)

    async def test_revoke_mini_app_session_and_no_session_revival(self):
        offer = await self.issue()
        self.mini.revoke(self.mini_cookie)
        self.assertFalse(await self.consume(offer.proof))
        self.assertFalse((await self.issue()).approved)

    async def test_invalid_proofs_wrong_cookie_and_replay(self):
        offer = await self.issue()
        for invalid in (None, "", "short", "?" * 43, "Q" * 100,
                        offer.proof + "\\n", 42):
            self.assertFalse(await self.consume(invalid))
        self.assertTrue(await self.consume(offer.proof))
        self.assertFalse(await self.consume(offer.proof))

    async def test_bounded_pending_capacity_and_per_session_throttling(self):
        for _ in range(MAX_ISSUES_PER_WINDOW):
            self.assertTrue((await self.issue()).approved)
        self.assertFalse((await self.issue()).approved)
        self.assertLessEqual(len(self.broker._pending), MAX_PENDING_GRANTS)
        self.clock += 60
        self.assertTrue((await self.issue()).approved)
        for _ in range(MAX_REDEEMS_PER_WINDOW):
            self.assertFalse(await self.consume("Q" * 43))
        self.assertFalse(await self.consume("Q" * 43))
        self.assertLessEqual(len(self.broker._redeem_rates), 256)

    async def test_concurrent_consumers_cannot_both_pass(self):
        offer = await self.issue()
        outcomes = await asyncio.gather(
            self.consume(offer.proof), self.consume(offer.proof),
        )
        self.assertEqual(sorted(outcomes), [False, True])

    async def test_session_revoke_during_async_policy_is_denied(self):
        original = self.service.profile
        async def profile_then_revoke(owner):
            self.mini.revoke(self.mini_cookie)
            return self.profile
        self.service.profile = AsyncMock(side_effect=profile_then_revoke)
        self.assertFalse((await self.issue()).approved)
        self.service.profile = original

    async def test_configuration_and_time_fail_closed(self):
        for invalid in (0, -1, PROOF_TTL_MAX + 1, True, 0.5):
            with self.subTest(ttl=invalid), self.assertRaises(ValueError):
                self.make_broker(proof_ttl=invalid)
        self.clock = float("nan")
        self.assertFalse((await self.issue()).approved)
        self.clock = 0.0
        self.assertFalse((await self.issue()).approved)


if __name__ == "__main__":
    unittest.main()
