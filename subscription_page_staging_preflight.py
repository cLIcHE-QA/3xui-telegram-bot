"""#887 D2e: bounded, read-only, opt-in staging HTTPS edge preflight.

Default invocation reads ONLY an owner-private staging JSON configuration.
No token, Bot API, HTTP listener, request, DNS query or process mutation.
An independently approved public staging direct-TCP edge may be probed with
five bounded HEAD requests. This does NOT test rate limits, real Telegram,
physical devices or grant deployment / production acceptance.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import http.client
import ipaddress
import json
import socket
import ssl
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlsplit

from aiogram import Bot

from subscription_page_staging import (
    StagingConfig, load_staging_config, read_staging_bot_token,
    verify_staging_bot,
)

_TIMEOUT = 4.0
_DENIED_PATHS = (
    "/admin/",
    "/compat/",
    "/api/subpage/v1/auth/standalone/approve",
)
_BAD_HOST = "untrusted-host.invalid"
_TLS_VERSIONS = frozenset({"TLSv1.2", "TLSv1.3"})


@dataclass(frozen=True)
class EdgeReply:
    status: int
    headers: dict[str, str]
    tls_version: str
    cert_sha256: str


def _resolve_public_address(hostname: str) -> tuple[int, str]:
    """Fail closed on any private/special DNS answer; select one pinned IP.

    Resolving is opt-in and happens exactly once; requests never resolve again.
    A private/VPN staging edge needs a separate reviewed testing topology, not
    a bypass of this PUBLIC direct-TCP probe.
    """
    answers = socket.getaddrinfo(
        hostname, 443, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP,
    )
    addresses: set[tuple[int, str]] = set()
    for family, _, _, _, sock_addr in answers:
        if family not in (socket.AF_INET, socket.AF_INET6):
            raise ValueError("Unsupported staging DNS address family")
        address = ipaddress.ip_address(sock_addr[0])
        if (not address.is_global or address.is_multicast
                or getattr(address, "ipv4_mapped", None) is not None):
            raise ValueError("Non-public staging DNS address refused")
        addresses.add((family, str(address)))
    if not addresses:
        raise ValueError("Staging DNS address missing")
    return sorted(addresses, key=lambda item: (item[0] != socket.AF_INET, item[1]))[0]


def _tls_head(family: int, address: str, hostname: str, path: str,
              host_header: str) -> EdgeReply:
    """Verified-system-CA TLS, pinned IP, SNI=approved hostname, HEAD only."""
    if path not in ("/", *_DENIED_PATHS) or host_header not in (hostname, _BAD_HOST):
        raise ValueError("Unexpected edge probe request")
    if family not in (socket.AF_INET, socket.AF_INET6):
        raise ValueError("Unsupported address family")
    ctx = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.set_alpn_protocols(["http/1.1"])
    with socket.socket(family, socket.SOCK_STREAM) as raw:
        raw.settimeout(_TIMEOUT)
        endpoint = (address, 443) if family == socket.AF_INET else (address, 443, 0, 0)
        raw.connect(endpoint)
        with ctx.wrap_socket(raw, server_hostname=hostname) as secured:
            secured.settimeout(_TIMEOUT)
            tls_version = secured.version() or ""
            certificate = secured.getpeercert(binary_form=True)
            if tls_version not in _TLS_VERSIONS or not certificate:
                raise ValueError("Unverified TLS version/certificate")
            fingerprint = hashlib.sha256(certificate).hexdigest()
            request = (
                f"HEAD {path} HTTP/1.1\r\n"
                f"Host: {host_header}\r\n"
                "Connection: close\r\n"
                "User-Agent: staging-readonly-preflight/1\r\n"
                "\r\n"
            )
            secured.sendall(request.encode("ascii"))
            reply = http.client.HTTPResponse(secured)
            try:
                reply.begin()
            except (http.client.RemoteDisconnected, ConnectionResetError, BrokenPipeError):
                # Expected for Nginx return 444 on the deliberately wrong Host.
                return EdgeReply(0, {}, tls_version, fingerprint)
            try:
                headers = {k.lower(): v for k, v in reply.getheaders()}
                return EdgeReply(reply.status, headers, tls_version, fingerprint)
            finally:
                reply.close()


def _check_public_origin(cfg: StagingConfig, approved_origin: str) -> str:
    if type(approved_origin) is not str or cfg.https_origin != approved_origin:
        raise ValueError("Reviewed origin must exactly match private staging config")
    url = urlsplit(cfg.https_origin)
    hostname = url.hostname
    if (url.scheme != "https" or not hostname
            or cfg.https_origin != "https://" + hostname
            or "." not in hostname
            or not any("staging" in label for label in hostname.split("."))
            or hostname.endswith((".invalid", ".test", ".example", ".localhost", ".local"))
            or any(ord(char) > 127 for char in hostname)):
        raise ValueError("Real dedicated staging HTTPS origin required")
    return hostname


def _validate_security_headers(reply: EdgeReply) -> None:
    if reply.status != 200:
        raise ValueError("Staging root not served directly with HTTP 200")
    required = {
        "cache-control": "no-store",
        "referrer-policy": "no-referrer",
        "x-content-type-options": "nosniff",
        "x-frame-options": "DENY",
    }
    if any(reply.headers.get(key, "").lower() != value.lower()
           for key, value in required.items()):
        raise ValueError("Missing staging no-store / anti-framing headers")
    hsts = reply.headers.get("strict-transport-security", "")
    if not hsts.startswith("max-age=") or not hsts[8:].split(";")[0].isdigit():
        raise ValueError("Staging HSTS missing")
    csp = reply.headers.get("content-security-policy", "")
    if "frame-ancestors 'none'" not in csp or "default-src 'none'" not in csp:
        raise ValueError("Staging CSP missing")
    if "set-cookie" in reply.headers or "location" in reply.headers:
        raise ValueError("Staging static root must not set cookies or redirect")


def probe_approved_public_edge(
    cfg: StagingConfig, *, approved_origin: str,
    direct_tcp_confirmed: bool = False,
    resolver: Callable[[str], tuple[int, str]] | None = None,
    request: Callable[[int, str, str, str, str], EdgeReply] | None = None,
) -> dict[str, object]:
    """Five bounded HEAD requests, no credentials, sessions or POST/rate bursts.

    The direct-TCP topology and owned DNS must have been independently reviewed;
    the booleans are explicit human attestations, not cryptographic evidence.
    """
    if (direct_tcp_confirmed is not True or cfg.edge_reviewed is not True
            or cfg.enabled is not False):
        raise ValueError("Reviewed direct-TCP edge with bot disabled is required")
    hostname = _check_public_origin(cfg, approved_origin)
    resolve = resolver if resolver is not None else _resolve_public_address
    head = request if request is not None else _tls_head
    family, address = resolve(hostname)

    def query(path: str, host_header: str = hostname) -> EdgeReply:
        value = head(family, address, hostname, path, host_header)
        if (not isinstance(value, EdgeReply)
                or value.tls_version not in _TLS_VERSIONS
                or len(value.cert_sha256) != 64
                or any(char not in "0123456789abcdef" for char in value.cert_sha256)):
            raise ValueError("Staging TLS evidence invalid")
        return value

    root = query("/")
    _validate_security_headers(root)
    for path in _DENIED_PATHS:
        reply = query(path)
        if reply.status != 404 or reply.cert_sha256 != root.cert_sha256:
            raise ValueError("Staging forbidden path exposed or TLS certificate drift")
    denied_host = query("/", _BAD_HOST)
    if (denied_host.status not in (0, 400, 403, 404, 421, 444)
            or denied_host.cert_sha256 != root.cert_sha256):
        raise ValueError("Staging wrong-Host request accepted")
    return {
        "status": "PARTIAL",
        "scope": "read_only_public_https_edge",
        "edge_probe": "PASS",
        "requests_sent": 5,
        "tls_certificate_sha256": root.cert_sha256,
        "edge_rate_limits": "PENDING",
        "real_telegram_identity": "PENDING",
        "mobile_webview": "PENDING",
        "overall_acceptance": "PENDING",
    }



async def check_approved_telegram_identity(
    cfg: StagingConfig, *, reviewed_username: str,
    explicitly_authorized: bool = False,
    bot_factory: Callable[..., object] | None = None,
) -> dict[str, object]:
    """Read-only getMe/getWebhookInfo; never poll, send, setWebhook or mutate.

    Requires a separate owner-private staging token file and exact, externally
    reviewed staging bot username. No bot is initialized before these gates.
    """
    if (explicitly_authorized is not True or cfg.enabled is not False
            or type(reviewed_username) is not str
            or reviewed_username != cfg.expected_bot_username):
        raise ValueError("Read-only Bot API identity review denied")
    token = read_staging_bot_token(cfg)
    factory = bot_factory if bot_factory is not None else Bot
    async with factory(token=token) as bot:
        await asyncio.wait_for(verify_staging_bot(bot, cfg), timeout=12)
    return {
        "status": "PARTIAL",
        "scope": "read_only_staging_bot_identity",
        "bot_identity_and_webhook": "PASS",
        "bot_api_methods": ["getMe", "getWebhookInfo"],
        "polling_or_mutations": "NONE",
        "dns_tls_edge": "PENDING",
        "edge_rate_limits": "PENDING",
        "mobile_webview": "PENDING",
        "overall_acceptance": "PENDING",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="D2e staging edge preflight; default OFF")
    parser.add_argument("config_file", help="Private 0600 staging-config.json")
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--probe-approved-public-edge", action="store_true")
    actions.add_argument("--verify-approved-bot-identity", action="store_true")
    parser.add_argument("--reviewed-origin")
    parser.add_argument("--direct-tcp-confirmed", action="store_true")
    parser.add_argument("--reviewed-bot-username")
    parser.add_argument("--explicit-telegram-readonly", action="store_true")
    args = parser.parse_args(argv)
    try:
        cfg = load_staging_config(args.config_file)
        if args.probe_approved_public_edge:
            if args.reviewed_bot_username is not None or args.explicit_telegram_readonly:
                raise ValueError("Mixing Bot API and edge preflight denied")
            report = probe_approved_public_edge(
                cfg, approved_origin=args.reviewed_origin,
                direct_tcp_confirmed=args.direct_tcp_confirmed,
            )
        elif args.verify_approved_bot_identity:
            if args.reviewed_origin is not None or args.direct_tcp_confirmed:
                raise ValueError("Mixing Bot API and edge preflight denied")
            report = asyncio.run(check_approved_telegram_identity(
                cfg, reviewed_username=args.reviewed_bot_username,
                explicitly_authorized=args.explicit_telegram_readonly,
            ))
        else:
            if (args.reviewed_origin is not None or args.direct_tcp_confirmed
                    or args.reviewed_bot_username is not None
                    or args.explicit_telegram_readonly):
                raise ValueError("Network-only flags require one explicit preflight mode")
            report = {
                "status": "PENDING", "scope": "offline_private_config_only",
                "config_schema_and_file_permissions": "PASS",
                "dns_tls_edge": "PENDING", "edge_rate_limits": "PENDING",
                "real_telegram_identity": "PENDING",
                "mobile_webview": "PENDING", "overall_acceptance": "PENDING",
                "requests_sent": 0,
            }
        print(json.dumps(report, sort_keys=True))
        return 0
    except Exception:
        # Never print exception details, token-bearing URLs, paths, IPs or IDs.
        print(json.dumps({
            "status": "BLOCKED", "scope": "staging_preflight",
            "reason": "private_config_or_public_edge_gate_denied",
            "overall_acceptance": "PENDING",
        }, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
