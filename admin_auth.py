from __future__ import annotations

from aiogram.types import CallbackQuery

from config import Settings
from db import Database

ROLE_LABELS = {
    "owner": "Owner",
    "admin": "Administrator",
    "support": "Support",
    "read_only": "Read-only",
}

ROLE_RANK = {
    "read_only": 10,
    "support": 20,
    "admin": 30,
    "owner": 40,
}


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


def _is_read_callback(data: str) -> bool:
    exact = {
        "admin:home", "admin:dashboard", "admin:users", "admin:subscriptions",
        "admin:stats", "admin:section:infrastructure", "admin:section:monitoring",
        "admin:section:system", "admin:infra:inbounds", "admin:nodes",
        "admin:nodes:refresh", "admin:nodes:noop", "admin:master", "admin:health",
        "admin:traffic", "admin:online", "admin:jobs", "admin:audit",
        "admin:backups", "admin:plans", "admin:servergroups", "admin:hosts",
        "admin:payments", "admin:promo", "admin:administrators", "admin:settings",
    }
    if data in exact:
        return True
    prefixes = (
        "adminuser:", "adminsub:", "admin:node:", "admin:plan:",
        "admin:servergroup:", "admin:host:", "admin:audit:",
        "admin:payment:", "admin:promo:", "admin:administrator:",
    )
    return data.startswith(prefixes)


def required_role_for_callback(data: str) -> str:
    data = data or ""

    # Administrator registry is owner-only. Environment owners are the recovery path.
    if data.startswith("admin:administrator") or data == "admin:administrators":
        return "owner"

    # Safe runtime settings may be changed by Owner/Admin; viewing is read-only.
    if data == "admin:settings":
        return "read_only"
    if data.startswith("admin:settings:"):
        return "admin"

    # Support can handle common user lifecycle operations but cannot delete users.
    if data.startswith(("adminextend:", "adminsync:", "adminenable:", "admindisable:")):
        return "support"

    # Read-only views are available to every administrator role.
    if _is_read_callback(data):
        # Some detail prefixes also contain mutation suffixes; catch them below.
        mutation_tokens = (
            ":toggle:", ":delete:", ":deleteask:", ":setgroup:", ":member:",
            ":status:", ":save", ":start", ":create", ":discover", ":run",
            ":tls:", ":cancel", ":backup", ":full", ":botdb",
        )
        if not any(token in data for token in mutation_tokens):
            return "read_only"

    # Explicit destructive/sensitive operations stay Admin+.
    if data.startswith(("admindel", "admin:syncall:")):
        return "admin"

    # New business mutations, infrastructure mutations, backups and catalog writes.
    return "admin"


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
    needed = minimum or required_role_for_callback(call.data or "")
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
