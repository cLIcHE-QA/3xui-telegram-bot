"""Ручная выдача бессрочного технического доступа, без Order/Payment (#705)."""
from __future__ import annotations

from db import Database, ManualEntitlementRecord
from provisioning import ProvisioningEngine


class ManualEntitlementUnknown(RuntimeError):
    """Исход удалённой операции не доказан. Автоматический replay запрещён."""


class ManualEntitlementService:
    def __init__(self, db: Database, provisioner: ProvisioningEngine):
        self.db = db
        self.provisioner = provisioner

    async def grant(
        self, *, telegram_id: int, plan_id: int, actor_id: int,
    ) -> tuple[ManualEntitlementRecord, bool]:
        # Read-only preflight: не создавать in_flight при заведомо непригодном Inbound.
        plan = await self.db.get_plan(plan_id)
        if plan is None or not (plan.active and plan.duration_days == 0
                and plan.traffic_gb == 0 and plan.ip_limit == 0
                and plan.price_minor == 0 and not plan.rub_price_enabled
                and plan.stars_price == 0 and plan.visibility == "admin_only"
                and plan.currency == "RUB"):
            raise ValueError("invalid free technical plan")
        policy = await self.provisioner.policy_for_plan(plan)
        if not policy.desired_inbound_ids or not policy.actionable_inbound_ids:
            raise ValueError("для ручной выдачи нет доступных Inbounds")
        record, created = await self.db.begin_manual_entitlement(
            telegram_id=telegram_id, plan_id=plan_id, actor_id=actor_id,
        )
        if not created:
            # Active grant is idempotent; unresolved grants must never be replayed.
            return record, False

        try:
            user = await self.db.get(telegram_id)
            if user is None:
                raise RuntimeError("customer missing after durable grant start")
            result = await self.provisioner.sync_user(
                telegram_id,
                strict=False,
                apply_plan_limits=True,
                target_expiry_ms=0,
                persist_local_expiry=False,
                manual_operation=True,
            )
            if (not result.limits_applied or result.remaining_missing_ids
                    or not result.policy.desired_inbound_ids):
                raise RuntimeError("provisioning postcondition is incomplete")
            if result.policy.plan is None or int(result.policy.plan.id) != int(plan_id):
                raise RuntimeError("plan changed during manual provisioning")
            # Независимый от ACK read-back, включая наличие полей; missing != zero.
            readback = await self.provisioner.xui.get_client(user.email)
            payload = readback.get("client", readback)
            if not isinstance(payload, dict) or any(
                key not in payload or payload[key] is None or int(payload[key]) != 0
                for key in ("expiryTime", "totalGB", "limitIp")
            ):
                raise RuntimeError("provider limits read-back is missing or mismatched")
            profile = await self.db.get_user_profile(telegram_id)
            if profile is None or int(profile.plan_id or 0) != int(plan_id):
                raise RuntimeError("profile changed before manual grant confirmation")
            await self.db.update_expiry(telegram_id, 0)
            active = await self.db.finish_manual_entitlement(
                record.id, status="active", result_code="provider_readback_match",
            )
            return active, True
        except Exception as exc:
            # in_flight/unknown блокирует повтор. Не выдавать второй раз через новый
            # callback, retry или restart даже при неполном 3x-ui read-back.
            try:
                await self.db.finish_manual_entitlement(
                    record.id, status="unknown",
                    result_code=f"operator_review:{type(exc).__name__}"[:96],
                )
            except Exception:
                # Если SQLite недоступен, durable in_flight сам блокирует replay.
                pass
            raise ManualEntitlementUnknown(
                "Ручная выдача: исход не подтверждён. "
                "Автоматический повтор заблокирован; нужен ручной read-back."
            ) from exc

    async def review(
        self, *, telegram_id: int, actor_id: int,
    ) -> ManualEntitlementRecord:
        """Read-only operator recovery; никаких повторных update/attach вызовов."""
        if int(actor_id) <= 0:
            raise ValueError("invalid reviewing actor")
        record = await self.db.get_live_manual_entitlement(telegram_id)
        if record is None:
            raise ValueError("no live manual entitlement")
        if record.status == "active":
            return record
        if record.status not in {"unknown", "in_flight"}:
            raise ValueError("manual entitlement is not reviewable")
        user = await self.db.get(telegram_id)
        profile = await self.db.get_user_profile(telegram_id)
        if (user is None or profile is None
                or int(profile.plan_id or 0) != record.plan_id):
            raise ManualEntitlementUnknown("Изменён профиль: нужна ручная сверка.")
        try:
            policy = await self.provisioner.policy_for_user(telegram_id)
            if (policy.plan is None or int(policy.plan.id) != record.plan_id
                    or not policy.desired_inbound_ids):
                raise RuntimeError("manual policy no longer matches")
            readback = await self.provisioner.xui.get_client(user.email)
            payload = readback.get("client", readback)
            inbounds = readback.get("inboundIds")
            if (not isinstance(payload, dict) or not isinstance(inbounds, list)
                    or not set(policy.desired_inbound_ids) <= set(map(int, inbounds))
                    or any(key not in payload or payload[key] is None
                           or int(payload[key]) != 0
                           for key in ("expiryTime", "totalGB", "limitIp"))):
                raise RuntimeError("manual grant read-back missing or mismatched")
        except Exception as exc:
            raise ManualEntitlementUnknown(
                "Ручная выдача не подтверждена; удалённые mutation не повторялись."
            ) from exc
        await self.db.update_expiry(telegram_id, 0)
        return await self.db.confirm_manual_entitlement_readback(record.id)
