"""Bounded process-local limiter state; synthetic identities and monotonic clock."""
from __future__ import annotations

import importlib
import random
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from client_rate_limit import SlidingWindowRateLimiter


class LimiterMemoryTests(unittest.TestCase):
    def test_other_users_activity_reclaims_fully_expired_buckets(self):
        limiter = SlidingWindowRateLimiter(limit=2, window_seconds=10)
        for key in range(100):
            self.assertTrue(limiter.allow(key, now=0))
        self.assertTrue(limiter.allow(1000, now=10))
        self.assertEqual(set(limiter._events), {1000})

    def test_has_bucket_reclaims_other_expired_users_without_allocating(self):
        limiter = SlidingWindowRateLimiter(limit=2, window_seconds=10)
        for key in range(100):
            limiter.allow(key, now=0)
        with patch("client_rate_limit.time.monotonic", return_value=10):
            self.assertFalse(limiter.has_bucket(1000))
        self.assertEqual(len(limiter._events), 0)

    def test_default_key_budget_rejects_without_allocating(self):
        limiter = SlidingWindowRateLimiter(limit=1, window_seconds=60)
        for key in range(4096):
            self.assertTrue(limiter.allow(key, now=0))
        self.assertFalse(limiter.allow(4096, now=0))
        self.assertEqual(len(limiter._events), 4096)
        self.assertNotIn(4096, limiter._events)

    def test_full_map_preserves_existing_users_remaining_budget(self):
        limiter = SlidingWindowRateLimiter(limit=2, window_seconds=10, max_keys=2)
        self.assertTrue(limiter.allow(1, now=0))
        self.assertTrue(limiter.allow(2, now=0))
        self.assertFalse(limiter.allow(3, now=1))
        self.assertTrue(limiter.allow(1, now=1))
        self.assertTrue(limiter.allow(2, now=1))
        self.assertFalse(limiter.allow(1, now=2))
        self.assertFalse(limiter.allow(2, now=2))
        self.assertEqual(set(limiter._events), {1, 2})

    def test_denial_does_not_extend_or_reorder_expiry(self):
        limiter = SlidingWindowRateLimiter(limit=1, window_seconds=10, max_keys=2)
        self.assertTrue(limiter.allow(1, now=0))
        self.assertTrue(limiter.allow(2, now=2))
        self.assertFalse(limiter.allow(1, now=9))
        self.assertTrue(limiter.allow(3, now=10))
        self.assertEqual(set(limiter._events), {2, 3})
        self.assertFalse(limiter.allow(2, now=10))

    def test_new_accepted_event_preserves_live_window_behind_expired_user(self):
        limiter = SlidingWindowRateLimiter(limit=3, window_seconds=10, max_keys=2)
        self.assertTrue(limiter.allow(1, now=0))
        self.assertTrue(limiter.allow(2, now=1))
        self.assertTrue(limiter.allow(1, now=8))
        self.assertTrue(limiter.allow(3, now=11))
        self.assertEqual(set(limiter._events), {1, 3})
        self.assertTrue(limiter.allow(1, now=11))
        self.assertEqual(list(limiter._events[1]), [8, 11])

    def test_capacity_is_reused_exactly_at_expiry_boundary(self):
        limiter = SlidingWindowRateLimiter(limit=1, window_seconds=10, max_keys=1)
        self.assertTrue(limiter.allow("1", now=0))
        self.assertFalse(limiter.allow(2, now=9.999))
        self.assertTrue(limiter.allow(2, now=10))
        self.assertEqual(set(limiter._events), {2})

    def test_reset_only_releases_target_capacity_and_preserves_foreign_window(self):
        limiter = SlidingWindowRateLimiter(limit=1, window_seconds=10, max_keys=2)
        limiter.allow(1, now=0)
        limiter.allow(2, now=0)
        limiter.reset("1")
        self.assertFalse(limiter.allow(2, now=1))
        self.assertTrue(limiter.allow(3, now=1))
        with patch("client_rate_limit.time.monotonic", return_value=1):
            self.assertFalse(limiter.has_bucket(1))
            self.assertTrue(limiter.has_bucket(2))
            self.assertFalse(limiter.has_bucket(999))
        self.assertEqual(set(limiter._events), {2, 3})

    def test_many_generations_of_distinct_ids_stay_bounded(self):
        limiter = SlidingWindowRateLimiter(limit=2, window_seconds=1, max_keys=3)
        for generation in range(250):
            current = generation * 2
            base = generation * 9
            for offset in range(9):
                self.assertEqual(limiter.allow(base + offset, now=current), offset < 3)
                self.assertLessEqual(len(limiter._events), 3)
                self.assertLessEqual(sum(map(len, limiter._events.values())), 6)
            self.assertEqual(set(limiter._events), set(range(base, base + 3)))

    def test_event_budget_stays_bounded_under_rejected_unique_key_pressure(self):
        limiter = SlidingWindowRateLimiter(limit=30, window_seconds=10, max_keys=8)
        for _ in range(30):
            for key in range(8):
                self.assertTrue(limiter.allow(key, now=0))
        for key in range(8, 2000):
            self.assertFalse(limiter.allow(key, now=1))
        self.assertEqual(len(limiter._events), 8)
        self.assertEqual(sum(map(len, limiter._events.values())), 240)
        self.assertTrue(limiter.allow(3000, now=10))
        self.assertEqual(set(limiter._events), {3000})

    def test_has_bucket_prunes_partial_window_without_refreshing_it(self):
        limiter = SlidingWindowRateLimiter(limit=2, window_seconds=10, max_keys=1)
        limiter.allow(1, now=0)
        limiter.allow(1, now=2)
        with patch("client_rate_limit.time.monotonic", return_value=10):
            self.assertTrue(limiter.has_bucket(1))
            self.assertEqual(list(limiter._events[1]), [2])
        self.assertFalse(limiter.allow(2, now=11))
        self.assertTrue(limiter.allow(2, now=12))

    def test_sliding_decisions_match_simple_oracle_without_capacity_pressure(self):
        limiter = SlidingWindowRateLimiter(limit=4, window_seconds=10, max_keys=64)
        rng = random.Random(995)
        reference: dict[int, list[float]] = {}
        current = 0.0
        for _ in range(5000):
            current += rng.choice((0, 0.125, 1, 10))
            key = rng.randrange(16)
            action = rng.randrange(10)
            events = [t for t in reference.get(key, []) if t > current - 10]
            if action == 0:
                limiter.reset(key)
                reference.pop(key, None)
            elif action == 1:
                with patch("client_rate_limit.time.monotonic", return_value=current):
                    self.assertEqual(limiter.has_bucket(key), bool(events))
            else:
                expected = len(events) < 4
                self.assertEqual(limiter.allow(str(key), now=current), expected)
                reference[key] = events + ([current] if expected else [])


class LimiterGuardTests(unittest.IsolatedAsyncioTestCase):
    async def test_pressure_uses_existing_refusal_before_customer_service(self):
        ui = importlib.import_module("client_access")
        limiter = SlidingWindowRateLimiter(limit=2, window_seconds=60, max_keys=1)
        self.assertTrue(limiter.allow(1001))
        flags = SimpleNamespace(snapshot=AsyncMock(return_value=SimpleNamespace(portal_enabled=True)))
        service = SimpleNamespace(traffic=AsyncMock(), profile=AsyncMock())
        call = SimpleNamespace(
            data="client:traffic", from_user=SimpleNamespace(id=1002),
            message=SimpleNamespace(chat=SimpleNamespace(id=1002, type="private")),
            answer=AsyncMock(),
        )
        render = AsyncMock()
        with patch.object(ui, "feature_flags", flags), patch.object(
            ui, "is_allowed", return_value=True
        ), patch.object(ui, "client_rate_limiter", limiter), patch.object(
            ui, "customer_service", service
        ), patch.object(ui, "render_callback", render):
            await ui.traffic_cb(call)
            call.answer.assert_awaited_once_with(
                "Слишком много запросов. Попробуйте немного позже.", show_alert=True
            )
            service.traffic.assert_not_awaited()
            service.profile.assert_not_awaited()
            render.assert_not_awaited()
            call.from_user.id = 1001
            self.assertTrue(await ui.guard_callback(call))
        self.assertEqual(set(limiter._events), {1001})

    async def test_portal_and_allowlist_denials_do_not_consume_key_capacity(self):
        ui = importlib.import_module("client_access")
        for portal, allowed in ((False, True), (True, False)):
            with self.subTest(portal=portal, allowed=allowed):
                limiter = SlidingWindowRateLimiter(limit=2, window_seconds=60, max_keys=1)
                flags = SimpleNamespace(snapshot=AsyncMock(return_value=SimpleNamespace(portal_enabled=portal)))
                event = SimpleNamespace(from_user=SimpleNamespace(id=1002), answer=AsyncMock())
                with patch.object(ui, "feature_flags", flags), patch.object(
                    ui, "is_allowed", return_value=allowed
                ), patch.object(ui, "client_rate_limiter", limiter):
                    self.assertFalse(await ui.guard_message(event))
                self.assertEqual(len(limiter._events), 0)
