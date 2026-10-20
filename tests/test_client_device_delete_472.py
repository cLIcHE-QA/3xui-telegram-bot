from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from customer_provider_xui import XuiCustomerProvider
from customer_service import (
    CustomerDevice,
    CustomerDeviceDeletePrompt,
    CustomerDeviceDeleteRejected,
    CustomerDeviceDeleteUnknown,
    CustomerDeviceInventory,
    CustomerPortalService,
    CustomerProviderUnavailable,
    DEVICE_DELETE_COOLDOWN_SECONDS,
)
from xui import XUIClient, XUIError, XUIMutationError


def inventory(*ids: int, verified: bool = True) -> CustomerDeviceInventory:
    return CustomerDeviceInventory(
        devices=tuple(CustomerDevice("Телефон", "iOS", 0, i) for i in ids),
        total=len(ids),
        verified_ids=frozenset(ids) if verified else None,
    )


class RecordingProvider:
    def __init__(self, ids=(17, 19)):
        self.ids = list(ids)
        self.supported = True
        self.fail_delete = None
        self.fail_read_after = False
        self.incomplete = False
        self.events = []

    def supports_device_delete(self) -> bool:
        return self.supported

    async def devices(self, email):
        self.events.append(("read", email))
        if self.fail_read_after and any(event[0] == "delete" for event in self.events):
            raise CustomerProviderUnavailable("private upstream exception")
        return inventory(*self.ids, verified=not self.incomplete)

    async def delete_device(self, email, device_id):
        self.events.append(("delete", email, device_id))
        await asyncio.sleep(0)
        if self.fail_delete is not None:
            raise self.fail_delete
        self.ids.remove(device_id)


def make_service(provider=None):
    db = SimpleNamespace(
        get=AsyncMock(return_value=SimpleNamespace(
            email="owned@example.invalid", expiry_time=0, sub_id="private-token",
        )),
        get_user_profile=AsyncMock(return_value=None),
    )
    provider = provider or RecordingProvider()
    svc = CustomerPortalService(
        db, SimpleNamespace(), provider,
        subscription_url_template="https://example.invalid/{sub_id}",
    )
    return svc, db, provider


class ClientDeviceDelete472Tests(unittest.IsolatedAsyncioTestCase):
    async def test_two_steps_and_exactly_one_verified_delete(self):
        service, db, provider = make_service()
        prepared = await service.prepare_device_delete(42, 17, page=2)
        self.assertIsInstance(prepared, CustomerDeviceDeletePrompt)
        self.assertEqual(prepared.device.title, "Телефон")
        self.assertNotIn("owned@example.invalid", prepared.token)
        self.assertFalse(any(e[0] == "delete" for e in provider.events))
        result = await service.confirm_device_delete(42, prepared.token)
        self.assertEqual(result.status, "deleted")
        self.assertEqual(result.page, 2)
        self.assertEqual(result.inventory.verified_ids, frozenset({19}))
        self.assertEqual(provider.events, [
            ("read", "owned@example.invalid"),
            ("read", "owned@example.invalid"),
            ("delete", "owned@example.invalid", 17),
            ("read", "owned@example.invalid"),
        ])
        self.assertEqual((await service.confirm_device_delete(42, prepared.token)).status, "stale")
        self.assertEqual(len([e for e in provider.events if e[0] == "delete"]), 1)

    async def test_cancel_only_invalidates_one_token(self):
        service, _, provider = make_service()
        prepared = await service.prepare_device_delete(42, 17, page=1)
        self.assertIsNone(await service.cancel_device_delete(43, prepared.token))
        self.assertEqual(await service.cancel_device_delete(42, prepared.token), (17, 1))
        self.assertEqual((await service.confirm_device_delete(42, prepared.token)).status, "stale")
        self.assertFalse(any(e[0] == "delete" for e in provider.events))

    async def test_forged_owner_token_device_and_changed_account(self):
        service, db, provider = make_service()
        self.assertEqual((await service.prepare_device_delete(42, 999)).status, "stale")
        self.assertEqual((await service.prepare_device_delete(42, True)).status, "stale")
        self.assertEqual((await service.prepare_device_delete(42, 2**70)).status, "stale")
        prepared = await service.prepare_device_delete(42, 17)
        self.assertEqual((await service.confirm_device_delete(43, prepared.token)).status, "stale")
        # Reassignment cannot authorize the previously issued token.
        db.get.return_value = SimpleNamespace(
            email="new-owner@example.invalid", expiry_time=0, sub_id="private",
        )
        self.assertEqual((await service.confirm_device_delete(42, prepared.token)).status, "stale")
        self.assertFalse(any(e[0] == "delete" for e in provider.events))

    async def test_account_disappears_before_confirmation(self):
        service, db, provider = make_service()
        prepared = await service.prepare_device_delete(42, 17)
        db.get.return_value = None
        self.assertEqual((await service.confirm_device_delete(42, prepared.token)).status, "stale")
        self.assertFalse(any(e[0] == "delete" for e in provider.events))

    async def test_provider_capability_and_incomplete_ids_fail_closed(self):
        provider = RecordingProvider()
        provider.supported = False
        service, _, _ = make_service(provider)
        self.assertEqual((await service.prepare_device_delete(42, 17)).status, "unsupported")
        provider.supported = True
        provider.incomplete = True
        self.assertEqual((await service.prepare_device_delete(42, 17)).status, "unavailable")
        self.assertFalse(any(e[0] == "delete" for e in provider.events))

    async def test_stale_inventory_before_confirm_does_not_mutate(self):
        service, _, provider = make_service()
        prepared = await service.prepare_device_delete(42, 17)
        provider.ids = [19]
        self.assertEqual((await service.confirm_device_delete(42, prepared.token)).status, "stale")
        self.assertFalse(any(e[0] == "delete" for e in provider.events))

    async def test_expired_token_is_not_executable(self):
        service, _, provider = make_service()
        prepared = await service.prepare_device_delete(42, 17)
        pending = service._device_delete_prompts[42]
        service._device_delete_prompts[42] = replace(pending, expires_at=0)
        self.assertEqual((await service.confirm_device_delete(42, prepared.token)).status, "stale")
        self.assertFalse(any(e[0] == "delete" for e in provider.events))

    async def test_two_concurrent_confirms_are_not_two_deletes(self):
        service, _, provider = make_service()
        prepared = await service.prepare_device_delete(42, 17)
        results = await asyncio.gather(
            service.confirm_device_delete(42, prepared.token),
            service.confirm_device_delete(42, prepared.token),
        )
        self.assertEqual(sorted(r.status for r in results), ["deleted", "stale"])
        self.assertEqual(len([e for e in provider.events if e[0] == "delete"]), 1)

    async def test_network_unknown_no_replay_and_cooldown(self):
        service, _, provider = make_service()
        provider.fail_delete = CustomerDeviceDeleteUnknown("private error")
        prepared = await service.prepare_device_delete(42, 17)
        result = await service.confirm_device_delete(42, prepared.token)
        self.assertEqual(result.status, "unknown")
        self.assertEqual((await service.confirm_device_delete(42, prepared.token)).status, "stale")
        self.assertEqual((await service.prepare_device_delete(42, 17)).status, "cooldown")
        self.assertGreater(DEVICE_DELETE_COOLDOWN_SECONDS, 0)
        self.assertEqual(len([e for e in provider.events if e[0] == "delete"]), 1)

    async def test_deterministic_rejection_separate_from_unknown(self):
        service, _, provider = make_service()
        provider.fail_delete = CustomerDeviceDeleteRejected("private error")
        prepared = await service.prepare_device_delete(42, 17)
        self.assertEqual((await service.confirm_device_delete(42, prepared.token)).status, "rejected")
        self.assertEqual(len([e for e in provider.events if e[0] == "delete"]), 1)

    async def test_postcondition_unknown_when_read_fails_or_not_complete(self):
        for mode in ("read_error", "still_present", "incomplete"):
            with self.subTest(mode=mode):
                service, _, provider = make_service()
                prepared = await service.prepare_device_delete(42, 17)
                if mode == "read_error":
                    provider.fail_read_after = True
                elif mode == "still_present":
                    provider.delete_device = AsyncMock(return_value=None)
                else:
                    async def mark_incomplete(email, did):
                        provider.events.append(("delete", email, did))
                        provider.ids.remove(did)
                        provider.incomplete = True
                    provider.delete_device = mark_incomplete
                self.assertEqual((await service.confirm_device_delete(42, prepared.token)).status, "unknown")

    async def test_opaque_confirmation_callback_and_cancel_ui(self):
        import client_access
        service, _, provider = make_service()
        call = SimpleNamespace(
            data="client:device-delete:ask:17:0",
            from_user=SimpleNamespace(id=42),
            message=SimpleNamespace(chat=SimpleNamespace(type="private")),
            answer=AsyncMock(),
        )
        with patch.object(client_access, "_guard_device_callback", new=AsyncMock(return_value=True)), \
             patch.object(client_access, "_service", return_value=service), \
             patch.object(client_access, "render_callback", new=AsyncMock()) as render:
            await client_access.device_delete_ask_cb(call)
            msg, markup = render.await_args.args[1], render.await_args.kwargs["reply_markup"]
            self.assertIn("Удалить", msg)
            self.assertNotIn("owned@example.invalid", str(markup))
            self.assertNotIn("private-token", str(markup))
            actions = [b.callback_data for row in markup.inline_keyboard for b in row]
            self.assertEqual(len(actions), 2)
            confirm = next(x for x in actions if ":confirm:" in x)
            cancel = next(x for x in actions if ":cancel:" in x)
            self.assertNotIn(":17:", confirm)
            self.assertFalse(any(e[0] == "delete" for e in provider.events))
            call.data = cancel
            await client_access.device_delete_cancel_cb(call)
            self.assertFalse(any(e[0] == "delete" for e in provider.events))
            call.data = confirm
            await client_access.device_delete_confirm_cb(call)
            self.assertIn("устарел", render.await_args.args[1].lower())
            self.assertFalse(any(e[0] == "delete" for e in provider.events))

    async def test_ui_confirmation_and_unknown_never_offer_direct_retry(self):
        import client_access
        service, _, provider = make_service()
        provider.fail_delete = CustomerDeviceDeleteUnknown("private")
        prompt = await service.prepare_device_delete(42, 17)
        call = SimpleNamespace(
            data=f"client:device-delete:confirm:{prompt.token}",
            from_user=SimpleNamespace(id=42),
            message=SimpleNamespace(chat=SimpleNamespace(type="private")),
            answer=AsyncMock(),
        )
        with patch.object(client_access, "_guard_device_callback", new=AsyncMock(return_value=True)), \
             patch.object(client_access, "_service", return_value=service), \
             patch.object(client_access, "render_callback", new=AsyncMock()) as render:
            await client_access.device_delete_confirm_cb(call)
            text, markup = render.await_args.args[1], render.await_args.kwargs["reply_markup"]
            self.assertIn("Исход DELETE не подтверждён", text)
            self.assertNotIn("private", text)
            self.assertNotIn("client:device-delete:confirm:", str(markup))
            self.assertEqual(len([e for e in provider.events if e[0] == "delete"]), 1)


class XuiDeleteAdapter472Tests(unittest.IsolatedAsyncioTestCase):
    async def test_single_success_and_capability(self):
        xui = SimpleNamespace(delete_client_hwid=AsyncMock(return_value={"success": True}))
        provider = XuiCustomerProvider(xui)
        self.assertTrue(provider.supports_device_delete())
        await provider.delete_device("owned@example.invalid", 9)
        xui.delete_client_hwid.assert_awaited_once_with("owned@example.invalid", 9)

    async def test_unknown_and_rejected_are_distinct(self):
        for uncertain, expected in ((True, CustomerDeviceDeleteUnknown), (False, CustomerDeviceDeleteRejected)):
            with self.subTest(uncertain=uncertain):
                xui = SimpleNamespace(delete_client_hwid=AsyncMock(side_effect=XUIMutationError(
                    "private", code="network_error", uncertain=uncertain,
                )))
                with self.assertRaises(expected):
                    await XuiCustomerProvider(xui).delete_device("owned@example.invalid", 9)
        xui = SimpleNamespace(delete_client_hwid=AsyncMock(return_value={}))
        with self.assertRaises(CustomerDeviceDeleteUnknown):
            await XuiCustomerProvider(xui).delete_device("owned@example.invalid", 9)

    async def test_complete_inventory_ids_required_for_delete_readback(self):
        xui = SimpleNamespace(
            client_hwids=AsyncMock(return_value=[{"id": 8}, {"id": 9}]),
            get_client=AsyncMock(return_value={"client": {"email": "owned@example.invalid", "limitHwid": 5}}),
        )
        provider = XuiCustomerProvider(xui)
        self.assertEqual((await provider.devices("owned@example.invalid")).verified_ids, frozenset({8, 9}))
        xui.client_hwids.return_value = [{"id": 8}, {"id": 8}]
        self.assertIsNone((await provider.devices("owned@example.invalid")).verified_ids)
        xui.client_hwids.return_value = [{"id": 8}, {}]
        self.assertIsNone((await provider.devices("owned@example.invalid")).verified_ids)

    async def test_xui_never_drops_invalid_rows_during_postcondition(self):
        xui = XUIClient("https://panel.example.invalid", "fake-token")
        xui._request = AsyncMock(return_value={"obj": [{"id": 2}, None]})
        with self.assertRaises(XUIError):
            await xui.client_hwids("owned@example.invalid")

    def test_client_handler_never_imports_provider_secrets(self):
        code = (Path(__file__).resolve().parents[1] / "client_access.py").read_text()
        for forbidden in ("XUIClient", "delete_client_hwid", "from xui import", "fingerprint"):
            self.assertNotIn(forbidden, code.split("DEVICE_PAGE_SIZE = 5", 1)[1].split(
                '@client_access_router.callback_query(F.data == "client:buy")', 1,
            )[0])


if __name__ == "__main__":
    unittest.main()
