"""Canonical trial setting parsing for admin UI and 3x-ui compatibility creation."""
from __future__ import annotations

TRIAL_LIMITS = {
    "trial_days": (1, 3650),
    "trial_traffic_gb": (0, 100000),
    "trial_ip_limit": (0, 1000),
}


def parse_trial_setting(key: str, raw: object, default: int) -> int:
    """Missing override uses .env; explicit zero stays zero; invalid data fails closed."""
    if key not in TRIAL_LIMITS:
        raise ValueError("Неизвестный параметр пробного доступа.")
    value = default if raw is None else raw
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError(f"Настройка {key}: ожидается целое число.")
    if isinstance(value, str):
        if not value or not value.isascii() or not value.isdecimal():
            raise ValueError(f"Настройка {key}: ожидается целое число.")
    number = int(value)
    minimum, maximum = TRIAL_LIMITS[key]
    if not minimum <= number <= maximum:
        raise ValueError(f"Настройка {key}: допустимый диапазон {minimum}..{maximum}.")
    return number


def trial_limit_label(key: str, number: int) -> str:
    if key not in {"trial_traffic_gb", "trial_ip_limit"}:
        raise ValueError("Неизвестный лимит.")
    return "без лимита" if number == 0 else f"{number} GB" if key == "trial_traffic_gb" else str(number)
