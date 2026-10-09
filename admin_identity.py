"""Ephemeral, bounded Telegram username hints for owner-only admin presentation.

Only identity received in an actual, already-authorized Telegram update may be
observed. Hints expire, are not persisted, and never determine authorization.
"""
from __future__ import annotations

import re
import time
from collections import OrderedDict

TTL_SECONDS = 6 * 60 * 60
MAX_ENTRIES = 256
MAX_BUTTON_LENGTH = 64
_USERNAME = re.compile(r"[A-Za-z][A-Za-z0-9_]{4,31}\Z")
_hints: OrderedDict[int, tuple[str, float]] = OrderedDict()


def clear_hints() -> None:
    """Test/reset helper; no persistent state."""
    _hints.clear()


def observe_admin_identity(telegram_id: int, username: str | None, *, now: float | None = None) -> None:
    """Record a verified Telegram from_user ID and the *current* username.

    Missing/invalid username replaces any older hint to prevent stale labels.
    """
    if int(telegram_id) <= 0:
        return
    moment = time.time() if now is None else float(now)
    name = str(username or "").lstrip("@")
    if not _USERNAME.fullmatch(name):
        _hints.pop(int(telegram_id), None)
        return
    _hints.pop(int(telegram_id), None)
    _hints[int(telegram_id)] = (name, moment)
    while len(_hints) > MAX_ENTRIES:
        _hints.popitem(last=False)


def observed_username(telegram_id: int, *, now: float | None = None) -> str | None:
    moment = time.time() if now is None else float(now)
    entry = _hints.get(int(telegram_id))
    if entry is None:
        return None
    name, when = entry
    if moment < when or moment - when > TTL_SECONDS:
        _hints.pop(int(telegram_id), None)
        return None
    return name


def administrator_label(telegram_id: int, *, now: float | None = None) -> str:
    name = observed_username(telegram_id, now=now)
    return f"@{name}" if name else f"TG {telegram_id}"


def bounded_admin_button(text: str) -> str:
    """Telegram limit is measured in text characters; keep long rows compact."""
    if len(text) <= MAX_BUTTON_LENGTH:
        return text
    return text[: MAX_BUTTON_LENGTH - 1].rstrip() + "…"
