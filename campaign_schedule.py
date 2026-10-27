"""Closed, UI-independent schedule validation; never starts a job or listener."""
from dataclasses import dataclass
from datetime import datetime
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from service_campaigns import CampaignInvalid


MAX_SCHEDULE_AHEAD = 366 * 24 * 60 * 60
_LOCAL = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}")
_ZONE = re.compile(r"[A-Za-z0-9_+-]+(?:/[A-Za-z0-9_+-]+){0,3}")


@dataclass(frozen=True)
class CampaignSchedule:
    due_at: int
    timezone: str
    local_time: str


def parse_campaign_schedule(local_time, timezone, *, now):
    """Require an explicit IANA key (or UTC), rejecting DST folds and gaps.

    The accepted UTC instant is frozen; a later OS timezone-data update must not
    silently reinterpret the original confirmation. No implicit host timezone.
    """
    if type(now) is not int or not 0 < now <= 2**63 - 1:
        raise CampaignInvalid("Campaign clock unavailable")
    if (not isinstance(local_time, str) or not _LOCAL.fullmatch(local_time)
            or not isinstance(timezone, str) or len(timezone) > 100
            or not _ZONE.fullmatch(timezone)
            or (timezone != "UTC" and "/" not in timezone)
            or timezone.startswith(("posix/", "right/"))):
        raise CampaignInvalid("Invalid campaign schedule")
    try:
        naive = datetime.strptime(local_time, "%Y-%m-%dT%H:%M")
        zone = ZoneInfo(timezone)
        choices = set()
        for fold in (0, 1):
            instant = int(naive.replace(tzinfo=zone, fold=fold).timestamp())
            if datetime.fromtimestamp(instant, zone).replace(tzinfo=None) == naive:
                choices.add(instant)
        if len(choices) != 1:
            raise ValueError
        due = choices.pop()
        if not now < due <= now + MAX_SCHEDULE_AHEAD:
            raise ValueError
        return CampaignSchedule(due, timezone, local_time)
    except (ValueError, OverflowError, OSError, ZoneInfoNotFoundError):
        raise CampaignInvalid("Invalid campaign schedule") from None
