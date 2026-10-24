"""#887 D2a: isolated, opt-in Telegram Mini App customer auth boundary.

No listener is started and app_runtime never imports this module.  In particular,
subscription URLs, sub_id, initDataUnsafe and admin sessions are not credentials.
Standalone authentication is a separate, not-yet-implemented protocol.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import time
from dataclasses import dataclass
from typing import Callable
from urllib.parse import parse_qsl, urlsplit

from aiohttp import web

COOKIE = "__Host-subpage-customer"
AUTH_MAX_AGE = 300
FUTURE_SKEW = 30
MAX_INIT_DATA_BYTES = 8192
MAX_SESSIONS = 256
MAX_REPLAY_PROOFS = 1024
MAX_LOGIN_SOURCES = 1024
LOGIN_WINDOW = 60
LOGIN_LIMIT = 12
COOKIE_TTL = 900
PATH = "/api/subpage/v1"
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_KEY = re.compile(r"[a-z][a-z0-9_]*\Z")


class InvalidMiniAppAuth(ValueError):
    """Deliberately generic: never echo Telegram payloads into logs or HTTP."""


@dataclass(frozen=True)
class VerifiedMiniAppIdentity:
    telegram_id: int
    auth_date: int
    proof: bytes


def verify_telegram_init_data(
    raw: str, bot_token: str, *, now: int | float | None = None,
    max_age: int = AUTH_MAX_AGE,
) -> VerifiedMiniAppIdentity:
    """Verify Telegram's bot-token HMAC on the *raw* Mini App initData string.

    Follow the bot-owned HMAC algorithm, not the third-party Ed25519 algorithm.
    Every received key except hash (including signature, if present) is signed.
    """
    if not isinstance(bot_token, str) or len(bot_token) < 12:
        raise ValueError("A dedicated bot token is required")
    if type(max_age) is not int or not 1 <= max_age <= AUTH_MAX_AGE:
        raise ValueError("Unbounded initData lifetime")
    if not isinstance(raw, str):
        raise InvalidMiniAppAuth("Invalid Mini App authentication")
    try:
        raw_size = len(raw.encode("utf-8"))
        if not 1 <= raw_size <= MAX_INIT_DATA_BYTES:
            raise InvalidMiniAppAuth("Invalid Mini App authentication")
        pairs = parse_qsl(
            raw, keep_blank_values=True, strict_parsing=True,
            encoding="utf-8", errors="strict", max_num_fields=32,
        )
        if not pairs or len({key for key, _ in pairs}) != len(pairs):
            raise InvalidMiniAppAuth("Invalid Mini App authentication")
        if any(not _KEY.fullmatch(key) for key, _ in pairs):
            raise InvalidMiniAppAuth("Invalid Mini App authentication")
        params = dict(pairs)
        received_hash = params.pop("hash", "")
        if not _HASH.fullmatch(received_hash):
            raise InvalidMiniAppAuth("Invalid Mini App authentication")
        signed = "\n".join(f"{key}={params[key]}" for key in sorted(params))
        secret = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
        expected = hmac.new(secret, signed.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(received_hash, expected):
            raise InvalidMiniAppAuth("Invalid Mini App authentication")

        raw_date = params.get("auth_date", "")
        if not raw_date.isascii() or not raw_date.isdecimal() or len(raw_date) > 12:
            raise InvalidMiniAppAuth("Invalid Mini App authentication")
        auth_date = int(raw_date)
        clock = time.time() if now is None else now
        if not isinstance(clock, (int, float)) or not 0 < clock < 10**12:
            raise ValueError("Invalid server clock")
        if auth_date <= 0 or auth_date > clock + FUTURE_SKEW or clock - auth_date > max_age:
            raise InvalidMiniAppAuth("Invalid Mini App authentication")
        # Reject floats/bools, bogus users and ID overflow before minting a session.
        user = json.loads(params.get("user", "null"))
        if not isinstance(user, dict) or type(user.get("id")) is not int:
            raise InvalidMiniAppAuth("Invalid Mini App authentication")
        user_id = user["id"]
        if not 0 < user_id < 2**52 or user.get("is_bot") is True:
            raise InvalidMiniAppAuth("Invalid Mini App authentication")
        return VerifiedMiniAppIdentity(
            telegram_id=user_id,
            auth_date=auth_date,
            proof=hashlib.sha256(received_hash.encode("ascii")).digest(),
        )
    except (ValueError, UnicodeError, OverflowError) as exc:
        if isinstance(exc, InvalidMiniAppAuth):
            raise
        raise InvalidMiniAppAuth("Invalid Mini App authentication") from None


class MiniAppSessions:
    """Bounded process-local customer cookies and one-time login proofs."""

    def __init__(self, *, ttl: int = COOKIE_TTL):
        if type(ttl) is not int or not 60 <= ttl <= COOKIE_TTL:
            raise ValueError("Invalid customer session lifetime")
        self.ttl = ttl
        self.sessions: dict[str, tuple[int, float]] = {}
        self.proofs: dict[bytes, float] = {}

    def _prune(self, now: float) -> None:
        for key, (_, expiry) in list(self.sessions.items()):
            if expiry <= now:
                del self.sessions[key]
        for key, expiry in list(self.proofs.items()):
            if expiry <= now:
                del self.proofs[key]

    def issue(self, identity: VerifiedMiniAppIdentity, now: float) -> str:
        self._prune(now)
        if identity.proof in self.proofs:
            raise InvalidMiniAppAuth("Invalid Mini App authentication")
        if len(self.sessions) >= MAX_SESSIONS or len(self.proofs) >= MAX_REPLAY_PROOFS:
            raise web.HTTPServiceUnavailable(text="Customer sessions unavailable")
        token = secrets.token_urlsafe(32)
        self.sessions[token] = (identity.telegram_id, now + self.ttl)
        self.proofs[identity.proof] = now + AUTH_MAX_AGE
        return token

    def user(self, token: str, now: float) -> int | None:
        self._prune(now)
        if not isinstance(token, str) or not 30 <= len(token) <= 128:
            return None
        row = self.sessions.get(token)
        return row[0] if row is not None else None

    def revoke(self, token: str) -> None:
        self.sessions.pop(token, None)


def create_customer_mini_app(
    *, bot_token: str, https_origin: str, customer_service: object,
    feature_flags: object, pilot_ids: frozenset[int],
    now: Callable[[], float] = time.time,
    session_ttl: int = COOKIE_TTL,
) -> web.Application:
    """Build a separate HTTPS-only API; caller must wire reviewed TLS ingress.

    The pilot allowlist and current durable portal feature veto are checked on
    *every* request, not copied into a login-time cookie privilege.
    """
    url = urlsplit(https_origin)
    if (url.scheme != "https" or not url.hostname or url.username or url.password
            or url.path or url.query or url.fragment or not url.netloc
            or url.hostname.endswith(".")):
        raise ValueError("A canonical HTTPS origin is required")
    if not isinstance(bot_token, str) or len(bot_token) < 12:
        raise ValueError("A dedicated bot token is required")
    if (not isinstance(pilot_ids, frozenset) or not pilot_ids
            or any(type(value) is not int or not 0 < value < 2**52 for value in pilot_ids)):
        raise ValueError("An explicit, nonempty pilot allowlist is required")
    if not callable(now) or not callable(getattr(feature_flags, "snapshot", None)):
        raise ValueError("A current feature-state reader and clock are required")
    if not callable(getattr(customer_service, "profile", None)):
        raise ValueError("A provider-neutral customer service is required")

    sessions = MiniAppSessions(ttl=session_ttl)
    sources: dict[str, list[float]] = {}
    app = web.Application(client_max_size=MAX_INIT_DATA_BYTES + 1024)

    def guard_origin(request: web.Request) -> None:
        # Do not trust incoming X-Forwarded-* or custom header user IDs.
        if request.host != url.netloc or request.headers.get("Origin") != https_origin:
            raise web.HTTPForbidden(text="Customer origin denied")
        if request.query_string:
            raise web.HTTPBadRequest(text="Unexpected query parameters")

    def security_headers(response: web.StreamResponse) -> web.StreamResponse:
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
        return response

    @web.middleware
    async def security(request: web.Request, handler):
        try:
            # Host check even for cookie-authenticated GET and before routing.
            if request.host != url.netloc:
                raise web.HTTPForbidden(text="Customer host denied")
            return security_headers(await handler(request))
        except web.HTTPException as exc:
            security_headers(exc)
            raise

    async def allowed(telegram_id: int) -> bool:
        try:
            state = await feature_flags.snapshot()
            return telegram_id in pilot_ids and state.portal_enabled is True
        except Exception:
            return False

    def throttle(request: web.Request) -> None:
        current = now()
        for key, entries in list(sources.items()):
            active = [stamp for stamp in entries if 0 <= current - stamp < LOGIN_WINDOW]
            if active:
                sources[key] = active
            else:
                del sources[key]
        source = request.remote or "unknown"
        if source not in sources and len(sources) >= MAX_LOGIN_SOURCES:
            raise web.HTTPTooManyRequests(text="Customer login limited")
        entries = sources.setdefault(source, [])
        if len(entries) >= LOGIN_LIMIT:
            raise web.HTTPTooManyRequests(text="Customer login limited")
        entries.append(current)

    async def telegram_login(request: web.Request) -> web.Response:
        guard_origin(request)
        if request.content_type != "application/json":
            raise web.HTTPUnsupportedMediaType(text="JSON required")
        throttle(request)
        try:
            payload = await request.json()
            if (not isinstance(payload, dict) or set(payload) != {"initData"}
                    or not isinstance(payload["initData"], str)):
                raise InvalidMiniAppAuth("Invalid Mini App authentication")
            identity = verify_telegram_init_data(
                payload["initData"], bot_token, now=now(),
            )
            if not await allowed(identity.telegram_id):
                raise web.HTTPForbidden(text="Customer access denied")
            token = sessions.issue(identity, now())
        except (InvalidMiniAppAuth, ValueError, UnicodeError):
            raise web.HTTPUnauthorized(text="Invalid Mini App authentication") from None
        response = web.json_response({"authenticated": True, "mode": "telegram"})
        response.set_cookie(
            COOKIE, token, secure=True, httponly=True, samesite="Strict",
            path="/", max_age=sessions.ttl,
        )
        return response

    async def identity(request: web.Request) -> int:
        if request.query_string:
            raise web.HTTPBadRequest(text="Unexpected query parameters")
        token = request.cookies.get(COOKIE, "")
        telegram_id = sessions.user(token, now())
        if telegram_id is None:
            raise web.HTTPUnauthorized(text="Customer authentication required")
        if not await allowed(telegram_id):
            sessions.revoke(token)
            raise web.HTTPForbidden(text="Customer access denied")
        return telegram_id

    async def me(request: web.Request) -> web.Response:
        user_id = await identity(request)
        try:
            profile = await customer_service.profile(user_id)
        except Exception:
            raise web.HTTPServiceUnavailable(text="Customer data unavailable") from None
        if not profile.exists:
            raise web.HTTPForbidden(text="Customer access denied")
        # Explicit DTO allowlist: never serialize email, sub_id, URL, HWID or keys.
        access = profile.access_status
        if access not in {"active", "disabled", "expired", "suspended", "provisioning", "unknown"}:
            access = "unknown"
        expiry = profile.expiry_time
        return web.json_response({
            "subscription": {
                "status": access,
                "periodStatus": profile.period_status if isinstance(profile.period_status, str) else "unknown",
                "planName": profile.plan_name[:128] if isinstance(profile.plan_name, str) else "",
                "expiryTime": expiry if profile.expiry_known and type(expiry) is int and expiry >= 0 else None,
                "availableLocations": profile.available_locations if type(profile.available_locations) is int else None,
            }
        })

    async def logout(request: web.Request) -> web.Response:
        guard_origin(request)
        token = request.cookies.get(COOKIE, "")
        sessions.revoke(token)
        response = web.json_response({"authenticated": False})
        response.del_cookie(COOKIE, path="/", secure=True, httponly=True, samesite="Strict")
        return response

    app.middlewares.append(security)
    app.router.add_post(PATH + "/auth/telegram", telegram_login)
    app.router.add_get(PATH + "/me", me)
    app.router.add_post(PATH + "/logout", logout)
    return app
