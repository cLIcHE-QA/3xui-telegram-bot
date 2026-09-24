from __future__ import annotations

from aiogram.types import CallbackQuery

from admin_privileges import (
    ROLE_LABELS,
    ROLE_RANK,
    privilege_for_callback,
    required_role_for_callback,
)
from config import Settings
from db import Database


async def get_admin_role(db: Database, settings: Settings, telegram_id: int) -> str | None:
    """Return the effective admin role.

    ADMIN_TELEGRAM_IDS are immutable break-glass owners. Database administrators
    extend that list without being able to lock out an environment owner.
    """
    if int(telegram_id) in settings.admin_telegram_ids:
        return "owner"
    rec = await db.get_administrator(int(telegram_id))
    if not rec or not rec.enabled:
        return None
    role = (rec.role or "").strip().lower()
    return role if role in ROLE_RANK else None


async def is_admin_user(db: Database, settings: Settings, telegram_id: int) -> bool:
    return (await get_admin_role(db, settings, telegram_id)) is not None


def _stronger_role(catalog_role: str, explicit_minimum: str | None) -> str:
    if explicit_minimum is None:
        return catalog_role
    if explicit_minimum not in ROLE_RANK:
        return "__invalid__"
    return (
        explicit_minimum
        if ROLE_RANK[explicit_minimum] > ROLE_RANK[catalog_role]
        else catalog_role
    )


async def authorize_callback(
    db: Database,
    settings: Settings,
    call: CallbackQuery,
    *,
    minimum: str | None = None,
) -> tuple[bool, str | None]:
    if not call.from_user:
        return False, None
    role = await get_admin_role(db, settings, call.from_user.id)
    if role is None:
        await call.answer("Недостаточно прав.", show_alert=True)
        return False, None

    privilege = privilege_for_callback(call.data or "")
    if privilege is None:
        await call.answer(
            "Действие заблокировано: правило privilege не определено.",
            show_alert=True,
        )
        return False, role

    needed = _stronger_role(privilege.minimum_role, minimum)
    if ROLE_RANK.get(role, 0) < ROLE_RANK.get(needed, 999):
        await call.answer(
            f"Недостаточно прав. Требуется роль: {ROLE_LABELS.get(needed, needed)}.",
            show_alert=True,
        )
        return False, role
    return True, role


async def authorize_message(
    db: Database,
    settings: Settings,
    telegram_id: int,
    *,
    minimum: str = "admin",
) -> tuple[bool, str | None]:
    role = await get_admin_role(db, settings, int(telegram_id))
    if role is None:
        return False, None
    return ROLE_RANK.get(role, 0) >= ROLE_RANK.get(minimum, 999), role
