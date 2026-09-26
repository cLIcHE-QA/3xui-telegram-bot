"""Operator-facing timezone helpers.

Runtime storage, API timestamps and schedulers may remain UTC. Telegram UI is
rendered in fixed Moscow time (MSK, UTC+3) to keep operator-facing dates
consistent and independent from container/host local timezone.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone


UTC = timezone.utc
MSK = timezone(timedelta(hours=3), name="MSK")


def format_timestamp(
    value: int | float,
    *,
    milliseconds: bool = False,
    empty: str = "—",
) -> str:
    if not value:
        return empty
    try:
        seconds = float(value) / 1000 if milliseconds else float(value)
        return datetime.fromtimestamp(seconds, tz=MSK).strftime("%Y-%m-%d %H:%M MSK")
    except (OSError, OverflowError, TypeError, ValueError):
        return empty


def format_datetime(value: datetime, *, empty: str = "—") -> str:
    if value is None:
        return empty
    try:
        current = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return current.astimezone(MSK).strftime("%Y-%m-%d %H:%M MSK")
    except (OSError, OverflowError, TypeError, ValueError):
        return empty


def format_short_datetime(value: datetime, *, empty: str = "—") -> str:
    if value is None:
        return empty
    try:
        current = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return current.astimezone(MSK).strftime("%m-%d %H:%M")
    except (OSError, OverflowError, TypeError, ValueError):
        return empty


def end_of_day_timestamp(date_text: str) -> int:
    """Return 23:59:59 MSK for YYYY-MM-DD as Unix seconds."""
    dt = datetime.strptime(date_text, "%Y-%m-%d").replace(
        hour=23,
        minute=59,
        second=59,
        tzinfo=MSK,
    )
    return int(dt.timestamp())


def backup_schedule_text(hour_utc: int) -> str:
    hour = max(0, min(23, int(hour_utc)))
    sample = datetime(2000, 1, 1, hour=hour, tzinfo=UTC).astimezone(MSK)
    return f"{sample:%H:%M} MSK ({hour:02d}:00 UTC)"
