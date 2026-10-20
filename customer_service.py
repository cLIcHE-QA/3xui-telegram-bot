from __future__ import annotations

import asyncio
from dataclasses import dataclass
import hmac
import secrets
import time
from typing import Protocol

from checkout_service import CheckoutService, CheckoutSession
from commerce import CommerceService
from db import CommerceOrderRecord, Database, PlanRecord


class CustomerProviderUnavailable(RuntimeError):
    """Customer-facing provider read failed without exposing provider details."""


class CustomerDeviceDeleteUnknown(RuntimeError):
    """The provider may have committed DELETE; automatic replay is forbidden."""


class CustomerDeviceDeleteRejected(RuntimeError):
    """The provider deterministically rejected a single DELETE."""


DEVICE_DELETE_CONFIRM_TTL_SECONDS = 90
DEVICE_DELETE_COOLDOWN_SECONDS = 120
DEVICE_DELETE_MAX_PENDING = 256


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
    expiry_available: bool = True  # False when expiryTime is omitted by provider.


@dataclass(frozen=True)
class CustomerDevice:
    title: str
    os_name: str
    last_seen: int
    # Verified, stable upstream HWID row ID. Never substitute a list index.
    device_id: int | None = None
    os_version: str = ""


@dataclass(frozen=True)
class CustomerDeviceInventory:
    devices: tuple[CustomerDevice, ...]
    total: int
    # A positive, verified provider limit only. Zero/absent is not a quota.
    limit: int | None = None
    limit_state: str = "unknown"  # known | disabled | unknown
    truncated: bool = False
    # Complete, unique upstream IDs, or None when read-back cannot prove absence.
    verified_ids: frozenset[int] | None = None


@dataclass(frozen=True)
class CustomerDeviceDeletePrompt:
    token: str
    device: CustomerDevice
    page: int


@dataclass(frozen=True)
class CustomerDeviceDeleteResult:
    # deleted | stale | unsupported | unavailable | rejected | unknown | cooldown
    status: str
    page: int = 0
    inventory: CustomerDeviceInventory | None = None


@dataclass(frozen=True)
class _PendingDeviceDelete:
    token: str
    owner_email: str
    device_id: int
    page: int
    expires_at: float


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
    expiry_comparison: str = "insufficient_data"


@dataclass(frozen=True)
class CustomerDiagnostics:
    account_exists: bool
    entitlement_status: str = ""
    subscription_available: bool = False
    provider_reachable: bool | None = None
    vpn_access_status: str = "unknown"
    expiry_drift: bool = False
    expiry_comparison: str = "insufficient_data"
    note: str = ""


class CustomerAccessProvider(Protocol):
    async def access(self, email: str) -> CustomerProviderAccess: ...

    async def traffic(self, email: str) -> CustomerTraffic: ...

    async def devices(self, email: str) -> CustomerDeviceInventory: ...

    def supports_device_delete(self) -> bool: ...

    async def delete_device(self, email: str, device_id: int) -> None: ...


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
        # One-shot confirmations and serialized customer mutations are strictly
        # process-local. Never restore a pending token after a restart.
        self._device_delete_lock = asyncio.Lock()
        self._device_delete_prompts: dict[int, _PendingDeviceDelete] = {}
        self._device_delete_last_attempt: dict[int, float] = {}

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
        local_expiry_known = rec.expiry_time is not None
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
        raw_entitlement_expiry = (
            getattr(entitlement, "expires_at", None)
            if entitlement is not None else None
        )
        entitlement_expiry = int(raw_entitlement_expiry or 0) * 1000
        if (
            period_status in {"active", "suspended"}
            and entitlement_expiry > 0
            and entitlement_expiry <= now_ms
        ):
            period_status = "expired"

        provider_status = "unavailable"
        provider_expiry = 0
        provider_expiry_known = False
        provider_access: CustomerProviderAccess | None = None
        try:
            provider_access = await self.provider.access(rec.email)
            provider_status = "enabled" if provider_access.enabled else "disabled"
            provider_expiry = int(provider_access.expiry_time)
            provider_expiry_known = bool(provider_access.expiry_available)
        except CustomerProviderUnavailable:
            pass

        # Pending purchases do not provide an established entitlement expiry.
        # A missing expiry field is not the same as an explicit unlimited (0).
        relevant_entitlement = (
            entitlement is not None
            and str(entitlement.status) in {"active", "suspended", "expired"}
        )
        entitlement_expiry_known = (
            relevant_entitlement and raw_entitlement_expiry is not None
        )
        comparable_expiries: list[tuple[int, int]] = []
        if local_expiry_known and entitlement_expiry_known:
            comparable_expiries.append((local_expiry, entitlement_expiry))
        if local_expiry_known and provider_expiry_known:
            comparable_expiries.append((local_expiry, provider_expiry))
        if entitlement_expiry_known and provider_expiry_known:
            comparable_expiries.append((entitlement_expiry, provider_expiry))

        # Contradictory evidence takes priority even if a third source is
        # missing. MATCH requires every applicable established source.
        expiry_drift = any(
            self._expiry_mismatch(left, right)
            for left, right in comparable_expiries
        )
        if expiry_drift:
            expiry_comparison = "mismatch"
        elif (
            local_expiry_known
            and provider_expiry_known
            and (not relevant_entitlement or entitlement_expiry_known)
            and period_status not in {"pending", "provisioning", "failed"}
        ):
            expiry_comparison = "match"
        else:
            expiry_comparison = "insufficient_data"

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
        elif period_status == "failed":
            access_status = "unknown"
        elif period_status == "suspended":
            access_status = "suspended"
        elif provider_access is None or expiry_drift or not provider_expiry_known:
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
            expiry_comparison=expiry_comparison,
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

    async def devices(self, telegram_id: int) -> CustomerDeviceInventory | None:
        profile = await self.profile(telegram_id, read_access=False)
        if not profile.exists:
            return None
        return await self.provider.devices(profile.email)


    def supports_device_delete(self) -> bool:
        """Fail closed for missing, throwing or unreviewed provider capability."""
        capability = getattr(self.provider, "supports_device_delete", None)
        delete = getattr(self.provider, "delete_device", None)
        if not callable(capability) or not callable(delete):
            return False
        try:
            return capability() is True
        except Exception:
            return False

    def _prune_device_delete_state(self, now: float) -> None:
        self._device_delete_prompts = {
            user: item for user, item in self._device_delete_prompts.items()
            if item.expires_at > now
        }
        self._device_delete_last_attempt = {
            user: instant for user, instant in self._device_delete_last_attempt.items()
            if now - instant < DEVICE_DELETE_COOLDOWN_SECONDS
        }

    async def prepare_device_delete(
        self, telegram_id: int, device_id: int, *, page: int = 0,
    ) -> CustomerDeviceDeletePrompt | CustomerDeviceDeleteResult:
        """Only issue a short-lived single-user token for a freshly owned HWID."""
        if (type(telegram_id) is not int or telegram_id <= 0
                or type(device_id) is not int or not 0 < device_id <= 2**63 - 1
                or type(page) is not int or not 0 <= page <= 999):
            return CustomerDeviceDeleteResult("stale")
        if not self.supports_device_delete():
            return CustomerDeviceDeleteResult("unsupported", page=page)
        async with self._device_delete_lock:
            self._prune_device_delete_state(time.monotonic())
            self._device_delete_prompts.pop(telegram_id, None)
            if telegram_id in self._device_delete_last_attempt:
                return CustomerDeviceDeleteResult("cooldown", page=page)
        try:
            profile = await self.profile(telegram_id, read_access=False)
            if not profile.exists or not profile.email:
                return CustomerDeviceDeleteResult("stale", page=page)
            inventory = await self.provider.devices(profile.email)
        except Exception:
            return CustomerDeviceDeleteResult("unavailable", page=page)
        if not isinstance(inventory, CustomerDeviceInventory) or inventory.verified_ids is None:
            return CustomerDeviceDeleteResult("unavailable", page=page)
        if device_id not in inventory.verified_ids:
            return CustomerDeviceDeleteResult("stale", page=page)
        matches = [d for d in inventory.devices if d.device_id == device_id]
        if len(matches) != 1:
            return CustomerDeviceDeleteResult("stale", page=page)
        async with self._device_delete_lock:
            now = time.monotonic()
            self._prune_device_delete_state(now)
            if telegram_id in self._device_delete_last_attempt:
                return CustomerDeviceDeleteResult("cooldown", page=page)
            if len(self._device_delete_prompts) >= DEVICE_DELETE_MAX_PENDING:
                return CustomerDeviceDeleteResult("unavailable", page=page)
            token = secrets.token_urlsafe(16)
            self._device_delete_prompts[telegram_id] = _PendingDeviceDelete(
                token=token, owner_email=profile.email, device_id=device_id, page=page,
                expires_at=now + DEVICE_DELETE_CONFIRM_TTL_SECONDS,
            )
        return CustomerDeviceDeletePrompt(token, matches[0], page)

    async def cancel_device_delete(
        self, telegram_id: int, token: str,
    ) -> tuple[int, int] | None:
        """Invalidate confirmation on Cancel without provider mutations."""
        async with self._device_delete_lock:
            self._prune_device_delete_state(time.monotonic())
            pending = self._device_delete_prompts.get(telegram_id)
            if not pending or not isinstance(token, str) or not hmac.compare_digest(pending.token, token):
                return None
            del self._device_delete_prompts[telegram_id]
            return pending.device_id, pending.page

    async def confirm_device_delete(
        self, telegram_id: int, token: str,
    ) -> CustomerDeviceDeleteResult:
        """Consume once; re-resolve owner and device, then DELETE exactly once.

        A successful HTTP response is NOT a success claim until an independent
        complete provider inventory read-back proves the ID has disappeared.
        """
        async with self._device_delete_lock:
            self._prune_device_delete_state(time.monotonic())
            pending = self._device_delete_prompts.get(telegram_id)
            if (not pending or not isinstance(token, str)
                    or not hmac.compare_digest(pending.token, token)):
                return CustomerDeviceDeleteResult("stale")
            # Consume before any network await, including an uncertain attempt.
            del self._device_delete_prompts[telegram_id]
            page = pending.page
            if telegram_id in self._device_delete_last_attempt:
                return CustomerDeviceDeleteResult("cooldown", page=page)
            if not self.supports_device_delete():
                return CustomerDeviceDeleteResult("unsupported", page=page)

            try:
                # No callback-controlled customer identity/email is accepted.
                profile = await self.profile(telegram_id, read_access=False)
                if (not profile.exists or not profile.email
                        or profile.email != pending.owner_email):
                    return CustomerDeviceDeleteResult("stale", page=page)
                before = await self.provider.devices(profile.email)
            except Exception:
                return CustomerDeviceDeleteResult("unavailable", page=page)
            if not isinstance(before, CustomerDeviceInventory) or before.verified_ids is None:
                return CustomerDeviceDeleteResult("unavailable", page=page)
            if pending.device_id not in before.verified_ids:
                return CustomerDeviceDeleteResult("stale", page=page)
            if len([d for d in before.devices if d.device_id == pending.device_id]) != 1:
                return CustomerDeviceDeleteResult("stale", page=page)

            # Charge cooldown BEFORE the only possible mutation attempt.
            self._device_delete_last_attempt[telegram_id] = time.monotonic()
            try:
                await self.provider.delete_device(profile.email, pending.device_id)
            except CustomerDeviceDeleteRejected:
                return CustomerDeviceDeleteResult("rejected", page=page)
            except CustomerDeviceDeleteUnknown:
                return CustomerDeviceDeleteResult("unknown", page=page)
            except Exception:
                # Unclassified transport/adapter errors after dispatch may have
                # committed the mutation. Never blindly replay.
                return CustomerDeviceDeleteResult("unknown", page=page)

            try:
                after = await self.provider.devices(profile.email)
            except Exception:
                return CustomerDeviceDeleteResult("unknown", page=page)
            if (not isinstance(after, CustomerDeviceInventory)
                    or after.verified_ids is None
                    or pending.device_id in after.verified_ids):
                return CustomerDeviceDeleteResult("unknown", page=page)
            return CustomerDeviceDeleteResult(
                "deleted", page=page, inventory=after,
            )

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
        if profile.expiry_comparison == "mismatch":
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
            expiry_comparison=profile.expiry_comparison,
            note="\n".join(notes),
        )

    async def _plan_visible(self, plan: PlanRecord, telegram_id: int) -> bool:
        """Текущие memberships; ошибка БД или битые правила закрывают доступ."""
        import json
        from audience import audience_matches_group_ids
        if (not plan.active or int(plan.stars_price or 0) <= 0
                or plan.currency != "RUB" or plan.duration_days <= 0):
            return False
        try:
            if await self.db.get_live_manual_entitlement(telegram_id) is not None:
                return False
        except Exception:
            return False
        visibility = getattr(plan, "visibility", "all")
        if visibility == "admin_only":
            return False
        if visibility == "all":
            return True
        if visibility != "groups":
            return False
        try:
            include = json.loads(getattr(plan, "include_group_ids", "[]"))
            exclude = json.loads(getattr(plan, "exclude_group_ids", "[]"))
            if not isinstance(include, list) or not include:
                return False
            if not isinstance(exclude, list):
                return False
            all_ids = include + exclude
            if any(type(i) is not int or i <= 0 for i in all_ids):
                return False
            groups = await self.db.list_user_groups()
            valid = {g.id for g in groups}
            if not set(all_ids) <= valid:
                return False
            members = await self.db.list_user_group_ids_for_user(telegram_id)
            return audience_matches_group_ids(members, include_group_ids=include, exclude_group_ids=exclude)
        except Exception:  # Fail closed: не показывать тариф при отказе storage
            return False

    async def manual_purchase_block_reason(self, telegram_id: int) -> str | None:
        """Read-only reason for blocked purchase; uncertain storage remains fail-closed."""
        try:
            grant = await self.db.get_live_manual_entitlement(telegram_id)
        except Exception:
            return "Проверить право покупки сейчас не удалось. Попробуйте позже."
        if grant is None:
            return None
        if grant.status == "active":
            return (
                "У вас действует подписка, назначенная администратором. "
                "Самостоятельная покупка другого тарифа недоступна. "
                "Для смены тарифа обратитесь к администратору."
            )
        return (
            "По вашей ручной подписке идёт проверка. "
            "Самостоятельная покупка сейчас недоступна. Обратитесь к администратору."
        )

    async def active_plans(self, telegram_id: int | None = None) -> list[PlanRecord]:
        plans = [plan for plan in await self.db.list_plans() if plan.active]
        if telegram_id is None:
            return plans
        visible = [plan for plan in plans if await self._plan_visible(plan, telegram_id)]
        return sorted(visible, key=lambda plan: (-int(plan.stars_price), int(plan.id)))

    async def active_plan(self, plan_id: int, telegram_id: int | None = None) -> PlanRecord | None:
        plan = await self.db.get_plan(plan_id)
        if plan is None or not plan.active:
            return None
        if telegram_id is not None and not await self._plan_visible(plan, telegram_id):
            return None
        return plan

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
        # Never trust the PlanRecord supplied by a prior callback: pricing, visibility
        # and membership may have changed since the card was rendered.
        current_plan = await self.db.get_plan(plan.id)
        if current_plan is None or not await self._plan_visible(current_plan, telegram_id):
            raise ValueError("plan is not purchasable for this customer")
        profile = await self.profile(telegram_id, read_access=False)
        if not profile.exists:
            raise ValueError("customer account does not exist")
        order, created = await self.commerce.get_or_create_order(
            telegram_id=telegram_id,
            plan_id=plan.id,
            amount_minor=int(current_plan.stars_price),
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
        plan = await self.db.get_plan(order.plan_id)
        if plan is None or not await self._plan_visible(plan, telegram_id):
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
