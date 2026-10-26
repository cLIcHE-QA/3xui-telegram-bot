"""#887 D3f: reviewed owner-bound subscription URL disclosure policy.

Source-only and opt-in. This module never reads browser-provided owner IDs,
subscription IDs or URLs. A subscription URL is a bearer credential: only a
fresh active owner-scoped CustomerPortalService.subscription_card may supply it.
Review metadata is trusted *build-time* configuration, not user attestation.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlsplit

PLATFORMS = frozenset({
    "ios", "android", "macos", "windows", "linux", "appleTV", "androidTV",
})
_ID = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
_REVIEW = re.compile(r"#[1-9][0-9]{0,7}")
_SUB_ID = re.compile(r"[A-Za-z0-9_-]{1,128}")


@dataclass(frozen=True)
class ReviewedImportClient:
    platform: str
    client_id: str
    version: str
    review_issue: str
    allow_copy: bool
    allow_qr: bool


def reviewed_import_keys(
    clients: tuple[ReviewedImportClient, ...],
) -> frozenset[tuple[str, str, str]]:
    """Fail-closed startup validation; empty is the shipping default."""
    if not isinstance(clients, tuple):
        raise ValueError("Reviewed clients must be immutable trusted configuration")
    seen: set[tuple[str, str, str]] = set()
    for client in clients:
        if (not isinstance(client, ReviewedImportClient)
                or client.platform not in PLATFORMS
                or not isinstance(client.client_id, str)
                or not _ID.fullmatch(client.client_id)
                or not isinstance(client.version, str)
                or not _ID.fullmatch(client.version)
                or not isinstance(client.review_issue, str)
                or not _REVIEW.fullmatch(client.review_issue)
                or type(client.allow_copy) is not bool
                or type(client.allow_qr) is not bool
                or not (client.allow_copy or client.allow_qr)):
            raise ValueError("Invalid reviewed client/version evidence")
        key = (client.platform, client.client_id, client.version)
        if key in seen:
            raise ValueError("Duplicate reviewed client/version")
        seen.add(key)
    return frozenset(seen)


def validate_subscription_url(raw: object, *, expected_origin: str) -> str | None:
    """Return the exact HTTPS bearer string only on an explicitly reviewed origin.

    Do not normalize or redirect a bearer URL: normalization may change
    token semantics. Never accept credentials, fragments, control chars,
    backslashes, or another origin/port. No logging.
    """
    origin = urlsplit(expected_origin)
    if (origin.scheme != "https" or not origin.netloc or not origin.hostname
            or origin.username or origin.password or origin.path
            or origin.query or origin.fragment
            or expected_origin != "https://" + origin.netloc):
        return None
    if (not isinstance(raw, str) or not 12 <= len(raw) <= 2048
            or raw != raw.strip() or any(ord(c) < 0x21 or ord(c) == 0x7f for c in raw)
            or "\\" in raw or "{" in raw or "}" in raw):
        return None
    try:
        parsed = urlsplit(raw)
        if (parsed.scheme != "https" or parsed.netloc != origin.netloc
                or parsed.username or parsed.password or parsed.fragment
                or not parsed.path or parsed.path == "/"
                or parsed.hostname != origin.hostname):
            return None
        # Deliberately allow a query: existing provider-neutral URL templates
        # may carry bearer parameters. The entire value stays inside no-store JSON.
        return raw
    except ValueError:
        return None


async def owner_bound_subscription_url(
    *, customer_service: object, authenticated_owner: int,
    expected_origin: str,
) -> str | None:
    """Obtain a fresh owner-scoped card and fail closed on *any* uncertain state.

    CustomerPortalService.subscription_url() is deliberately NOT used here:
    it calls profile(read_access=False), which does not prove active entitlement.
    The card must be built from profile(read_access=True) at request time.
    """
    if (type(authenticated_owner) is not int
            or not 0 < authenticated_owner < 2**52
            or not callable(getattr(customer_service, "subscription_card", None))):
        return None
    try:
        card = await customer_service.subscription_card(authenticated_owner)
        profile = card.profile
        if (profile.exists is not True
                or profile.access_status != "active"
                or profile.period_status != "active"
                or not isinstance(profile.sub_id, str)
                or not _SUB_ID.fullmatch(profile.sub_id)):
            return None
        return validate_subscription_url(card.url, expected_origin=expected_origin)
    except Exception:
        return None
