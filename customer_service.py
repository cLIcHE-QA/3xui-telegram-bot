from __future__ import annotations

from dataclasses import dataclass
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
        return CustomerProfile(
            exists=True,
            email=rec.email,
            display_name=getattr(profile, "display_name", "") or "",
            plan_name=plan.name if plan else "",
            expiry_time=int(rec.expiry_time or 0),
            sub_id=rec.sub_id,
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

    async def active_plans(self) -> list[PlanRecord]:
        return [plan for plan in await self.db.list_plans() if plan.active]

    async def active_plan(self, plan_id: int) -> PlanRecord | None:
        plan = await self.db.get_plan(plan_id)
        return plan if plan is not None and plan.active else None

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
