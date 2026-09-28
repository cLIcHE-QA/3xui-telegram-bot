from __future__ import annotations

from dataclasses import replace
import os
from unittest.mock import AsyncMock, patch
import unittest

from cheburcheck import CheburcheckClient, ProbeSummary, parse_response

_TEST_ENV = {
    "BOT_TOKEN": "123456789:offline-test-token",
    "PANEL_URL": "https://master.example.invalid/base",
    "PANEL_API_TOKEN": "offline-panel-token",
    "SUBSCRIPTION_URL_TEMPLATE": "https://sub.example.invalid/sub/{sub_id}",
    "ALLOWED_TELEGRAM_IDS": "1",
    "ADMIN_TELEGRAM_IDS": "1",
    "HOST_CONTROL_TARGETS": "",
    "NODE_BACKUP_TARGETS": "",
}
with patch.dict(os.environ, _TEST_ENV, clear=False):
    import cheburcheck_admin


def domain_result():
    return parse_response({
        "id": "11111111-1111-1111-1111-111111111111",
        "target": "example.org",
        "target_type": "Домен",
        "blocked": False,
        "rkn_domain": None,
        "ips": ["93.184.216.34"],
        "reverse_lookup": [],
        "blocked_subnets": [],
        "cdn_providers": {},
        "geo": {
            "asn": "AS216154",
            "organisation": "Example ISP",
            "location": "Amsterdam, Netherlands",
        },
        "whitelist": None,
        "subnet_size": None,
        "complaints": [],
    })


def asn_result():
    return parse_response({
        "id": "22222222-2222-2222-2222-222222222222",
        "target": "AS216154",
        "target_type": "ASN",
        "blocked": True,
        "rkn_domain": None,
        "ips": ["203.0.113.1"],
        "reverse_lookup": [],
        "blocked_subnets": [],
        "cdn_providers": {},
        "geo": {
            "asn": "AS216154",
            "organisation": "Example ISP",
            "location": "Amsterdam, Netherlands",
        },
        "asn_info": {
            "asn": 216154,
            "prefixes": ["203.0.113.0/24", "2001:db8::/32", "198.51.100.0/24"],
            "blocked_prefixes": ["203.0.113.0/24", "198.51.100.0/24"],
        },
        "whitelist": None,
        "subnet_size": None,
        "complaints": [],
    })


class V4233CheburcheckHotfixTests(unittest.IsolatedAsyncioTestCase):
    async def test_geo_asn_is_enriched_by_second_read_only_check(self):
        client = CheburcheckClient("https://example.invalid")
        base = domain_result()
        enriched = asn_result()

        with patch.object(client, "check", AsyncMock(return_value=enriched)) as check:
            summary = await client.asn_summary(base)

        self.assertEqual(summary, (2, 3))
        check.assert_awaited_once_with("AS216154")

    async def test_existing_asn_result_does_not_repeat_check(self):
        client = CheburcheckClient("https://example.invalid")
        result = asn_result()

        with patch.object(client, "check", AsyncMock()) as check:
            summary = await client.asn_summary(result)

        self.assertEqual(summary, (2, 3))
        check.assert_not_awaited()

    async def test_operator_result_merges_asn_and_probe_enrichment(self):
        base = domain_result()
        regional = ProbeSummary(
            online_probes=11,
            response_count=9,
            green=7,
            red=1,
            yellow=1,
        )

        with (
            patch.object(cheburcheck_admin.client, "check", AsyncMock(return_value=base)),
            patch.object(
                cheburcheck_admin.client,
                "asn_summary",
                AsyncMock(return_value=(2, 184)),
            ),
            patch.object(
                cheburcheck_admin.client,
                "probe_summary",
                AsyncMock(return_value=regional),
            ),
        ):
            result = await cheburcheck_admin._check_result("example.org")

        self.assertEqual(result.asn_blocked_prefix_count, 2)
        self.assertEqual(result.asn_prefix_count, 184)
        self.assertEqual(result.probe_summary, regional)

    def test_empty_cdn_is_explicitly_not_found(self):
        text = cheburcheck_admin.result_text(domain_result())
        self.assertIn("CDN: 🟢 не найден", text)
        self.assertNotIn("CDN: —", text)

    def test_zero_online_probes_is_explicit(self):
        result = replace(
            domain_result(),
            asn_blocked_prefix_count=2,
            asn_prefix_count=184,
            probe_summary=ProbeSummary(
                online_probes=0,
                response_count=0,
                green=0,
                red=0,
                yellow=0,
            ),
        )
        text = cheburcheck_admin.result_text(result)
        self.assertIn("ASN: 2 / 184 подсетей в списках", text)
        self.assertIn("🌍 Регионы: ⚪ нет активных региональных сканеров", text)

    def test_supported_target_distinguishes_probe_unavailable(self):
        text = cheburcheck_admin.result_text(domain_result())
        self.assertIn("🌍 Регионы: 🟡 региональная проверка недоступна", text)

    def test_asn_target_keeps_regions_not_applicable(self):
        text = cheburcheck_admin.result_text(asn_result())
        self.assertIn("🌍 Регионы: —", text)
        self.assertNotIn("региональная проверка недоступна", text)


if __name__ == "__main__":
    unittest.main()
