from __future__ import annotations

import asyncio
from dataclasses import replace
import socket
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from db import Database
from website_monitoring import (
    CONFIRMATION_DELAY,
    MAX_REDIRECTS,
    MAX_RESPONSE_BYTES,
    MAX_SITEMAP_BYTES,
    MAX_SITEMAP_DOCUMENTS,
    MAX_SITEMAP_URLS,
    SafeHttpResponse,
    SafePublicResolver,
    UnsafeTargetError,
    WebsiteCheckOutcome,
    WebsiteMonitoringError,
    WebsiteMonitoringRepository,
    WebsiteMonitoringService,
    canonicalize_public_url,
    classify_check_error,
    transition_monitor,
)


class QueueClient:
    def __init__(self, *items):
        self.items = list(items)
        self.calls: list[str] = []

    async def fetch(self, url: str):
        self.calls.append(url)
        if not self.items:
            raise AssertionError("unexpected fetch")
        item = self.items.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def response(
    *,
    url: str = "https://example.org/",
    status: int = 200,
    latency_ms: int = 100,
) -> SafeHttpResponse:
    return SafeHttpResponse(
        requested_url=url,
        final_url=url,
        status=status,
        latency_ms=latency_ms,
        headers={},
        body=b"ok",
        redirects=(),
    )


async def no_sleep(_seconds: float):
    return None


class WebsiteMonitoringFoundationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "bot.sqlite3"
        await Database(str(self.path)).init()
        self.repo = WebsiteMonitoringRepository(str(self.path))

    async def asyncTearDown(self):
        self.tmp.cleanup()

    def test_canonical_url_rejects_private_and_unsafe_targets(self):
        blocked = (
            "http://127.0.0.1/",
            "http://10.0.0.1/",
            "http://169.254.169.254/latest/meta-data/",
            "http://[::1]/",
            "https://metadata.google.internal/",
            "https://user:pass@example.org/",
            "https://example.org:8443/",
            "file:///etc/passwd",
        )
        for target in blocked:
            with self.subTest(target=target), self.assertRaises(UnsafeTargetError):
                canonicalize_public_url(target)

        self.assertEqual(
            canonicalize_public_url("example.org/path?q=1#fragment"),
            "https://example.org/path?q=1",
        )
        self.assertEqual(
            canonicalize_public_url("http://8.8.8.8"),
            "http://8.8.8.8/",
        )

    async def test_resolver_rejects_any_non_global_dns_answer(self):
        resolver = SafePublicResolver()
        loop = asyncio.get_running_loop()
        fake = [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                ("93.184.216.34", 443),
            ),
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                ("10.0.0.7", 443),
            ),
        ]
        with patch.object(loop, "getaddrinfo", return_value=fake):
            with self.assertRaises(UnsafeTargetError):
                await resolver.resolve("example.org", 443)

    def test_hard_bounds_match_release_contract(self):
        self.assertEqual(MAX_REDIRECTS, 5)
        self.assertEqual(MAX_RESPONSE_BYTES, 1024 * 1024)
        self.assertEqual(MAX_SITEMAP_BYTES, 2 * 1024 * 1024)
        self.assertEqual(MAX_SITEMAP_DOCUMENTS, 10)
        self.assertEqual(MAX_SITEMAP_URLS, 5000)
        self.assertEqual(CONFIRMATION_DELAY, 2)

    def test_state_machine_requires_confirmation_before_down(self):
        failure = WebsiteCheckOutcome(kind="failure", http_status=503, error_kind="http_status")
        first = transition_monitor("up", failure)
        self.assertEqual(first.next_state, "suspect")
        self.assertTrue(first.needs_recheck)
        self.assertFalse(first.open_incident)

        confirmed = transition_monitor("suspect", failure, confirmed=True)
        self.assertEqual(confirmed.next_state, "down")
        self.assertTrue(confirmed.open_incident)
        self.assertEqual(confirmed.notify_kind, "opened")

        recovered = transition_monitor(
            "down",
            WebsiteCheckOutcome(kind="success", http_status=200, latency_ms=50),
        )
        self.assertEqual(recovered.next_state, "up")
        self.assertTrue(recovered.resolve_incident)
        self.assertEqual(recovered.notify_kind, "recovered")

    def test_policy_error_is_not_site_down(self):
        outcome = classify_check_error(
            UnsafeTargetError("blocked", code="unsafe_target")
        )
        self.assertEqual(outcome.kind, "checker_error")
        transition = transition_monitor("up", outcome)
        self.assertEqual(transition.next_state, "up")
        self.assertFalse(transition.open_incident)

    async def test_watchers_are_deduplicated_and_share_one_monitor(self):
        first = await self.repo.add_watcher("https://example.org", 101)
        same = await self.repo.add_watcher("https://example.org/", 101)
        other = await self.repo.add_watcher("https://example.org/", 202)

        self.assertEqual(first.id, same.id)
        self.assertEqual(first.id, other.id)
        self.assertEqual(await self.repo.watchers(first.id), (101, 202))

        with sqlite3.connect(self.path) as conn:
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM website_monitors").fetchone()[0],
                1,
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM website_monitor_watchers").fetchone()[0],
                2,
            )

    async def test_per_admin_limit_does_not_duplicate_existing_subscription(self):
        one = await self.repo.add_watcher("https://one.example.org", 101, max_targets=1)
        same = await self.repo.add_watcher("https://one.example.org/", 101, max_targets=1)
        self.assertEqual(one.id, same.id)

        with self.assertRaises(WebsiteMonitoringError) as ctx:
            await self.repo.add_watcher("https://two.example.org", 101, max_targets=1)
        self.assertEqual(ctx.exception.code, "monitor_limit")

    async def test_confirmed_failure_opens_one_incident_then_recovery_resolves_it(self):
        monitor = await self.repo.add_watcher("https://example.org", 101)
        service = WebsiteMonitoringService(
            self.repo,
            QueueClient(
                response(status=503),
                response(status=503),
            ),
        )

        down = await service.check_monitor(monitor.id, sleep=no_sleep)
        self.assertEqual(down.previous_state, "unknown")
        self.assertEqual(down.final_state, "down")
        self.assertEqual(down.notify_kind, "opened")
        self.assertIsNotNone(down.incident_id)

        with sqlite3.connect(self.path) as conn:
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) FROM website_incidents WHERE monitor_id = ? AND resolved_at = 0",
                    (monitor.id,),
                ).fetchone()[0],
                1,
            )

        service.client = QueueClient(response(status=200))
        up = await service.check_monitor(monitor.id, sleep=no_sleep)
        self.assertEqual(up.final_state, "up")
        self.assertEqual(up.notify_kind, "recovered")
        self.assertEqual(up.incident_id, down.incident_id)

        with sqlite3.connect(self.path) as conn:
            resolved = conn.execute(
                "SELECT resolved_at FROM website_incidents WHERE id = ?",
                (down.incident_id,),
            ).fetchone()[0]
            self.assertGreater(resolved, 0)

    async def test_failed_confirmation_checker_error_preserves_previous_stable_state(self):
        monitor = await self.repo.add_watcher("https://example.org", 101)
        await self.repo.store_check(
            monitor.id,
            state="up",
            outcome=WebsiteCheckOutcome(kind="success", http_status=200, latency_ms=20),
            next_check_at=0,
        )
        service = WebsiteMonitoringService(
            self.repo,
            QueueClient(
                response(status=503),
                UnsafeTargetError("policy", code="unsafe_target"),
            ),
        )
        result = await service.check_monitor(monitor.id, sleep=no_sleep)
        self.assertEqual(result.previous_state, "up")
        self.assertEqual(result.final_state, "up")
        self.assertEqual(result.outcome.kind, "checker_error")
        self.assertIsNone(result.incident_id)

    async def test_notification_journal_is_idempotent(self):
        monitor = await self.repo.add_watcher("https://example.org", 101)
        incident_id = await self.repo.open_incident(
            monitor.id,
            WebsiteCheckOutcome(kind="failure", http_status=503, error_kind="http_status"),
        )
        first = await self.repo.record_notification(
            incident_id,
            101,
            kind="opened",
            sequence=0,
        )
        duplicate = await self.repo.record_notification(
            incident_id,
            101,
            kind="opened",
            sequence=0,
        )
        self.assertTrue(first)
        self.assertFalse(duplicate)


if __name__ == "__main__":
    unittest.main()
