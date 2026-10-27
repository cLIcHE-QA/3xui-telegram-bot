"""D3d synthetic negative tests: no URL, session or runtime route."""
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from subscription_page_import_preflight import check_import_eligibility

OWNER = 100001


class ImportPreflightTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.flags = SimpleNamespace(snapshot=AsyncMock(
            return_value=SimpleNamespace(portal_enabled=True)))
        self.profile = SimpleNamespace(
            exists=True, access_status="active", period_status="active",
            sub_id="PRIVATE_SUB_ID", email="private@example.invalid")
        self.service = SimpleNamespace(profile=AsyncMock(return_value=self.profile))

    async def decide(self, **overrides):
        args = dict(authenticated_owner=OWNER, customer_service=self.service,
                    feature_flags=self.flags, pilot_ids=frozenset({OWNER}),
                    explicitly_enabled=True)
        args.update(overrides)
        return await check_import_eligibility(**args)

    async def test_default_off_and_unknown_owner(self):
        self.assertFalse((await self.decide(explicitly_enabled=False)).permitted)
        self.assertFalse((await self.decide(authenticated_owner=100002)).permitted)
        self.assertFalse((await self.decide(authenticated_owner=True)).permitted)
        self.assertFalse((await self.decide(pilot_ids=frozenset())).permitted)

    async def test_fresh_flags_and_active_owner_required(self):
        self.flags.snapshot.return_value = SimpleNamespace(portal_enabled=False)
        self.assertFalse((await self.decide()).permitted)
        self.flags.snapshot.return_value = SimpleNamespace(portal_enabled=True)
        for key, value in [("exists", False), ("access_status", "disabled"),
                           ("access_status", "unknown"), ("period_status", "expired")]:
            original = getattr(self.profile, key)
            setattr(self.profile, key, value)
            self.assertFalse((await self.decide()).permitted)
            setattr(self.profile, key, original)

    async def test_fail_closed_on_provider_errors(self):
        self.service.profile.side_effect = RuntimeError("private provider details")
        self.assertFalse((await self.decide()).permitted)
        self.service.profile.side_effect = None
        self.flags.snapshot.side_effect = RuntimeError("private feature details")
        self.assertFalse((await self.decide()).permitted)

    async def test_eligible_only_returns_public_boolean_not_bearer(self):
        result = await self.decide()
        self.assertTrue(result.permitted)
        self.assertEqual(result.reason, "owner-eligible")
        self.assertNotIn("PRIVATE_SUB_ID", repr(result))
        self.assertNotIn("private@example.invalid", repr(result))
        self.service.profile.assert_awaited_with(OWNER)


if __name__ == "__main__":
    unittest.main()
