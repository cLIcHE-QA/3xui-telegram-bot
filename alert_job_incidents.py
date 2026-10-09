"""Stable job-alert identity and safe, operator-readable notifications.

Kept free of runtime dependencies so notification semantics can be tested without
Telegram, credentials or a production database.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

MSK = timezone(timedelta(hours=3))
RUN = re.compile(r"^Job ID: #(\d+); ", re.ASCII)


def timestamp_msk(value: int) -> str:
    if not value:
        return "неизвестно"
    return datetime.fromtimestamp(value, tz=MSK).strftime("%d.%m.%Y %H:%M:%S MSK")


def job_value(run_id: int, status: str, started_at: int, finished_at: int) -> str:
    status = (status or "unknown").lower()
    if status not in {"success", "failed", "unknown", "running", "cancelled", "partial", "interrupted"}:
        status = "unknown"
    return (
        f"Job ID: #{int(run_id)}; статус: {status}; "
        f"начало: {timestamp_msk(started_at)}; завершение: {timestamp_msk(finished_at)}"
    )


def job_incident_changed(previous_value: str, new_value: str) -> bool:
    """New failed run bypasses cooldown; an unchanged run does not."""
    old = RUN.match(previous_value or "")
    new = RUN.match(new_value or "")
    return bool(new and (not old or old.group(1) != new.group(1)))


def job_incident_message(
    target: str, value: str, *, kind: str,
    original_first_seen: int = 0, previous_value: str = "",
) -> str:
    # Never interpolate raw job.details/exception text into a Telegram alert.
    safe_target = re.sub(r"[^A-Za-z0-9._ -]", "_", str(target))[:96]
    if kind == "new":
        title = "🚨 Новая ошибка фонового задания"
    elif kind == "reminder":
        title = "🔁 Повторное напоминание: прежняя ошибка задания"
    elif kind == "recovery":
        title = "✅ Восстановлено: фоновое задание снова выполняется успешно"
    else:
        raise ValueError("Unsupported job incident notification type")
    lines = [title, f"Цель: {safe_target}", value]
    if kind == "reminder" and original_first_seen:
        lines.append(f"Инцидент отслеживается с: {timestamp_msk(original_first_seen)}")
        lines.append("Это напоминание об исходной ошибке, а не новый запуск.")
    if kind == "recovery":
        original = RUN.match(previous_value or "")
        if original:
            lines.append(f"Исходная ошибка: job #{original.group(1)}")
        lines.append("Исторический ошибочный запуск сохранён в журнале.")
    return "\n".join(lines)
