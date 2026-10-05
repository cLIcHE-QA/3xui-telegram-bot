from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from subscription_proxy import SubscriptionProxy


ROOT = Path(__file__).resolve().parents[1]


class SubscriptionAccessLogAuditTests(unittest.IsolatedAsyncioTestCase):
    async def test_proxy_disables_raw_aiohttp_access_log(self):
        runner = SimpleNamespace(setup=AsyncMock(), cleanup=AsyncMock())
        site = SimpleNamespace(start=AsyncMock())

        with (
            patch("subscription_proxy.web.AppRunner", return_value=runner) as app_runner,
            patch("subscription_proxy.web.TCPSite", return_value=site),
        ):
            proxy = SubscriptionProxy(
                SimpleNamespace(),
                "https://upstream.example.invalid/sub/{sub_id}",
                "https://public.example.invalid/compat/{sub_id}",
            )
            await proxy.start()

        self.assertIsNone(app_runner.call_args.kwargs.get("access_log"))
        runner.setup.assert_awaited_once()
        site.start.assert_awaited_once()

    def test_canonical_nginx_compat_route_disables_access_log(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        block = readme.split("location /compat/ {", 1)[1].split("}", 1)[0]
        self.assertIn("access_log off;", block)
        self.assertNotIn("access_log main", block)

    def test_security_contract_treats_sub_id_as_credential(self):
        security = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
        routing = (ROOT / "docs" / "SUBSCRIPTION_ROUTING.md").read_text(encoding="utf-8")
        proxy = (ROOT / "subscription_proxy.py").read_text(encoding="utf-8")

        self.assertIn("bearer-like credentials", security)
        self.assertIn("access_log off", security)
        self.assertIn("request URI/`$request_uri`", routing)
        self.assertIn("access_log=None", proxy)
        self.assertNotIn("access_log=LOG", proxy)


if __name__ == "__main__":
    unittest.main()
