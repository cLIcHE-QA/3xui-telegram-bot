"""Fail-closed, durable Client Portal and Stars runtime feature switches.

The launch .env flags are immutable vetoes; operators may only reduce access.
Reading both switch rows and their revisions uses one SQLite snapshot. No cached
state is used for customer entry, invoice creation or pre-checkout.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from config import Settings
    from db import Database

FEATURE_KEYS = {
    "portal": "client_portal_enabled",
    "stars": "client_payment_acceptance_enabled",
}
MAX_REVISION = 2_147_483_646


def parse_override(value: object) -> bool | None:
    if value is None:
        return None
    if value == "true":
        return True
    if value == "false":
        return False
    raise ValueError("Invalid persisted runtime feature flag")


def parse_revision(value: object) -> int:
    if value is None:
        return 0
    if not isinstance(value, str) or not value.isascii() or not value.isdecimal():
        raise ValueError("Invalid persisted feature revision")
    number = int(value)
    if not 0 <= number <= MAX_REVISION:
        raise ValueError("Feature revision out of range")
    return number


def revision_key(flag_key: str) -> str:
    if flag_key not in FEATURE_KEYS.values():
        raise ValueError("Unknown feature key")
    return flag_key + ":revision"


@dataclass(frozen=True)
class FeatureSnapshot:
    available: bool
    env_portal: bool
    env_stars: bool
    db_portal: bool | None = None
    db_stars: bool | None = None
    portal_revision: int = 0
    stars_revision: int = 0

    @property
    def portal_enabled(self) -> bool:
        return self.available and self.env_portal and self.db_portal is not False

    @property
    def stars_enabled(self) -> bool:
        return self.portal_enabled and self.env_stars and self.db_stars is not False

    def reason(self, feature: str) -> str:
        if not self.available:
            return "⚠️ состояние SQLite недоступно или некорректно; запрещено"
        if feature == "portal":
            if not self.env_portal:
                return "запрет локальной конфигурации (.env)"
            if self.db_portal is False:
                return "отключено Owner в панели"
            return "разрешено (с учётом pilot allowlist)"
        if feature == "stars":
            if not self.env_stars:
                return "запрет локальной конфигурации (.env)"
            if not self.portal_enabled:
                return "клиентский портал отключён"
            if self.db_stars is False:
                return "отключено Owner в панели"
            return "разрешено для доступных pilot-аккаунтов"
        raise ValueError("Unknown feature")

    def revision(self, feature: str) -> int:
        return self.portal_revision if feature == "portal" else self.stars_revision


class ClientFeatureFlags:
    def __init__(self, db: Database, settings: Settings):
        self.db = db
        self.settings = settings

    async def snapshot(self) -> FeatureSnapshot:
        env_portal = bool(self.settings.client_portal_enabled)
        env_stars = bool(self.settings.client_payment_acceptance_enabled)
        try:
            rows = await self.db.get_feature_flag_records()
            portal = FEATURE_KEYS["portal"]
            stars = FEATURE_KEYS["stars"]
            return FeatureSnapshot(
                available=True,
                env_portal=env_portal,
                env_stars=env_stars,
                db_portal=parse_override(rows.get(portal)),
                db_stars=parse_override(rows.get(stars)),
                portal_revision=parse_revision(rows.get(revision_key(portal))),
                stars_revision=parse_revision(rows.get(revision_key(stars))),
            )
        except Exception:
            # In particular, never mistake a DB outage for absence of overrides.
            return FeatureSnapshot(available=False, env_portal=env_portal, env_stars=env_stars)
