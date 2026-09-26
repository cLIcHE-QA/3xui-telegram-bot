"""Shared presentation helpers for bot-managed user identity."""
from __future__ import annotations


def display_name_from_profile(profile) -> str:
    return (getattr(profile, "display_name", "") or "").strip() if profile else ""


def user_label(user, profile=None, *, include_email: bool = True) -> str:
    """Presentation label only; stable callbacks/mutations must use technical IDs."""
    display_name = display_name_from_profile(profile)
    email = str(getattr(user, "email", "") or "")
    if display_name and include_email and email:
        return f"{display_name} · {email}"
    return display_name or email
