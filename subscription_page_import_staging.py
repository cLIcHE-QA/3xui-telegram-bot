"""#887 D3i: отдельная staging-only сборка D3e import-preflight, default OFF.

Ни один импорт модуля не создаёт ledger, listener, Telegram poller или URL.
Сборка доступна только для того же process/host, что D2d standalone
session. Источник данных — строго synthetic D2d service, не production.
Доставка bearer запрещена безусловно, даже при включённом preflight.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from aiohttp import web

from subscription_page_customer import MiniAppSessions
from subscription_page_import_http import create_import_preflight_app
from subscription_page_import_sqlite import ImportSQLiteLedger
from subscription_page_pilot_wiring import IsolatedPilot
from subscription_page_staging import _SyntheticCustomer, _SyntheticFlags

_LEDGER = "import-staging.sqlite3"
_LOOPBACK = "127.0.0.1"


@dataclass(frozen=True)
class IsolatedImportStaging:
    """Только HTTP factory. Никогда не содержит production entitlement/URL."""

    app: web.Application
    ledger: ImportSQLiteLedger


@dataclass
class IsolatedImportListener:
    """Явно запускаемый локальный listener, не public HTTPS ingress."""

    runner: web.AppRunner
    port: int

    async def close(self) -> None:
        await self.runner.cleanup()


def build_isolated_import_staging(
    *,
    explicitly_enabled: bool = False,
    pilot_bundle: IsolatedPilot,
    import_sqlite_path: str,
    csrf_secret: bytes,
    preflight_enabled: bool = False,
    now: Callable[[], float] = time.time,
) -> IsolatedImportStaging:
    """Использует ТУ ЖЕ standalone D2d session/owner/host, что и бот.

    Отдельный SQLite предназначен только для HMAC/digest proof, не bearer.
    D2a Mini App здесь намеренно не подключён (fresh empty session store).
    """
    if explicitly_enabled is not True or type(preflight_enabled) is not bool:
        raise ValueError("Explicit staging-only feature gate required")
    if not isinstance(pilot_bundle, IsolatedPilot):
        raise ValueError("Verified D2d staging bundle required")
    pilot = pilot_bundle.pilot
    if (type(pilot.service) is not _SyntheticCustomer
            or type(pilot.flags) is not _SyntheticFlags
            or pilot.service.owners != pilot.pilot_ids
            or pilot.ledger is None):
        raise ValueError("Only synthetic single-host D2d staging is supported")
    if not isinstance(import_sqlite_path, str) or not Path(import_sqlite_path).is_absolute():
        raise ValueError("Absolute private staging ledger path required")
    target = Path(import_sqlite_path)
    if (target.name != _LEDGER or target.parent != pilot.ledger.path.parent
            or target == pilot.ledger.path):
        raise ValueError("Separate co-located staging ledger required")
    if not callable(now) or now is not pilot.now:
        raise ValueError("Single trusted D2d staging clock required")
    if not isinstance(csrf_secret, bytes) or len(csrf_secret) < 32:
        raise ValueError("Private staging CSRF secret required")

    # This creates only a private SQLite file, after all guards have passed.
    # No Telegram, VPS, DNS, TLS or subscription provider request is made.
    ledger = ImportSQLiteLedger(import_sqlite_path, https_origin=pilot.https_origin)
    app = create_import_preflight_app(
        https_origin=pilot.https_origin, ledger=ledger,
        mini_sessions=MiniAppSessions(ttl=120),
        standalone=pilot, customer_service=pilot.service,
        feature_flags=pilot.flags, pilot_ids=pilot.pilot_ids,
        enabled=preflight_enabled, now=pilot.now,
        csrf_secret=csrf_secret,
        delivery_enabled=False, subscription_origin=None,
        reviewed_clients=(),
    )
    return IsolatedImportStaging(app=app, ledger=ledger)


async def start_isolated_import_loopback(
    staging: IsolatedImportStaging, *,
    explicitly_enabled: bool = False,
    host: str = _LOOPBACK, port: int = 0,
) -> IsolatedImportListener:
    """Only explicit, separate 127.0.0.1 source-level staging start.

    This is NOT called by app_runtime or the existing D2d staging runner.
    Public TLS/edge review and operator deployment approval remain separate.
    """
    if explicitly_enabled is not True or not isinstance(staging, IsolatedImportStaging):
        raise ValueError("Explicitly enabled isolated import instance required")
    if host != _LOOPBACK or type(port) is not int or not 0 <= port <= 65535:
        raise ValueError("Only explicit IPv4 loopback bind permitted")
    runner = web.AppRunner(staging.app, access_log=None, handle_signals=False)
    await runner.setup()
    try:
        site = web.TCPSite(runner, _LOOPBACK, port)
        await site.start()
        addresses = runner.addresses
        if (len(addresses) != 1 or addresses[0][0] != _LOOPBACK
                or type(addresses[0][1]) is not int):
            raise RuntimeError("Unexpected non-loopback listener")
        return IsolatedImportListener(runner=runner, port=addresses[0][1])
    except BaseException:
        await runner.cleanup()
        raise
