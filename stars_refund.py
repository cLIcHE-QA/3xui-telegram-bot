from __future__ import annotations

import asyncio
import uuid

from aiogram.exceptions import TelegramAPIError

from db import Database, StarsRefundOperationRecord


async def run_stars_refund(
    db: Database,
    bot,
    *,
    payment_id: int,
    requested_by: int,
) -> StarsRefundOperationRecord:
    """Execute exactly one Telegram Stars refund mutation.

    The operation is journaled before the external call. Ambiguous transport
    failures become unknown and are never replayed automatically.
    """
    operation = await db.begin_stars_refund(
        payment_id=payment_id,
        requested_by=requested_by,
        operation_id=str(uuid.uuid4()),
    )
    if operation.status != "in_flight":
        return operation
    try:
        await bot.refund_star_payment(
            user_id=operation.telegram_id,
            telegram_payment_charge_id=operation.provider_payment_id,
        )
    except asyncio.TimeoutError:
        return await db.finish_stars_refund(
            operation.operation_id,
            status="unknown",
            error="Telegram refund request timed out; mutation was not retried.",
        )
    except TelegramAPIError as exc:
        return await db.finish_stars_refund(
            operation.operation_id,
            status="failed",
            error=f"{type(exc).__name__}: {exc}",
        )
    except Exception as exc:
        return await db.finish_stars_refund(
            operation.operation_id,
            status="unknown",
            error=f"{type(exc).__name__}: {exc}",
        )
    return await db.finish_stars_refund(operation.operation_id, status="success")
