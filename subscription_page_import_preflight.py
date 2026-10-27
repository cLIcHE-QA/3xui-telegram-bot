"""D3d offline-only owner eligibility policy for a future subscription import.

No HTTP route, URL, token, clipboard action or deployment integration.
Identity must originate from existing verified server-side session boundaries.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ImportEligibility:
    permitted: bool
    reason: str = "not-authorized"


async def check_import_eligibility(
    *, authenticated_owner: int, customer_service: object,
    feature_flags: object, pilot_ids: frozenset[int],
    explicitly_enabled: bool = False,
) -> ImportEligibility:
    """Fail closed; never return profile data or subscription credentials."""
    if explicitly_enabled is not True:
        return ImportEligibility(False)
    if (type(authenticated_owner) is not int
            or not 0 < authenticated_owner < 2**52
            or not isinstance(pilot_ids, frozenset)
            or authenticated_owner not in pilot_ids):
        return ImportEligibility(False)
    try:
        state = await feature_flags.snapshot()
        if state.portal_enabled is not True:
            return ImportEligibility(False)
        profile = await customer_service.profile(authenticated_owner)
        if (profile.exists is not True or profile.access_status != "active"
                or profile.period_status != "active"):
            return ImportEligibility(False)
        return ImportEligibility(True, "owner-eligible")
    except Exception:
        return ImportEligibility(False)
