from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Protocol

from checkout_service import CheckoutService, CheckoutSession
from commerce import CommerceService
from db import CommerceOrderRecord, Database, PlanRecord


class CustomerProviderUnavailable(RuntimeError):
    """Customer-facing provider read failed without exposing provider details."""


@dataclass(frozen=True)
class CustomerTraffic:
    up: int
    down: int
    total: int


@dataclass(frozen=True)
class CustomerDevice:
    title: str
    os_name: str
    last_seen: int


@dataclass(frozen=True)
class CustomerProfile:
    exists: bool
    email: str = ""
    display_name: str = ""
    plan_name: str = ""
    expiry_time: int = 0
    sub_id: str = ""
    access_status: str = "missing"


@dataclass(frozen=True)
class CustomerDiagnostics:
    account_exists: bool
    entitlement_status: str = ""
    subscription_available: bool = False
    provider_reachable: bool | None = None
    note: str = ""


class CustomerAccessProvider(Protocol):
    async def traffic(self, email: str) -> CustomerTraffic: ...

    async def devices(self, email: str) -> list[CustomerDevice]: ...


class CustomerPortalService:
    """Provider-neutral domain boundary for the Telegram Client Portal."""

    def __init__(
        self,
        db: Database,
        commerce: CommerceService,
        provider: CustomerAccessProvider,
        *,
        subscription_url_template: str,
        checkout: CheckoutService | None = None,
    ):
        self.db = db
        self.commerce = commerce
        self.provider = provider
        self.subscription_url_template = subscription_url_template
        self.checkout = checkout

    async def profile(self, telegram_id: int) -> CustomerProfile:
        rec = await self.db.get(telegram_id)
        if rec is None:
            return CustomerProfile(exists=False)
        profile = await self.db.get_user_profile(telegram_id)
        plan = await self.db.get_plan(profile.plan_id) if profile and profile.plan_id else None
        expiry_time = int(rec.expiry_time or 0)
        now_ms = int(time.time() * 1000)
        access_status = (
            "expired"
            if expiry_time > 0 and expiry_time <= now_ms
            else "active"
        )
        return CustomerProfile(
            exists=True,
            email=rec.email,
            display_name=getattr(profile, "display_name", "") or "",
            plan_name=plan.name if plan else "",
            expiry_time=expiry_time,
            sub_id=rec.sub_id,
            access_status=access_status,
        )

    async def subscription_url(self, telegram_id: int) -> str | None:
        profile = await self.profile(telegram_id)
        if not profile.exists:
            return None
        return self.subscription_url_template.format(sub_id=profile.sub_id)

    async def traffic(self, telegram_id: int) -> CustomerTraffic | None:
        profile = await self.profile(telegram_id)
        if not profile.exists:
            return None
        return await self.provider.traffic(profile.email)

    async def devices(self, telegram_id: int) -> list[CustomerDevice] | None:
        profile = await self.profile(telegram_id)
        if not profile.exists:
            return None
        return await self.provider.devices(profile.email)

    async def diagnostics(self, telegram_id: int) -> CustomerDiagnostics:
        profile = await self.profile(telegram_id)
        if not profile.exists:
            return CustomerDiagnostics(
                account_exists=False,
                note="Клиентский аккаунт ещё не оформлен.",
            )
        entitlement = await self.db.get_latest_entitlement_for_user(telegram_id)
        now = int(time.time())
        if entitlement is not None:
            entitlement_status = entitlement.status
            entitlement_expires_at = int(getattr(entitlement, "expires_at", 0) or 0)
            if (
                entitlement_status in {"active", "suspended"}
                and entitlement_expires_at > 0
                and entitlement_expires_at <= now
            ):
                entitlement_status = "expired"
        else:
            entitlement_status = (
                "expired" if profile.access_status == "expired" else "legacy"
            )
        provider_reachable: bool | None = None
        try:
            await self.provider.traffic(profile.email)
            provider_reachable = True
        except CustomerProviderUnavailable:
            provider_reachable = False
        return CustomerDiagnostics(
            account_exists=True,
            entitlement_status=entitlement_status,
            subscription_available=bool(profile.sub_id),
            provider_reachable=provider_reachable,
            note=(
                "Для legacy-доступа entitlement journal может отсутствовать."
                if entitlement is None
                else ""
            ),
        )

    async def active_plans(self) -> list[PlanRecord]:
        return [plan for plan in await self.db.list_plans() if plan.active]

    async def active_plan(self, plan_id: int) -> PlanRecord | None:
        plan = await self.db.get_plan(plan_id)
        return plan if plan is not None and plan.active else None

    async def has_accepted_terms(self, telegram_id: int, terms_version: str) -> bool:
        return await self.db.has_customer_accepted_terms(
            telegram_id=telegram_id,
            terms_version=terms_version,
        )

    async def accept_terms(self, telegram_id: int, terms_version: str) -> None:
        await self.db.accept_customer_terms(
            telegram_id=telegram_id,
            terms_version=terms_version,
        )

    async def get_or_create_stars_order(
        self, *, telegram_id: int, plan: PlanRecord,
    ):
        if int(plan.stars_price or 0) <= 0:
            raise ValueError("plan has no Telegram Stars price")
        profile = await self.profile(telegram_id)
        if not profile.exists:
            raise ValueError("customer account does not exist")
        order, created = await self.commerce.get_or_create_order(
            telegram_id=telegram_id,
            plan_id=plan.id,
            amount_minor=int(plan.stars_price),
            currency="XTR",
        )
        order = await self.commerce.mark_order_awaiting_payment(order.id)
        return order, created

    async def validate_stars_precheckout(
        self, *, telegram_id: int, order_id: int, amount: int,
    ) -> bool:
        order = await self.commerce.get_order(order_id)
        if order is None:
            return False
        return (
            int(order.telegram_id) == int(telegram_id)
            and str(order.currency) == "XTR"
            and int(order.amount_minor) == int(amount)
            and str(order.status) in {"created", "awaiting_payment"}
        )

    async def confirm_stars_payment(
        self, *, telegram_id: int, order_id: int, charge_id: str,
        amount: int, raw_payload: bytes,
    ):
        return await self.commerce.confirm_telegram_stars_payment(
            order_id=order_id,
            telegram_id=telegram_id,
            charge_id=charge_id,
            amount=amount,
            raw_payload=raw_payload,
        )

    async def checkout_for_plan(
        self, *, telegram_id: int, plan: PlanRecord,
    ) -> tuple[CommerceOrderRecord, bool, CheckoutSession | None]:
        order, created = await self.get_or_create_order(
            telegram_id=telegram_id,
            plan=plan,
        )
        if self.checkout is None:
            return order, created, None
        session = await self.checkout.start(order)
        return order, created, session

    async def get_or_create_order(self, *, telegram_id: int, plan: PlanRecord):
        profile = await self.profile(telegram_id)
        if not profile.exists:
            raise ValueError("customer account does not exist")
        return await self.commerce.get_or_create_order(
            telegram_id=telegram_id,
            plan_id=plan.id,
            amount_minor=plan.price_minor,
            currency=plan.currency,
        )
