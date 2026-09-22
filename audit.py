from __future__ import annotations

from aiogram.types import CallbackQuery, Message

from db import Database


def _clean(value: object, limit: int = 1200) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    return text[:limit]


async def audit_from_call(
    db: Database,
    call: CallbackQuery,
    action: str,
    *,
    target_type: str = "",
    target_id: object = "",
    details: object = "",
    success: bool = True,
) -> None:
    user = call.from_user
    await db.add_audit(
        actor_id=int(user.id if user else 0),
        actor_username=(user.username or "") if user else "",
        action=_clean(action, 96),
        target_type=_clean(target_type, 64),
        target_id=_clean(target_id, 160),
        details=_clean(details, 1200),
        success=success,
    )


async def audit_from_message(
    db: Database,
    message: Message,
    action: str,
    *,
    target_type: str = "",
    target_id: object = "",
    details: object = "",
    success: bool = True,
) -> None:
    user = message.from_user
    await db.add_audit(
        actor_id=int(user.id if user else 0),
        actor_username=(user.username or "") if user else "",
        action=_clean(action, 96),
        target_type=_clean(target_type, 64),
        target_id=_clean(target_id, 160),
        details=_clean(details, 1200),
        success=success,
    )


async def audit_system(
    db: Database,
    action: str,
    *,
    target_type: str = "",
    target_id: object = "",
    details: object = "",
    success: bool = True,
) -> None:
    await db.add_audit(
        actor_id=0,
        actor_username="system",
        action=_clean(action, 96),
        target_type=_clean(target_type, 64),
        target_id=_clean(target_id, 160),
        details=_clean(details, 1200),
        success=success,
    )
