from __future__ import annotations

import asyncio
import logging
import time

from aiogram import Bot

from audit import audit_system
from config import load_settings
from db import Database
from website_monitoring import (
    FIRST_REPEAT_ALERT_INTERVAL,
    LATER_REPEAT_ALERT_INTERVAL,
    MonitorCheckExecution,
    WebsiteMonitoringRepository,
    WebsiteMonitoringService,
)


LOG = logging.getLogger(__name__)
settings = load_settings()
db = Database(settings.db_path)
repository = WebsiteMonitoringRepository(settings.db_path)
service = WebsiteMonitoringService(repository)


def _failure_text(execution: MonitorCheckExecution) -> str:
    outcome = execution.outcome
    if outcome.error_kind == "http_status" and outcome.http_status:
        return f"HTTP {outcome.http_status}"
    if outcome.error_kind == "slow":
        return f"медленный ответ · {outcome.latency_ms} мс"
    labels = {
        "timeout": "таймаут",
        "dns": "ошибка DNS",
        "connect": "ошибка подключения",
        "tls": "ошибка TLS",
    }
    return labels.get(outcome.error_kind, outcome.error_kind or "неизвестная ошибка")


def _notification_text(
    execution: MonitorCheckExecution,
    *,
    canonical_url: str,
) -> str:
    if execution.notify_kind == "opened":
        return (
            "🚨 Сайт недоступен\n\n"
            f"Сайт: {canonical_url}\n"
            f"Причина: {_failure_text(execution)}"
        )
    if execution.notify_kind == "repeat":
        return (
            "🔴 Сайт всё ещё недоступен\n\n"
            f"Сайт: {canonical_url}\n"
            f"Причина: {_failure_text(execution)}"
        )
    return (
        "✅ Сайт снова доступен\n\n"
        f"Сайт: {canonical_url}\n"
        f"HTTP: {execution.outcome.http_status or '—'}\n"
        f"Ответ: {execution.outcome.latency_ms} мс"
    )


async def _repeat_is_due(execution: MonitorCheckExecution, *, now: int) -> bool:
    if execution.incident_id is None:
        return False
    incident = await repository.get_incident(execution.incident_id)
    if incident is None:
        return False
    if incident.alert_count <= 0:
        return True
    interval = (
        FIRST_REPEAT_ALERT_INTERVAL
        if incident.alert_count < 2
        else LATER_REPEAT_ALERT_INTERVAL
    )
    return now - int(incident.last_alert_at or 0) >= interval


async def dispatch_monitor_notification(
    bot: Bot,
    execution: MonitorCheckExecution,
) -> int:
    if not execution.notify_kind or execution.incident_id is None:
        return 0

    now = int(time.time())
    if execution.notify_kind == "repeat" and not await _repeat_is_due(execution, now=now):
        return 0

    monitor = await repository.get_monitor(execution.monitor_id)
    if monitor is None:
        return 0

    watchers = await repository.watchers(monitor.id, enabled_only=True)
    if not watchers:
        return 0

    incident = await repository.get_incident(execution.incident_id)
    sequence = 0
    if execution.notify_kind == "repeat" and incident is not None:
        sequence = max(1, int(incident.alert_count))

    text = _notification_text(execution, canonical_url=monitor.canonical_url)
    claimed = 0
    for telegram_id in watchers:
        # Claim before Telegram send. If delivery outcome becomes uncertain
        # because the process stops, startup does not replay the same alert.
        fresh = await repository.record_notification(
            execution.incident_id,
            telegram_id,
            kind=execution.notify_kind,
            sequence=sequence,
            sent_at=now,
        )
        if not fresh:
            continue
        claimed += 1
        try:
            await bot.send_message(telegram_id, text, disable_web_page_preview=True)
        except Exception:
            LOG.exception(
                "Could not deliver website-monitor alert monitor=%s incident=%s recipient=%s",
                execution.monitor_id,
                execution.incident_id,
                telegram_id,
            )

    if claimed and execution.notify_kind in {"opened", "repeat"}:
        await repository.mark_incident_alert(execution.incident_id, sent_at=now)
    return claimed


async def process_monitor_execution(
    bot: Bot,
    execution: MonitorCheckExecution,
) -> None:
    if execution.notify_kind == "opened":
        await audit_system(
            db,
            "website_monitor.incident.open",
            target_type="website_monitor",
            target_id=execution.monitor_id,
            details=f"reason={execution.outcome.error_kind}; http={execution.outcome.http_status}",
            success=False,
        )
    elif execution.notify_kind == "recovered":
        await audit_system(
            db,
            "website_monitor.incident.recover",
            target_type="website_monitor",
            target_id=execution.monitor_id,
            details=f"http={execution.outcome.http_status}; latency_ms={execution.outcome.latency_ms}",
            success=True,
        )
    await dispatch_monitor_notification(bot, execution)


async def website_monitoring_loop(bot: Bot) -> None:
    await asyncio.sleep(10)
    while True:
        try:
            results = await service.check_due_once(limit=50)
            for item in results:
                if isinstance(item, Exception):
                    LOG.error(
                        "Website monitoring scheduled check failed: %s: %s",
                        type(item).__name__,
                        item,
                    )
                    continue
                await process_monitor_execution(bot, item)
        except asyncio.CancelledError:
            raise
        except Exception:
            LOG.exception("Website monitoring loop failed")
        await asyncio.sleep(15)
