from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from customer_provider_xui import XuiCustomerProvider
from customer_service import CustomerDevice, CustomerDeviceInventory, CustomerPortalService, CustomerProviderUnavailable
from xui import XUIClient, XUIError


class DeviceInventory471Tests(unittest.IsolatedAsyncioTestCase):
    def provider(self, rows, limit=5):
        return XuiCustomerProvider(SimpleNamespace(
            client_hwids=AsyncMock(return_value=rows),
            get_client=AsyncMock(return_value={"client": {"email": "owned@example.invalid", "limitHwid": limit}}),
        ))

    async def test_verified_real_ids_and_positive_limit(self):
        adapter = self.provider([
            {"id": 7, "deviceModel": "Pixel 9", "deviceOs": "Android", "lastSeen": 1735000000000},
            {"id": 8, "deviceModel": "Windows", "deviceOs": "Windows"},
        ])
        inventory = await adapter.devices("owned@example.invalid")
        self.assertEqual(inventory.total, 2)
        self.assertEqual(inventory.limit, 5)
        self.assertEqual(inventory.limit_state, "known")
        self.assertEqual([d.device_id for d in inventory.devices], [7, 8])
        adapter.xui.client_hwids.assert_awaited_once_with("owned@example.invalid")

    async def test_missing_disabled_and_unreachable_limit(self):
        for limit, expected in [(None, "unknown"), (0, "disabled"), (-1, "unknown"), ("garbage", "unknown")]:
            with self.subTest(limit=limit):
                obj = await self.provider([], limit=limit).devices("owned@example.invalid")
                self.assertIsNone(obj.limit)
                self.assertEqual(obj.limit_state, expected)
        adapter = self.provider([{"id": 3}], limit=5)
        adapter.xui.get_client.side_effect = XUIError("private provider failure")
        obj = await adapter.devices("owned@example.invalid")
        self.assertEqual(obj.total, 1)
        self.assertEqual(obj.limit_state, "unknown")

    async def test_missing_duplicate_and_oversized_ids_do_not_forge_identity(self):
        rows = [
            {"id": "3", "deviceModel": "Phone", "deviceOs": "iOS"},
            {"id": 3, "deviceModel": "Phone"},
            {"id": None, "deviceModel": "Unknown"},
            {"id": 2**70, "deviceModel": "Unknown"},
            {"id": True, "deviceModel": "Unknown"},
            {"id": 9, "deviceModel": "<b>bad</b>", "deviceOs": "Android"},
        ]
        devices = (await self.provider(rows).devices("owned@example.invalid")).devices
        self.assertEqual([d.device_id for d in devices], [None, None, None, None, None, 9])
        self.assertEqual(devices[-1].title, "Android")

    async def test_large_inventory_truncated_and_duplicate_outside_window(self):
        rows = [{"id": i + 1, "deviceModel": "Phone"} for i in range(119)]
        rows[-1]["id"] = 1
        inventory = await self.provider(rows).devices("owned@example.invalid")
        self.assertEqual(inventory.total, 119)
        self.assertTrue(inventory.truncated)
        self.assertEqual(len(inventory.devices), 100)
        self.assertIsNone(inventory.devices[0].device_id)

    async def test_corrupt_inventory_fails_closed(self):
        for rows in (None, [None], "bad", [{}] * 1001):
            with self.subTest(rows=type(rows)):
                with self.assertRaises(CustomerProviderUnavailable):
                    await self.provider(rows).devices("owned@example.invalid")

    async def test_xui_invalid_response_not_empty(self):
        client = XUIClient("https://panel.example.invalid", "token")
        for obj in (None, {}, [None]):
            client._request = AsyncMock(return_value={"obj": obj})
            with self.assertRaises(XUIError):
                await client.client_hwids("owned@example.invalid")

    async def test_customer_service_resolves_owner_on_each_inventory_read(self):
        db = SimpleNamespace(get=AsyncMock(return_value=SimpleNamespace(
            email="owned@example.invalid", expiry_time=0, sub_id="secret",
        )), get_user_profile=AsyncMock(return_value=None))
        inventory = CustomerDeviceInventory(devices=(CustomerDevice("Phone", "iOS", 0, 7),), total=1)
        provider = SimpleNamespace(devices=AsyncMock(return_value=inventory))
        service = CustomerPortalService(db, SimpleNamespace(), provider, subscription_url_template="https://example.invalid/{sub_id}")
        self.assertEqual((await service.devices(17)).devices[0].device_id, 7)
        provider.devices.assert_awaited_once_with("owned@example.invalid")
        db.get.return_value = None
        self.assertIsNone(await service.devices(99))
        provider.devices.assert_awaited_once()

    async def test_list_pagination_unknown_and_private_detail(self):
        import client_access
        devices = tuple(CustomerDevice("Phone", "iOS", 0, i + 1) for i in range(12))
        inventory = CustomerDeviceInventory(devices=devices, total=12)
        text, keyboard = client_access._device_list_view(inventory, 1)
        self.assertIn("Лимит HWID: UNKNOWN", text)
        self.assertIn("Страница 2/3", text)
        self.assertNotIn("client:device:1:1", str(keyboard))
        self.assertIn("client:device:6:1", str(keyboard))
        self.assertLess(len(text), 1000)

    async def test_detail_rechecks_owner_and_stale_id(self):
        import client_access
        data = CustomerDeviceInventory(devices=(CustomerDevice("Phone", "iOS", 0, 9),), total=1)
        svc = SimpleNamespace(devices=AsyncMock(return_value=data))
        call = SimpleNamespace(
            data="client:device:7:0", from_user=SimpleNamespace(id=17),
            message=SimpleNamespace(chat=SimpleNamespace(type="private")),
            answer=AsyncMock(),
        )
        with patch.object(client_access, "_guard_device_callback", new=AsyncMock(return_value=True)), \
             patch.object(client_access, "_service", return_value=svc), \
             patch.object(client_access, "render_callback", new=AsyncMock()) as render:
            await client_access.device_detail_cb(call)
            self.assertIn("устарела", render.await_args.args[1])
            svc.devices.assert_awaited_once_with(17)
            call.data = "client:device:9:0"
            await client_access.device_detail_cb(call)
            self.assertIn("Phone", render.await_args.args[1])

    async def test_non_private_callbacks_rejected(self):
        import client_access
        call = SimpleNamespace(message=SimpleNamespace(chat=SimpleNamespace(type="group")), answer=AsyncMock())
        with patch.object(client_access, "guard_callback", new=AsyncMock(return_value=True)):
            self.assertFalse(await client_access._guard_device_callback(call))
        call.answer.assert_awaited_once()

    def test_no_device_mutation_or_fingerprint_in_client_ui(self):
        source = (Path(__file__).resolve().parents[1] / "client_access.py").read_text()
        segment = source.split("DEVICE_PAGE_SIZE = 5", 1)[1].split('@client_access_router.callback_query(F.data == "client:buy")', 1)[0]
        for forbidden in ("delete_client_hwid", "fingerprint", "client_ips", "XUIClient"):
            self.assertNotIn(forbidden, segment)


if __name__ == "__main__":
    unittest.main()
