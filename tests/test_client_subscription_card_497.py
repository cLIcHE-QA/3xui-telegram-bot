"""#497: изолированная матрица read-only карточки подписки и private ownership."""
from __future__ import annotations

import time
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from customer_service import (
    CustomerPortalService,
    CustomerProfile,
    CustomerSubscriptionCard,
    CustomerProviderAccess,
    CustomerProviderUnavailable,
)
from customer_provider_xui import XuiCustomerProvider


def make_customer(*, status="active", enabled=True, expiry=None,
                  plan="Пилот", sub_id="owned-sub", outage=False):
    if expiry is None:
        expiry = (int(time.time()) + 3600) * 1000
    record = SimpleNamespace(
        email="owned@example.invalid", expiry_time=expiry, sub_id=sub_id,
    )
    entitlement = SimpleNamespace(status=status, expires_at=expiry // 1000)
    db = SimpleNamespace(
        get=AsyncMock(return_value=record),
        get_user_profile=AsyncMock(return_value=SimpleNamespace(
            display_name="Клиент", plan_id=7,
        )),
        get_plan=AsyncMock(return_value=SimpleNamespace(name=plan)),
        get_latest_entitlement_for_user=AsyncMock(return_value=entitlement),
    )
    provider = SimpleNamespace(
        access=AsyncMock(
            side_effect=CustomerProviderUnavailable("offline") if outage else None,
            return_value=CustomerProviderAccess(
                enabled=enabled, expiry_time=expiry, master_inbounds=2,
            ),
        ),
        devices=AsyncMock(),
        traffic=AsyncMock(),
        delete_device=AsyncMock(),
    )
    commerce = SimpleNamespace(
        create_order=AsyncMock(),
        confirm_payment=AsyncMock(),
    )
    service = CustomerPortalService(
        db, commerce, provider,
        subscription_url_template="https://sub.example.invalid/compat/{sub_id}",
    )
    return service, db, provider, commerce


class CustomerSubscriptionCard497Tests(unittest.IsolatedAsyncioTestCase):
    async def test_owned_snapshot_is_read_only_and_preserves_subscription_identity(self):
        service, db, provider, commerce = make_customer()
        before = await service.subscription_url(42)
        card = await service.subscription_card(42)
        self.assertEqual(card.url, before)
        self.assertEqual(card.url, "https://sub.example.invalid/compat/owned-sub")
        self.assertEqual(card.profile.access_status, "active")
        self.assertEqual(card.profile.period_status, "active")
        self.assertEqual(card.profile.expiry_comparison, "match")
        self.assertEqual(card.profile.master_inbounds, 2)
        self.assertIsNone(card.profile.available_locations)
        provider.access.assert_awaited_once_with("owned@example.invalid")
        provider.delete_device.assert_not_awaited()
        provider.traffic.assert_not_awaited()
        provider.devices.assert_not_awaited()
        commerce.create_order.assert_not_awaited()
        commerce.confirm_payment.assert_not_awaited()
        db.get.assert_awaited_with(42)

    async def test_no_account_never_reads_provider_or_builds_url(self):
        service, db, provider, commerce = make_customer()
        db.get.return_value = None
        card = await service.subscription_card(42)
        self.assertFalse(card.profile.exists)
        self.assertIsNone(card.url)
        db.get_user_profile.assert_not_awaited()
        db.get_latest_entitlement_for_user.assert_not_awaited()
        provider.access.assert_not_awaited()
        commerce.create_order.assert_not_awaited()

    async def test_invalid_subscription_identity_is_not_renderable(self):
        for value in ("", "../other", "token with spaces", "a" * 129):
            with self.subTest(sub_id=value[:20]):
                service, _, _, _ = make_customer(sub_id=value)
                self.assertIsNone((await service.subscription_card(42)).url)
                self.assertIsNone(await service.subscription_url(42))

    async def test_state_matrix_never_promotes_unknown_to_active(self):
        cases = [
            ("active", True, False, "active"),
            ("active", False, False, "disabled"),
            ("expired", True, False, "expired"),
            ("pending", True, False, "provisioning"),
            ("provisioning", True, False, "provisioning"),
            ("failed", True, False, "unknown"),
            ("suspended", True, False, "suspended"),
            ("invalid_future_status", True, False, "unknown"),
            ("active", True, True, "unknown"),
        ]
        for state, enabled, outage, expected in cases:
            with self.subTest(state=state, enabled=enabled, outage=outage):
                service, _, _, _ = make_customer(
                    status=state, enabled=enabled, outage=outage,
                )
                self.assertEqual(
                    (await service.subscription_card(42)).profile.access_status,
                    expected,
                )

    async def test_expired_legacy_local_evidence_remains_expired(self):
        service, db, _, _ = make_customer(
            status="active",
            expiry=(int(time.time()) - 60) * 1000,
        )
        card = await service.subscription_card(42)
        self.assertEqual(card.profile.access_status, "expired")
        self.assertTrue(card.profile.expiry_known)

    async def test_provider_inbound_count_requires_exact_owner_and_valid_unique_ids(self):
        for ids, owner, expected in [
            ([4, 5], "owned@example.invalid", 2),
            ([], "owned@example.invalid", 0),
            ([1, 1], "owned@example.invalid", None),
            ([True, 2], "owned@example.invalid", None),
            ([1, "2"], "owned@example.invalid", None),
            ([1, 2], "another@example.invalid", None),
            (None, "owned@example.invalid", None),
        ]:
            with self.subTest(ids=ids, owner=owner):
                response = {
                    "client": {
                        "email": owner, "enable": True,
                        "expiryTime": 0,
                    },
                }
                if ids is not None:
                    response["inboundIds"] = ids
                xui = SimpleNamespace(get_client=AsyncMock(return_value=response))
                if owner != "owned@example.invalid":
                    with self.assertRaises(CustomerProviderUnavailable):
                        await XuiCustomerProvider(xui).access("owned@example.invalid")
                else:
                    access = await XuiCustomerProvider(xui).access("owned@example.invalid")
                    self.assertEqual(access.master_inbounds, expected)
                    self.assertIsNone(access.available_locations)
                xui.get_client.assert_awaited_once_with("owned@example.invalid")


class CustomerSubscriptionCardUI497Tests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def card(**changes):
        profile = CustomerProfile(
            exists=True, plan_name="Пилот",
            access_status="active", period_status="active",
            expiry_time=(int(time.time()) + 3600) * 1000,
            expiry_known=True, expiry_comparison="match",
            master_inbounds=3, **changes,
        )
        return CustomerSubscriptionCard(
            profile=profile,
            url="https://sub.example.invalid/compat/owned-sub",
        )

    def test_copy_action_only_uses_safe_url_and_no_plaintext_callback_identity(self):
        import client_access as ui
        card = self.card()
        text = ui.subscription_card_text(card)
        self.assertIn("VPN-доступ: 🟢 доступен", text)
        self.assertIn("Доступные серверы/локации: не подтверждено", text)
        self.assertIn("Привязки Master Inbounds: 3", text)
        self.assertIn("https://sub.example.invalid/compat/owned-sub", text)
        keyboard = ui.subscription_card_menu(card, can_buy=True).inline_keyboard
        self.assertEqual(keyboard[0][0].copy_text.text, card.url)
        callbacks = [button.callback_data for row in keyboard for button in row if button.callback_data]
        self.assertIn("client:onboard:subscription", callbacks)
        self.assertIn("client:buy", callbacks)
        self.assertIn("client:home", callbacks)
        self.assertFalse(any("owned" in data or "42" in data for data in callbacks))
        self.assertEqual(ui.onboarding_menu(
            subscription_origin=True,
        ).inline_keyboard[-1][0].callback_data, "client:subscription")
        self.assertEqual(ui.onboarding_menu().inline_keyboard[-1][0].callback_data, "client:help")

    def test_no_account_malformed_url_and_payment_off(self):
        import client_access as ui
        empty = CustomerSubscriptionCard(CustomerProfile(exists=False), None)
        self.assertIn("Доступ пока не оформлен", ui.subscription_card_text(empty))
        self.assertEqual(
            [row[0].callback_data for row in ui.subscription_card_menu(
                empty, can_buy=True,
            ).inline_keyboard],
            ["client:home"],
        )
        bad = CustomerSubscriptionCard(self.card().profile, "http://host.invalid/id")
        rows = ui.subscription_card_menu(bad, can_buy=False).inline_keyboard
        self.assertFalse(any(button.copy_text for row in rows for button in row))
        self.assertFalse(any(
            button.callback_data == "client:buy"
            for row in rows for button in row
        ))

    def test_long_untrusted_text_never_leaks_into_card(self):
        import client_access as ui
        raw = "X" * 300 + "\u2028" + "<admin>"
        profile = CustomerProfile(
            exists=True, plan_name=raw, access_status="unknown",
            period_status="provisioning", expiry_known=False,
        )
        text = ui.subscription_card_text(CustomerSubscriptionCard(
            profile=profile, url="https://example.invalid/path\nspoof",
        ))
        self.assertNotIn(raw, text)
        self.assertNotIn("https://example.invalid/path", text)
        self.assertIn("Тариф: не назначен", text)
        self.assertIn("срок не подтверждён", text)
        self.assertIn("Активация: 🟡 выполняется активация", text)
        self.assertIn("статус неизвестен", text)

    async def test_group_and_wrong_chat_fail_before_owner_data_read(self):
        import client_access as ui
        for chat_type, chat_id in (("group", 42), ("private", 1001), ("supergroup", 42)):
            with self.subTest(chat_type=chat_type, chat_id=chat_id):
                service = SimpleNamespace(subscription_card=AsyncMock())
                call = SimpleNamespace(
                    data="client:subscription",
                    from_user=SimpleNamespace(id=42),
                    message=SimpleNamespace(chat=SimpleNamespace(type=chat_type, id=chat_id)),
                    answer=AsyncMock(),
                )
                message = SimpleNamespace(
                    from_user=SimpleNamespace(id=42),
                    chat=call.message.chat,
                    answer=AsyncMock(),
                )
                with patch.object(ui, "guard_callback", new=AsyncMock(return_value=True)), \
                     patch.object(ui, "guard_message", new=AsyncMock(return_value=True)), \
                     patch.object(ui, "_service", return_value=service):
                    await ui.subscription_cb(call)
                    await ui.subscription_cmd(message)
                service.subscription_card.assert_not_awaited()
                call.answer.assert_awaited_once()
                message.answer.assert_awaited_once()

    async def test_owner_private_message_and_callback_render_single_snapshot(self):
        import client_access as ui
        card = self.card()
        service = SimpleNamespace(subscription_card=AsyncMock(return_value=card))
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=42),
            chat=SimpleNamespace(type="private", id=42),
            answer=AsyncMock(),
        )
        call = SimpleNamespace(
            data="client:subscription",
            from_user=SimpleNamespace(id=42),
            message=SimpleNamespace(chat=message.chat),
            answer=AsyncMock(),
        )
        with patch.object(ui, "guard_callback", new=AsyncMock(return_value=True)), \
             patch.object(ui, "guard_message", new=AsyncMock(return_value=True)), \
             patch.object(ui, "payment_acceptance_enabled", new=AsyncMock(return_value=False)), \
             patch.object(ui, "_service", return_value=service), \
             patch.object(ui, "render_callback", new=AsyncMock()) as render:
            await ui.subscription_cmd(message)
            await ui.subscription_cb(call)
        self.assertEqual(service.subscription_card.await_count, 2)
        self.assertTrue(all(args.args == (42,) for args in service.subscription_card.await_args_list))
        self.assertIn("VPN-доступ:", message.answer.await_args.args[0])
        self.assertIn("VPN-доступ:", render.await_args.args[1])
        self.assertFalse(any(
            button.callback_data == "client:buy"
            for row in render.await_args.kwargs["reply_markup"].inline_keyboard
            for button in row
        ))

    async def test_portal_off_short_circuits_before_any_subscription_data(self):
        import client_access as ui
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=42),
            chat=SimpleNamespace(type="private", id=42),
            answer=AsyncMock(),
        )
        call = SimpleNamespace(
            from_user=SimpleNamespace(id=42),
            data="client:subscription",
            message=SimpleNamespace(chat=message.chat),
            answer=AsyncMock(),
        )
        service = SimpleNamespace(subscription_card=AsyncMock())
        flags = SimpleNamespace(snapshot=AsyncMock(return_value=SimpleNamespace(portal_enabled=False)))
        with patch.object(ui, "feature_flags", flags), \
             patch.object(ui, "_service", return_value=service):
            await ui.subscription_cmd(message)
            await ui.subscription_cb(call)
        service.subscription_card.assert_not_awaited()
        message.answer.assert_awaited_once_with("Личный кабинет временно отключён.")
        call.answer.assert_awaited_once()

    async def test_qr_rejects_wrong_chat_without_credential_lookup(self):
        import client_access as ui
        call = SimpleNamespace(
            data="client:onboard:subscription:qr",
            from_user=SimpleNamespace(id=42),
            message=SimpleNamespace(chat=SimpleNamespace(type="supergroup", id=88)),
            answer=AsyncMock(),
        )
        service = SimpleNamespace(subscription_url=AsyncMock())
        with patch.object(ui, "guard_callback", new=AsyncMock(return_value=True)), \
             patch.object(ui, "_service", return_value=service):
            await ui.onboarding_platform_cb(call)
        service.subscription_url.assert_not_awaited()
        call.answer.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
