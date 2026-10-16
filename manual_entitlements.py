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
