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
class CustomerProviderAccess:
    """Read-only state returned by the customer access provider."""

    enabled: bool
    expiry_time: int  # ms; 0 means unlimited


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
    period_status: str = "missing"
    provider_status: str = "unavailable"
    entitlement_expiry_time: int = 0
    provider_expiry_time: int = 0
    expiry_drift: bool = False


@dataclass(frozen=True)
class CustomerDiagnostics:
    account_exists: bool
    entitlement_status: str = ""
    subscription_available: bool = False
    provider_reachable: bool | None = None
    vpn_access_status: str = "unknown"
    expiry_drift: bool = False
    note: str = ""


class CustomerAccessProvider(Protocol):
    async def access(self, email: str) -> CustomerProviderAccess: ...

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

    @staticmethod
    def _expiry_mismatch(left: int, right: int) -> bool:
        # 3x-ui milliseconds and entitlement seconds may differ by rounding.
        # Zero (unlimited) versus a finite expiry is a genuine mismatch.
        return abs(int(left) - int(right)) > 2000

    async def profile(
        self, telegram_id: int, *, read_access: bool = True,
    ) -> CustomerProfile:
        rec = await self.db.get(telegram_id)
        if rec is None:
            return CustomerProfile(exists=False)
        user_profile = await self.db.get_user_profile(telegram_id)
        plan = (
            await self.db.get_plan(user_profile.plan_id)
            if user_profile and user_profile.plan_id else None
        )
        local_expiry = int(rec.expiry_time or 0)
        now_ms = int(time.time() * 1000)
        local_expired = local_expiry > 0 and local_expiry <= now_ms
        base = dict(
            exists=True,
            email=rec.email,
            display_name=getattr(user_profile, "display_name", "") or "",
            plan_name=plan.name if plan else "",
            expiry_time=local_expiry,
            sub_id=rec.sub_id,
        )
        if not read_access:
            # Payment, subscription URL and inventory need identity, not
            # an extra provider lookup on their critical path.
            return CustomerProfile(
                **base, access_status="expired" if local_expired else "unknown",
                period_status="expired" if local_expired else "legacy",
            )

        entitlement = await self.db.get_latest_entitlement_for_user(telegram_id)
        period_status = (
            str(entitlement.status) if entitlement is not None
            else ("expired" if local_expired else "legacy")
        )
        entitlement_expiry = (
            int(getattr(entitlement, "expires_at", 0) or 0) * 1000
            if entitlement is not None else 0
        )
        if (
            period_status in {"active", "suspended"}
            and entitlement_expiry > 0
            and entitlement_expiry <= now_ms
        ):
            period_status = "expired"

        provider_status = "unavailable"
        provider_expiry = 0
        provider_access: CustomerProviderAccess | None = None
        try:
            provider_access = await self.provider.access(rec.email)
            provider_status = "enabled" if provider_access.enabled else "disabled"
            provider_expiry = int(provider_access.expiry_time)
        except CustomerProviderUnavailable:
            pass

        # Ignore a pending purchase's unset entitlement expiry; only compare
        # the established lifecycle's expiry to local/provider state.
        relevant_entitlement = (
            entitlement is not None
            and str(entitlement.status) in {"active", "suspended", "expired"}
        )
        expiry_drift = (
            relevant_entitlement
            and self._expiry_mismatch(local_expiry, entitlement_expiry)
        )
        if provider_access is not None:
            expiry_drift = (
                expiry_drift
                or self._expiry_mismatch(local_expiry, provider_expiry)
                or (
                    relevant_entitlement
                    and self._expiry_mismatch(entitlement_expiry, provider_expiry)
                )
            )

        if provider_status == "disabled":
            access_status = "disabled"
        elif local_expired or period_status == "expired" or (
            provider_access is not None
            and provider_expiry > 0
            and provider_expiry <= now_ms
        ):
            access_status = "expired"
        elif period_status in {"pending", "provisioning"}:
            access_status = "provisioning"
        elif period_status == "suspended":
            access_status = "suspended"
        elif provider_access is None or expiry_drift:
            access_status = "unknown"
        else:
            access_status = "active"

        return CustomerProfile(
            **base,
            access_status=access_status,
            period_status=period_status,
            provider_status=provider_status,
            entitlement_expiry_time=entitlement_expiry,
            provider_expiry_time=provider_expiry,
            expiry_drift=bool(expiry_drift),
        )

    async def subscription_url(self, telegram_id: int) -> str | None:
        profile = await self.profile(telegram_id, read_access=False)
        if not profile.exists:
            return None
        return self.subscription_url_template.format(sub_id=profile.sub_id)

    async def traffic(self, telegram_id: int) -> CustomerTraffic | None:
        profile = await self.profile(telegram_id, read_access=False)
        if not profile.exists:
            return None
        return await self.provider.traffic(profile.email)

    async def devices(self, telegram_id: int) -> list[CustomerDevice] | None:
        profile = await self.profile(telegram_id, read_access=False)
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
        notes = []
        if profile.period_status == "legacy":
            notes.append("Для legacy-доступа entitlement journal может отсутствовать.")
        if profile.expiry_drift:
            notes.append(
                "Сроки подписки и VPN-доступа не совпадают. "
                "Обратитесь в поддержку; автоматическое исправление не выполняется."
            )
        if profile.access_status == "disabled":
            notes.append(
                "VPN-доступ отключён в панели. Оплата и срок не включают его автоматически."
            )
        return CustomerDiagnostics(
            account_exists=True,
            entitlement_status=profile.period_status,
            subscription_available=bool(profile.sub_id),
            provider_reachable=profile.provider_status != "unavailable",
            vpn_access_status=profile.access_status,
            expiry_drift=profile.expiry_drift,
            note="\n".join(notes),
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
        profile = await self.profile(telegram_id, read_access=False)
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
        profile = await self.profile(telegram_id, read_access=False)
        if not profile.exists:
            raise ValueError("customer account does not exist")
        return await self.commerce.get_or_create_order(
            telegram_id=telegram_id,
            plan_id=plan.id,
            amount_minor=plan.price_minor,
            currency=plan.currency,
        )
