from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from xui import XUIClient


class V410NativeControlEndpointTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.client = XUIClient(
            "https://panel.example.invalid/base",
            "offline-test-token",
            verify_tls=True,
        )

    async def test_restart_xray_uses_native_forced_restart_endpoint(self):
        request = AsyncMock(return_value={"success": True})
        with patch.object(self.client, "_mutation_request", new=request):
            await self.client.restart_xray()
        request.assert_awaited_once_with("/panel/api/server/restartXrayService")

    async def test_stop_xray_uses_native_stop_endpoint(self):
        request = AsyncMock(return_value={"success": True})
        with patch.object(self.client, "_mutation_request", new=request):
            await self.client.stop_xray()
        request.assert_awaited_once_with("/panel/api/server/stopXrayService")

    async def test_restart_panel_uses_native_soft_restart_endpoint(self):
        request = AsyncMock(return_value={"success": True})
        with patch.object(self.client, "_mutation_request", new=request):
            await self.client.restart_panel()
        request.assert_awaited_once_with("/panel/api/setting/restartPanel")


if __name__ == "__main__":
    unittest.main()
