"""#887 D2c: strictly opt-in assembly of a standalone pilot API and bot router.

No module import starts a listener, polls Telegram, modifies app_runtime, reads
the production DB/token or installs a new handler on the running bot.
The factory composes the *same* separate SQLite ledger for the HTTP API and
an isolated aiogram Dispatcher. The only permitted local HTTP bind is loopback.

Only an authenticated Telegram Bot API transport may feed Updates to this
Dispatcher in a separately reviewed future integration. Synthetic
Dispatcher.feed_update tests do not prove a real Telegram transport.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from aiogram import Dispatcher
from aiohttp import web

from subscription_page_standalone import StandalonePilot, create_standalone_pilot
from subscription_page_telegram_approval import StandaloneTelegramApproval


_LEDGER_NAME = "standalone-pilot.sqlite3"
_LOOPBACK = "127.0.0.1"


@dataclass(frozen=True)
class IsolatedPilot:
    """No bot, token, polling task, network listener or implicit runtime hook."""

    pilot: StandalonePilot
    dispatcher: Dispatcher
    approval: StandaloneTelegramApproval

    @property
    def app(self) -> web.Application:
        return self.pilot.app


@dataclass
class LoopbackAPI:
    """An explicitly started local HTTP listener; never an HTTPS ingress."""

    runner: web.AppRunner
    port: int

    async def close(self) -> None:
        await self.runner.cleanup()


def build_isolated_pilot(
    *, explicitly_enabled: bool = False,
    https_origin: str,
    sqlite_path: str,
    customer_service: object,
    feature_flags: object,
    pilot_ids: frozenset[int],
    now: Callable[[], float] = time.time,
    display_full_challenge: bool = False,
) -> IsolatedPilot:
    """Bind one private Telegram Router and one HTTP app to one SQLite ledger.

    The caller must supply an explicit pilot account allowlist and independently
    isolated customer service / durable feature flags; no settings/app_runtime
    dependency is silently loaded here.

    The database must live in a pre-existing 0700 directory, with a dedicated
    basename. The underlying ledger checks ownership, 0600, symlinks, its HTTPS
    origin pin and schema on each access. It is NOT multi-host storage.
    """
    if explicitly_enabled is not True:
        raise ValueError("Standalone pilot must be explicitly enabled")
    if type(display_full_challenge) is not bool:
        raise ValueError("Explicit anti-phishing display mode required")
    if not isinstance(sqlite_path, str) or (
        not Path(sqlite_path).is_absolute()
        or Path(sqlite_path).name != _LEDGER_NAME
    ):
        raise ValueError("A dedicated standalone-pilot.sqlite3 is required")
    pilot = create_standalone_pilot(
        https_origin=https_origin,
        customer_service=customer_service,
        feature_flags=feature_flags,
        pilot_ids=pilot_ids,
        now=now,
        sqlite_path=sqlite_path,
    )
    if pilot.ledger is None:
        raise ValueError("Shared standalone ledger required")
    dispatcher = Dispatcher()
    approval = StandaloneTelegramApproval(
        pilot, display_full_challenge=display_full_challenge,
    )
    dispatcher.include_router(approval.router)
    # Do NOT call start_polling, register a production handler, or start HTTP.
    return IsolatedPilot(pilot=pilot, dispatcher=dispatcher, approval=approval)


async def start_loopback_api(
    bundle: IsolatedPilot, *, explicitly_enabled: bool = False,
    host: str = _LOOPBACK, port: int = 0,
) -> LoopbackAPI:
    """Expose only local HTTP for a future separately reviewed TLS terminator.

    Never bind 0.0.0.0 or public network interfaces, and never claim this is
    a production-ready HTTPS endpoint. No implicit real Bot API polling.
    """
    if explicitly_enabled is not True or not isinstance(bundle, IsolatedPilot):
        raise ValueError("A deliberately enabled isolated pilot is required")
    if host != _LOOPBACK or type(port) is not int or not 0 <= port <= 65535:
        raise ValueError("Only an explicit IPv4 loopback bind is permitted")
    runner = web.AppRunner(bundle.app, access_log=None, handle_signals=False)
    await runner.setup()
    try:
        site = web.TCPSite(runner, _LOOPBACK, port)
        await site.start()
        # aiohttp exposes the bound addresses after startup.
        addresses = runner.addresses
        if len(addresses) != 1 or addresses[0][0] != _LOOPBACK:
            raise RuntimeError("Unexpected non-loopback listener")
        bound = addresses[0][1]
        if type(bound) is not int or not 0 < bound <= 65535:
            raise RuntimeError("Invalid loopback listener")
        return LoopbackAPI(runner=runner, port=bound)
    except BaseException:
        await runner.cleanup()
        raise
