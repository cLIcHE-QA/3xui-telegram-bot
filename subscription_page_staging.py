"""#887 D2d: separate, opt-in staging-only Bot API + localhost pilot runner.

No imports, configuration loading or network happen until an operator explicitly
invokes this entrypoint. Uses a DIFFERENT staging bot and synthetic customer DTO,
not production credentials, bot.sqlite3 or real 3x-ui subscriptions.

The TLS/edge side is a separately reviewed ingress. Never run behind an
unverified public reverse proxy; --run-approved-staging is NOT deploy approval.
"""
from __future__ import annotations

import argparse
import asyncio
import ipaddress
import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Mapping
from urllib.parse import urlsplit

from aiogram import Bot

from subscription_page_pilot_wiring import build_isolated_pilot, start_loopback_api


_CONFIG_FIELDS = frozenset({
    "mode", "enabled", "edge_reviewed", "https_origin", "bot_token_file",
    "expected_bot_id", "expected_bot_username", "pilot_ids",
    "sqlite_path", "loopback_port",
})
_DNS = re.compile(r"[a-z0-9](?:[a-z0-9.-]{1,251}[a-z0-9])?\Z")
_USERNAME = re.compile(r"[A-Za-z0-9_]{5,32}\Z")
_TOKEN = re.compile(r"([1-9][0-9]{4,15}):[A-Za-z0-9_-]{30,}\Z")


@dataclass(frozen=True)
class StagingConfig:
    enabled: bool
    edge_reviewed: bool
    https_origin: str
    bot_token_file: str
    expected_bot_id: int
    expected_bot_username: str
    pilot_ids: frozenset[int]
    sqlite_path: str
    loopback_port: int

    @classmethod
    def parse(cls, obj: Mapping[str, object]) -> "StagingConfig":
        if not isinstance(obj, dict) or frozenset(obj) != _CONFIG_FIELDS:
            raise ValueError("Exact staging configuration fields are required")
        if obj["mode"] != "isolated-staging":
            raise ValueError("Production or ambiguous mode refused")
        if type(obj["enabled"]) is not bool or type(obj["edge_reviewed"]) is not bool:
            raise ValueError("Explicit staging and edge-review booleans required")
        origin = obj["https_origin"]
        if type(origin) is not str or len(origin) > 254:
            raise ValueError("Invalid staging origin")
        url = urlsplit(origin)
        if (url.scheme != "https" or url.username or url.password
                or url.port is not None or url.path or url.query or url.fragment
                or not url.hostname or origin != "https://" + url.hostname
                or not _DNS.fullmatch(url.hostname)
                or ".." in url.hostname or "." not in url.hostname
                or not any("staging" in label for label in url.hostname.split("."))):
            raise ValueError("A dedicated canonical staging HTTPS DNS origin is required")
        try:
            ipaddress.ip_address(url.hostname)
        except ValueError:
            pass
        else:
            raise ValueError("An IP address is not a staging origin")
        username = obj["expected_bot_username"]
        if (type(username) is not str or not _USERNAME.fullmatch(username)
                or "staging" not in username.casefold()
                or not username.casefold().endswith("bot")):
            raise ValueError("A separate, explicitly named staging bot is required")
        bot_id = obj["expected_bot_id"]
        if type(bot_id) is not int or not 0 < bot_id < 2**52:
            raise ValueError("Explicit expected staging Bot API identity required")
        owners = obj["pilot_ids"]
        if (type(owners) is not list or not 1 <= len(owners) <= 8
                or any(type(i) is not int or not 0 < i < 2**52 for i in owners)
                or len(set(owners)) != len(owners)):
            raise ValueError("Small, explicit private staging owner allowlist required")
        port = obj["loopback_port"]
        if type(port) is not int or not 1024 <= port <= 65535:
            raise ValueError("Fixed unprivileged loopback port required")
        token_file, ledger = obj["bot_token_file"], obj["sqlite_path"]
        for value in (token_file, ledger):
            if (type(value) is not str or not Path(value).is_absolute()
                    or ".." in Path(value).parts):
                raise ValueError("Absolute private staging file paths are required")
        if (Path(ledger).name != "standalone-pilot.sqlite3"
                or Path(token_file).name != "staging-bot.token"
                or Path(token_file).parent != Path(ledger).parent):
            raise ValueError("Dedicated staging secret and SQLite directory required")
        return cls(
            enabled=obj["enabled"], edge_reviewed=obj["edge_reviewed"],
            https_origin=origin, bot_token_file=token_file,
            expected_bot_id=bot_id, expected_bot_username=username,
            pilot_ids=frozenset(owners), sqlite_path=ledger,
            loopback_port=port,
        )


def _read_private_file(path: str) -> bytes:
    """No symlinks, no world/group access, no logs of credentials or config."""
    file = Path(path)
    parent = file.parent
    try:
        directory = parent.lstat()
        item = file.lstat()
        if (not stat.S_ISDIR(directory.st_mode) or directory.st_uid != os.getuid()
                or stat.S_IMODE(directory.st_mode) != 0o700
                or not stat.S_ISREG(item.st_mode) or item.st_uid != os.getuid()
                or stat.S_IMODE(item.st_mode) != 0o600
                or item.st_nlink != 1 or not 0 < item.st_size <= 4096):
            raise ValueError("Private staging file permissions or type denied")
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
        fd = os.open(file, flags)
        try:
            opened = os.fstat(fd)
            if opened.st_ino != item.st_ino or opened.st_dev != item.st_dev:
                raise ValueError("Staging file changed during verification")
            data = os.read(fd, 4097)
        finally:
            os.close(fd)
        if not 0 < len(data) <= 4096:
            raise ValueError("Staging file exceeds private size limit")
        return data
    except OSError:
        raise ValueError("Required private staging file unavailable") from None


def load_staging_config(path: str) -> StagingConfig:
    if type(path) is not str or Path(path).name != "staging-config.json":
        raise ValueError("Dedicated private staging-config.json is required")
    try:
        obj = json.loads(_read_private_file(path).decode("utf-8"))
    except (ValueError, UnicodeError, json.JSONDecodeError):
        raise ValueError("Invalid private staging configuration") from None
    return StagingConfig.parse(obj)


def read_staging_bot_token(cfg: StagingConfig) -> str:
    token = _read_private_file(cfg.bot_token_file)
    try:
        secret = token.decode("ascii").strip()
    except UnicodeError:
        raise ValueError("Invalid private staging bot token") from None
    match = _TOKEN.fullmatch(secret)
    if match is None or int(match.group(1)) != cfg.expected_bot_id:
        raise ValueError("Staging Bot API token identity mismatch")
    return secret


async def verify_staging_bot(bot: Bot, cfg: StagingConfig) -> None:
    """Read-only getMe, fail-closed before opening the local web listener."""
    # Never expose a Bot API transport exception / request URL in logs:
    # the request path may contain the staging Bot token.
    try:
        me = await bot.get_me()
        if (getattr(me, "is_bot", None) is not True
                or getattr(me, "id", None) != cfg.expected_bot_id
                or getattr(me, "username", None) != cfg.expected_bot_username):
            raise ValueError("Remote staging Bot API identity mismatch")
        webhook = await bot.get_webhook_info()
        if getattr(webhook, "url", None) != "":
            raise ValueError("A separate staging bot must have no active webhook")
    except Exception:
        raise ValueError("Staging Bot API identity preflight denied") from None


class _SyntheticFlags:
    async def snapshot(self):
        return SimpleNamespace(portal_enabled=True)


class _SyntheticCustomer:
    """Never touches real subscribers, database, provider, billing or HWID."""

    def __init__(self, owners: frozenset[int]):
        self.owners = owners

    async def profile(self, owner: int):
        return SimpleNamespace(
            exists=type(owner) is int and owner in self.owners,
            access_status="unknown", period_status="unknown",
            plan_name="Изолированный staging (синтетические данные)",
            expiry_time=None, expiry_known=False, available_locations=None,
        )


async def run_approved_staging(
    cfg: StagingConfig, *, explicitly_enabled: bool = False,
) -> None:
    """Single staging Bot polling process plus separate loopback web API.

    All real Bot API traffic is confined to the explicitly verified staging
    Bot identity. The independently reviewed HTTPS edge and operator approval
    MUST exist before invoking; this function does not configure TLS/DNS.
    """
    if explicitly_enabled is not True or cfg.enabled is not True or cfg.edge_reviewed is not True:
        raise ValueError("Staging runtime requires independent explicit security review")
    hostname = urlsplit(cfg.https_origin).hostname or ""
    if hostname.endswith((".invalid", ".test", ".localhost")):
        raise ValueError("A real, dedicated staging DNS name is required for live testing")
    token = read_staging_bot_token(cfg)
    async with Bot(token=token) as bot:
        await verify_staging_bot(bot, cfg)
        bundle = build_isolated_pilot(
            explicitly_enabled=True,
            https_origin=cfg.https_origin,
            sqlite_path=cfg.sqlite_path,
            customer_service=_SyntheticCustomer(cfg.pilot_ids),
            feature_flags=_SyntheticFlags(),
            pilot_ids=cfg.pilot_ids,
            display_full_challenge=True,
        )
        listener = await start_loopback_api(
            bundle, explicitly_enabled=True, host="127.0.0.1",
            port=cfg.loopback_port,
        )
        try:
            # The token MUST belong to a separate bot with no other poller or
            # production webhook. No command menu/WebApp deployment mutation.
            await bundle.dispatcher.start_polling(
                bot, allowed_updates=["message", "callback_query"],
                handle_signals=False, close_bot_session=False,
                polling_timeout=10,
            )
        finally:
            await listener.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Isolated staging pilot (default OFF)")
    parser.add_argument("config_file", help="0600 JSON in a private 0700 directory")
    parser.add_argument("--run-approved-staging", action="store_true")
    args = parser.parse_args()
    cfg = load_staging_config(args.config_file)
    if not args.run_approved_staging:
        # No token read, Bot API, HTTP listener or feature activation.
        print("Staging configuration verified; network remains OFF")
        return
    asyncio.run(run_approved_staging(cfg, explicitly_enabled=True))


if __name__ == "__main__":
    main()
