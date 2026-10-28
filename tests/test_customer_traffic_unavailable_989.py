from __future__ import annotations

import asyncio
import traceback
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

import aiohttp

from customer_provider_xui import XuiCustomerProvider
from customer_service import CustomerPortalService, CustomerProviderUnavailable, CustomerTraffic
import panel_read_budget
from xui import XUIClient, XUIError


OWNER = "owner@example.invalid"
PRIVATE_FAILURE = "synthetic-private-response https://panel.example.invalid/opaque"


class CustomerTrafficUnavailableTests(unittest.IsolatedAsyncioTestCase):
    def provider(self, client=None, traffic=None):
        return XuiCustomerProvider(SimpleNamespace(
            get_client=AsyncMock(return_value={"client": {"email": OWNER, "totalGB": 100}} if client is None else client),
            traffic=AsyncMock(return_value={"up": 2, "down": 3} if traffic is None else traffic),
            client_hwids=AsyncMock(return_value=[{"id": 1}]),
            delete_client_hwid=AsyncMock(),
        ))

    def assert_sanitized(self, error):
        self.assertEqual(str(error), "customer provider unavailable")
        formatted = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        self.assertNotIn(PRIVATE_FAILURE, formatted)
        self.assertIsNone(error.__cause__)

    async def test_transport_failures_at_either_stage_are_one_shot_and_sanitized(self):
        for stage in ("get_client", "traffic"):
            for error_type in (XUIError, aiohttp.ClientConnectionError, TimeoutError, OSError):
                with self.subTest(stage=stage, error=error_type.__name__):
                    provider = self.provider()
                    getattr(provider.xui, stage).side_effect = error_type(PRIVATE_FAILURE)
                    with self.assertRaises(CustomerProviderUnavailable) as caught:
                        await provider.traffic(OWNER)
                    self.assert_sanitized(caught.exception)
                    provider.xui.get_client.assert_awaited_once_with(OWNER)
                    self.assertEqual(provider.xui.traffic.await_count, int(stage == "traffic"))
                    provider.xui.client_hwids.assert_not_awaited()
                    provider.xui.delete_client_hwid.assert_not_awaited()

    async def test_invalid_client_shapes_stop_before_second_read(self):
        for obj in (None, [], "bad", 7, {"client": None}, {"client": []}, {"client": "bad"}):
            with self.subTest(shape=repr(obj)):
                provider = self.provider()
                provider.xui.get_client.return_value = obj
                with self.assertRaises(CustomerProviderUnavailable) as caught:
                    await provider.traffic(OWNER)
                self.assert_sanitized(caught.exception)
                provider.xui.traffic.assert_not_awaited()

    async def test_invalid_traffic_shapes_do_not_become_zero_counters(self):
        for obj in (None, [], "bad", 7):
            with self.subTest(shape=repr(obj)):
                provider = self.provider()
                provider.xui.traffic.return_value = obj
                with self.assertRaises(CustomerProviderUnavailable) as caught:
                    await provider.traffic(OWNER)
                self.assert_sanitized(caught.exception)
                provider.xui.get_client.assert_awaited_once_with(OWNER)
                provider.xui.traffic.assert_awaited_once_with(OWNER)

    async def test_counter_conversion_failures_are_unavailable(self):
        for field in ("up", "down", "totalGB"):
            for value in (PRIVATE_FAILURE, [1], {"bad": 1}, float("inf"), float("nan")):
                with self.subTest(field=field, value=repr(value)):
                    provider = self.provider()
                    if field == "totalGB":
                        provider.xui.get_client.return_value["client"][field] = value
                    else:
                        provider.xui.traffic.return_value[field] = value
                    with self.assertRaises(CustomerProviderUnavailable) as caught:
                        await provider.traffic(OWNER)
                    self.assert_sanitized(caught.exception)
                    provider.xui.get_client.assert_awaited_once_with(OWNER)
                    provider.xui.traffic.assert_awaited_once_with(OWNER)

    async def test_successful_nested_direct_alias_and_zero_contract(self):
        cases = [
            ({"client": {"totalGB": "100"}}, {"up": "2", "down": "3"}, (2, 3, 100)),
            ({"totalGB": 90}, {"uplink": 4, "downlink": 5}, (4, 5, 90)),
            ({"totalGB": 0}, {"up": 0, "down": 0}, (0, 0, 0)),
            ({}, {}, (0, 0, 0)),
        ]
        for client, counters, expected in cases:
            with self.subTest(expected=expected):
                provider = self.provider(client, counters)
                result = await provider.traffic(OWNER)
                self.assertIs(type(result), CustomerTraffic)
                self.assertEqual((result.up, result.down, result.total), expected)
                provider.xui.get_client.assert_awaited_once_with(OWNER)
                provider.xui.traffic.assert_awaited_once_with(OWNER)

    async def test_cancellation_is_preserved_at_both_awaits(self):
        for stage in ("get_client", "traffic"):
            provider = self.provider()
            cancellation = asyncio.CancelledError()
            getattr(provider.xui, stage).side_effect = cancellation
            with self.assertRaises(asyncio.CancelledError) as caught:
                await provider.traffic(OWNER)
            self.assertIs(caught.exception, cancellation)
            self.assertEqual(provider.xui.traffic.await_count, int(stage == "traffic"))

    async def test_unexpected_programming_errors_are_not_masked(self):
        for stage in ("get_client", "traffic"):
            provider = self.provider()
            programming_error = RuntimeError("synthetic programming defect")
            getattr(provider.xui, stage).side_effect = programming_error
            with self.assertRaises(RuntimeError) as caught:
                await provider.traffic(OWNER)
            self.assertIs(caught.exception, programming_error)

    async def test_devices_retain_existing_inventory_and_unknown_limit_contract(self):
        for error_type in (aiohttp.ClientConnectionError, TimeoutError, OSError):
            provider = self.provider()
            provider.xui.client_hwids.side_effect = error_type("synthetic")
            with self.assertRaises(CustomerProviderUnavailable):
                await provider.devices(OWNER)
            provider.xui.get_client.assert_not_awaited()
            provider = self.provider()
            provider.xui.get_client.side_effect = error_type("synthetic")
            inventory = await provider.devices(OWNER)
            self.assertEqual(inventory.total, 1)
            self.assertEqual(inventory.verified_ids, frozenset({1}))
            self.assertEqual(inventory.limit_state, "unknown")
            self.assertIsNone(inventory.limit)
            provider.xui.delete_client_hwid.assert_not_awaited()

    async def test_service_to_existing_ui_unavailable_panel_keeps_owner_and_back(self):
        import client_access

        provider = self.provider()
        provider.xui.traffic.side_effect = aiohttp.ClientConnectionError(PRIVATE_FAILURE)
        service = CustomerPortalService(SimpleNamespace(), SimpleNamespace(), provider, subscription_url_template="")
        profile = AsyncMock(return_value=SimpleNamespace(exists=True, email=OWNER))
        call = SimpleNamespace(from_user=SimpleNamespace(id=10), answer=AsyncMock())
        with patch.object(service, "profile", profile), patch.object(
            client_access, "guard_callback", AsyncMock(return_value=True)
        ), patch.object(client_access, "_service", return_value=service), patch.object(
            client_access, "render_callback", AsyncMock()
        ) as rendered:
            await client_access.traffic_cb(call)
        profile.assert_awaited_once_with(10, read_access=False)
        provider.xui.get_client.assert_awaited_once_with(OWNER)
        provider.xui.traffic.assert_awaited_once_with(OWNER)
        text = rendered.await_args.args[1]
        self.assertIn("Данные провайдера временно недоступны", text)
        self.assertNotIn(PRIVATE_FAILURE, text)
        self.assertNotIn("Использовано:", text)
        buttons = rendered.await_args.kwargs["reply_markup"].inline_keyboard
        self.assertEqual(buttons[0][0].callback_data, "client:home")
        call.answer.assert_awaited_once()
        provider.xui.delete_client_hwid.assert_not_awaited()

    async def test_missing_profile_and_rejected_ui_guard_do_not_read_provider(self):
        import client_access

        provider = self.provider()
        service = CustomerPortalService(SimpleNamespace(), SimpleNamespace(), provider, subscription_url_template="")
        with patch.object(service, "profile", AsyncMock(return_value=SimpleNamespace(exists=False))):
            self.assertIsNone(await service.traffic(10))
        call = SimpleNamespace(from_user=SimpleNamespace(id=10), answer=AsyncMock())
        with patch.object(client_access, "guard_callback", AsyncMock(return_value=False)), patch.object(
            client_access, "_service", return_value=service
        ) as factory, patch.object(client_access, "render_callback", AsyncMock()) as rendered:
            await client_access.traffic_cb(call)
        factory.assert_not_called()
        rendered.assert_not_awaited()
        provider.xui.get_client.assert_not_awaited()
        provider.xui.traffic.assert_not_awaited()

    async def test_real_xui_read_path_releases_budget_and_sessions_without_retries(self):
        for failed_path in ("/get/", "/traffic/"):
            calls, sessions, closed = [], [], []

            class Response:
                status = 200

                async def __aenter__(self):
                    if failed_path in calls[-1][1]:
                        raise aiohttp.ClientConnectionError(PRIVATE_FAILURE)
                    return self

                async def __aexit__(self, *args):
                    return False

                async def text(self):
                    return "synthetic JSON"

                async def json(self, **kwargs):
                    return {"success": True, "obj": {"client": {"totalGB": 100}}}

            class Session:
                def __init__(self, **kwargs):
                    sessions.append(kwargs)

                async def __aenter__(self):
                    return self

                async def __aexit__(self, *args):
                    closed.append(True)
                    return False

                def request(self, method, url, **kwargs):
                    calls.append((method, url, kwargs))
                    return Response()

            client = XUIClient("https://panel.example.invalid", "synthetic", verify_tls=True)
            with patch.object(aiohttp, "ClientSession", Session):
                with self.assertRaises(CustomerProviderUnavailable) as caught:
                    await XuiCustomerProvider(client).traffic(OWNER)
            self.assert_sanitized(caught.exception)
            expected_count = 1 if failed_path == "/get/" else 2
            self.assertEqual(len(calls), expected_count)
            self.assertEqual(len(sessions), expected_count)
            self.assertEqual(len(closed), expected_count)
            self.assertTrue(all(method == "GET" and options["ssl"] is None for method, _, options in calls))
            snapshot = panel_read_budget.read_budget_snapshot()
            self.assertEqual(snapshot["active"], 0)
            self.assertEqual(snapshot["targets"], 0)


if __name__ == "__main__":
    unittest.main()
