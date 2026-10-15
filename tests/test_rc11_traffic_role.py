from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

_TEST_ENV = {
    "BOT_TOKEN": "123456789:offline-test-token",
    "PANEL_URL": "https://panel.example.invalid/base",
    "PANEL_API_TOKEN": "offline-panel-token",
    "SUBSCRIPTION_URL_TEMPLATE": "https://sub.example.invalid/sub/{sub_id}",
    "ALLOWED_TELEGRAM_IDS": "1",
    "ADMIN_TELEGRAM_IDS": "1",
    "NODE_BACKUP_TARGETS": "",
    "HOST_CONTROL_TARGETS": "",
    "DB_PATH": "/tmp/rc11-traffic-role-test.sqlite3",
}
with patch.dict(os.environ, _TEST_ENV, clear=False):
    import admin_observability as target


class TrafficRoleRegressionTests(unittest.IsolatedAsyncioTestCase):
    async def test_success_for_read_only_role(self):
        call = SimpleNamespace(answer=AsyncMock())
        with (
            patch.object(target, "authorize_callback", new_callable=AsyncMock, return_value=(True, "read_only")),
            patch.object(target.xui, "clients_list", new_callable=AsyncMock, return_value=[]),
            patch.object(target.db, "list_users", new_callable=AsyncMock, return_value=[]),
            patch.object(target, "render_callback", new_callable=AsyncMock) as render,
        ):
            await target.traffic_view(call)
        text = render.await_args.args[1]
        self.assertIn("📊 Трафик", text)
        self.assertIn("данных пока нет", text)
        kb = render.await_args.kwargs["reply_markup"]
        self.assertEqual(
            {button.callback_data for row in kb.inline_keyboard for button in row},
            {"admin:traffic", "admin:section:monitoring"},
        )

    async def test_denied_role_does_not_call_provider(self):
        call = SimpleNamespace(answer=AsyncMock())
        with (
            patch.object(target, "authorize_callback", new_callable=AsyncMock, return_value=(False, None)),
            patch.object(target.xui, "clients_list", new_callable=AsyncMock) as clients,
            patch.object(target, "render_callback", new_callable=AsyncMock) as render,
        ):
            await target.traffic_view(call)
        clients.assert_not_awaited()
        render.assert_not_awaited()

    async def test_upstream_error_has_navigation(self):
        call = SimpleNamespace(answer=AsyncMock())
        with (
            patch.object(target, "authorize_callback", new_callable=AsyncMock, return_value=(True, "owner")),
            patch.object(target.xui, "clients_list", new_callable=AsyncMock, side_effect=target.XUIError("offline")),
            patch.object(target, "render_callback", new_callable=AsyncMock) as render,
        ):
            await target.traffic_view(call)
        self.assertIn("3x-ui: offline", render.await_args.args[1])
        buttons = render.await_args.kwargs["reply_markup"].inline_keyboard
        self.assertEqual(buttons[0][0].callback_data, "admin:section:monitoring")


if __name__ == "__main__":
    unittest.main()
