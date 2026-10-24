"""#887 D2b: opt-in, offline-only standalone browser/Telegram approval exchange.

A public challenge is NOT a credential: only a verified private Telegram bot
interaction can approve it, and the original HttpOnly browser binding must still
be present to exchange the approval for a separate short-lived cookie.

No bot handler, listener, HTTPS ingress, or production route is installed here.
The deployer must not expose this factory before reviewed bot approval wiring,
shared state, trusted edge rate limits and real browser/device validation.
"""
from __future__ import annotations

import hashlib
import re
import secrets
import time
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlsplit

from aiohttp import web

from subscription_page_customer import PATH, public_customer_summary
from subscription_page_standalone_sqlite import StandaloneSQLiteLedger

PENDING_COOKIE = "__Host-subpage-standalone-bind"
SESSION_COOKIE = "__Host-subpage-standalone"
CHALLENGE_TTL = 180
SESSION_TTL = 600
MAX_PENDING = 128
MAX_SESSIONS = 128
MAX_SOURCES = 512
LOGIN_WINDOW = 60
LOGIN_LIMIT = 10
MAX_BODY = 2048
CHALLENGE_PATTERN = re.compile(r"[A-Za-z0-9_-]{16}\Z")
BASE = PATH + "/auth/standalone"


@dataclass
class _Pending:
    binding: bytes
    issued_at: float
    expires_at: float
    approved_owner: int | None = None


class StandalonePilot:
    """One-process pilot state. Never share this across unreviewed workers.

    approve_from_private_telegram() is a Python-only trusted bot-side entrypoint,
    NOT an HTTP route. Its actor_id/chat_id/confirmation MUST be constructed from
    a verified Telegram private Update and real user confirmation, not headers,
    messages forwarded by other actors, deep-link parameters or browser input.
    """

    def __init__(
        self, *, https_origin: str, customer_service: object,
        feature_flags: object, pilot_ids: frozenset[int],
        now: Callable[[], float] = time.time,
        pending_ttl: int = CHALLENGE_TTL,
        session_ttl: int = SESSION_TTL,
        sqlite_path: str | None = None,
    ) -> None:
        url = urlsplit(https_origin)
        if (url.scheme != "https" or not url.hostname or not url.netloc
                or url.username or url.password or url.path or url.query or url.fragment
                or url.hostname.endswith(".")):
            raise ValueError("Canonical HTTPS origin is required")
        if (not isinstance(pilot_ids, frozenset) or not pilot_ids
                or any(type(user) is not int or not 0 < user < 2**52 for user in pilot_ids)):
            raise ValueError("Explicit nonempty pilot owner allowlist is required")
        if (type(pending_ttl) is not int or not 30 <= pending_ttl <= CHALLENGE_TTL
                or type(session_ttl) is not int or not 60 <= session_ttl <= SESSION_TTL):
            raise ValueError("Bounded standalone session lifetime is required")
        if (not callable(now) or not callable(getattr(feature_flags, "snapshot", None))
                or not callable(getattr(customer_service, "profile", None))):
            raise ValueError("Fresh feature flags, owner service and server clock required")
        self.https_origin = https_origin
        self.host = url.netloc
        self.service = customer_service
        self.flags = feature_flags
        self.pilot_ids = pilot_ids
        self.now = now
        self.pending_ttl = pending_ttl
        self.session_ttl = session_ttl
        # Optional isolated atomic state, never the bot's production database.
        self.ledger = StandaloneSQLiteLedger(sqlite_path) if sqlite_path is not None else None
        self.pending: dict[str, _Pending] = {}
        # Only digests are stored server-side; neither cookie token is logged.
        self.sessions: dict[bytes, tuple[int, float]] = {}
        self.sources: dict[str, list[float]] = {}
        self.app = web.Application(
            middlewares=[self._security], client_max_size=MAX_BODY,
        )
        self.app.router.add_post(BASE + "/start", self._start)
        self.app.router.add_post(BASE + "/complete", self._complete)
        self.app.router.add_post(BASE + "/cancel", self._cancel)
        self.app.router.add_get(PATH + "/standalone/me", self._me)
        self.app.router.add_post(BASE + "/logout", self._logout)

    def _clock(self) -> float:
        current = self.now()
        if (not isinstance(current, (int, float)) or isinstance(current, bool)
                or not 0 < current < 10**12):
            raise web.HTTPServiceUnavailable(text="Standalone unavailable")
        return float(current)

    def _prune(self, current: float) -> None:
        if self.ledger is not None:
            # Atomic transactions in the ledger prune themselves.
            return
        for code, row in list(self.pending.items()):
            if current >= row.expires_at or current < row.issued_at:
                del self.pending[code]
        for digest, (_, expiry) in list(self.sessions.items()):
            if current >= expiry:
                del self.sessions[digest]

    @staticmethod
    def _hash(token: str) -> bytes:
        return hashlib.sha256(token.encode("utf-8")).digest()

    def _binding(self, request: web.Request) -> bytes | None:
        token = request.cookies.get(PENDING_COOKIE, "")
        if not isinstance(token, str) or not 40 <= len(token) <= 96:
            return None
        return self._hash(token)

    def _session(self, request: web.Request, current: float) -> int | None:
        token = request.cookies.get(SESSION_COOKIE, "")
        if not isinstance(token, str) or not 40 <= len(token) <= 96:
            return None
        if self.ledger is not None:
            return self.ledger.session_owner(self._hash(token), current=current)
        row = self.sessions.get(self._hash(token))
        if row is None or current >= row[1]:
            return None
        return row[0]

    def challenge_pending(self, challenge: str, current: float) -> bool:
        """Only current, unapproved challenges may open a private prompt."""
        if not isinstance(challenge, str) or not CHALLENGE_PATTERN.fullmatch(challenge):
            return False
        if self.ledger is not None:
            row = self.ledger.pending(self._hash(challenge), current=current)
            return row is not None and row[1] is None
        self._prune(current)
        row = self.pending.get(challenge)
        return row is not None and row.approved_owner is None

    async def _enabled(self, user_id: int | None = None) -> bool:
        try:
            state = await self.flags.snapshot()
            if state.portal_enabled is not True:
                return False
            return user_id is None or user_id in self.pilot_ids
        except Exception:
            return False

    async def _verified_owner(self, user_id: int) -> bool:
        if not await self._enabled(user_id):
            return False
        try:
            profile = await self.service.profile(user_id)
            return profile.exists is True
        except Exception:
            return False

    def _guard(self, request: web.Request, *, mutate: bool) -> None:
        if request.host != self.host:
            raise web.HTTPForbidden(text="Standalone origin denied")
        if request.query_string:
            raise web.HTTPBadRequest(text="Unexpected query")
        if mutate and request.headers.get("Origin") != self.https_origin:
            raise web.HTTPForbidden(text="Standalone origin denied")
        if mutate and request.content_type != "application/json":
            raise web.HTTPUnsupportedMediaType(text="JSON required")

    @staticmethod
    def _secure(response: web.StreamResponse) -> web.StreamResponse:
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        return response

    @web.middleware
    async def _security(self, request: web.Request, handler):
        try:
            if request.host != self.host:
                raise web.HTTPForbidden(text="Standalone origin denied")
            return self._secure(await handler(request))
        except web.HTTPException as exc:
            self._secure(exc)
            raise

    def _throttle(self, request: web.Request, current: float) -> None:
        # Never trust X-Forwarded-For supplied by the browser.
        for peer, entries in list(self.sources.items()):
            current_entries = [t for t in entries if 0 <= current - t < LOGIN_WINDOW]
            if current_entries:
                self.sources[peer] = current_entries
            else:
                del self.sources[peer]
        peer = request.remote or "unknown"
        if peer not in self.sources and len(self.sources) >= MAX_SOURCES:
            raise web.HTTPTooManyRequests(text="Standalone rate limit")
        entries = self.sources.setdefault(peer, [])
        if len(entries) >= LOGIN_LIMIT:
            raise web.HTTPTooManyRequests(text="Standalone rate limit")
        entries.append(current)

    @staticmethod
    async def _json(request: web.Request, *, keys: frozenset[str]) -> dict:
        try:
            data = await request.json()
        except (ValueError, UnicodeError):
            raise web.HTTPBadRequest(text="Invalid request") from None
        if not isinstance(data, dict) or frozenset(data) != keys:
            raise web.HTTPBadRequest(text="Invalid request")
        return data

    @staticmethod
    def _set_cookie(response: web.Response, name: str, token: str, ttl: int) -> None:
        response.set_cookie(
            name, token, httponly=True, secure=True, samesite="Strict",
            path="/", max_age=ttl,
        )

    @staticmethod
    def _clear_cookie(response: web.Response, name: str) -> None:
        response.del_cookie(name, path="/", secure=True, httponly=True, samesite="Strict")

    async def _start(self, request: web.Request) -> web.Response:
        self._guard(request, mutate=True)
        await self._json(request, keys=frozenset())
        current = self._clock()
        self._throttle(request, current)
        if not await self._enabled():
            raise web.HTTPForbidden(text="Standalone unavailable")
        self._prune(current)
        old_binding = self._binding(request)
        existing = request.cookies.get(SESSION_COOKIE, "")
        if self.ledger is not None:
            binding_token = secrets.token_urlsafe(32)
            old_session = self._hash(existing) if existing else None
            for _ in range(5):
                challenge = secrets.token_urlsafe(12)
                if self.ledger.begin(
                    self._hash(challenge), self._hash(binding_token),
                    current=current, expires=current + self.pending_ttl,
                    old_binding=old_binding, old_session_hash=old_session,
                ):
                    break
            else:
                raise web.HTTPServiceUnavailable(text="Standalone capacity reached")
        else:
            if old_binding is not None:
                for code, row in list(self.pending.items()):
                    if row.binding == old_binding:
                        del self.pending[code]
            if len(self.pending) >= MAX_PENDING:
                raise web.HTTPServiceUnavailable(text="Standalone capacity reached")
            for _ in range(5):
                challenge = secrets.token_urlsafe(12)
                if challenge not in self.pending:
                    break
            else:
                raise web.HTTPServiceUnavailable(text="Standalone capacity reached")
            binding_token = secrets.token_urlsafe(32)
            self.pending[challenge] = _Pending(
                binding=self._hash(binding_token),
                issued_at=current, expires_at=current + self.pending_ttl,
            )
        response = web.json_response({"challenge": challenge, "expiresIn": self.pending_ttl})
        self._set_cookie(response, PENDING_COOKIE, binding_token, self.pending_ttl)
        # Starting a new login never silently reuses an authenticated cookie.
        if isinstance(existing, str) and existing:
            if self.ledger is None:
                self.sessions.pop(self._hash(existing), None)
            self._clear_cookie(response, SESSION_COOKIE)
        return response

    async def approve_from_private_telegram(
        self, challenge: str, *, actor_id: int, chat_id: int, explicitly_confirmed: bool,
    ) -> bool:
        """Private in-process entrypoint, NEVER exposed via HTTP or callback payload.

        Bot integration must supply actor_id/chat_id from verified private Update
        and call only after the owner explicitly confirms *the displayed code*.
        """
        if (not isinstance(challenge, str) or not CHALLENGE_PATTERN.fullmatch(challenge)
                or type(actor_id) is not int or not 0 < actor_id < 2**52
                or type(chat_id) is not int or chat_id != actor_id
                or explicitly_confirmed is not True):
            return False
        current = self._clock()
        if not self.challenge_pending(challenge, current):
            return False
        if not await self._verified_owner(actor_id):
            return False
        # Critical re-check after awaits: an expired/replaced challenge cannot revive.
        current = self._clock()
        if not self.challenge_pending(challenge, current):
            return False
        if self.ledger is not None:
            return self.ledger.approve(self._hash(challenge), actor_id, current=current)
        self.pending[challenge].approved_owner = actor_id
        return True

    async def _complete(self, request: web.Request) -> web.Response:
        self._guard(request, mutate=True)
        data = await self._json(request, keys=frozenset({"challenge"}))
        code = data["challenge"]
        if not isinstance(code, str) or not CHALLENGE_PATTERN.fullmatch(code):
            raise web.HTTPUnauthorized(text="Standalone challenge invalid")
        current = self._clock()
        self._throttle(request, current)
        self._prune(current)
        binding = self._binding(request)
        if self.ledger is not None:
            record = self.ledger.pending(self._hash(code), current=current)
            row = (_Pending(binding=record[0], issued_at=current,
                            expires_at=current + self.pending_ttl,
                            approved_owner=record[1]) if record else None)
        else:
            row = self.pending.get(code)
        if binding is None or row is None or row.binding != binding:
            raise web.HTTPUnauthorized(text="Standalone challenge invalid")
        if row.approved_owner is None:
            return web.json_response({"state": "pending"}, status=202)
        owner = row.approved_owner
        if not await self._verified_owner(owner):
            if self.ledger is not None:
                self.ledger.cancel(self._hash(code), binding, current=current)
            else:
                self.pending.pop(code, None)
            raise web.HTTPForbidden(text="Standalone unavailable")
        current = self._clock()
        self._prune(current)
        token = secrets.token_urlsafe(32)
        if self.ledger is not None:
            if not self.ledger.exchange(
                self._hash(code), binding, owner, self._hash(token),
                current=current, session_ttl=self.session_ttl,
            ):
                raise web.HTTPUnauthorized(text="Standalone challenge invalid")
        else:
            row = self.pending.get(code)
            if row is None or row.binding != binding or row.approved_owner != owner:
                raise web.HTTPUnauthorized(text="Standalone challenge invalid")
            if len(self.sessions) >= MAX_SESSIONS:
                raise web.HTTPServiceUnavailable(text="Standalone capacity reached")
            del self.pending[code]
            self.sessions[self._hash(token)] = (owner, current + self.session_ttl)
        response = web.json_response({"state": "authenticated", "mode": "standalone"})
        self._set_cookie(response, SESSION_COOKIE, token, self.session_ttl)
        self._clear_cookie(response, PENDING_COOKIE)
        return response

    async def _me(self, request: web.Request) -> web.Response:
        self._guard(request, mutate=False)
        current = self._clock()
        self._prune(current)
        owner = self._session(request, current)
        if owner is None:
            raise web.HTTPUnauthorized(text="Standalone authentication required")
        if not await self._verified_owner(owner):
            token = request.cookies.get(SESSION_COOKIE, "")
            if self.ledger is not None:
                self.ledger.revoke_session(self._hash(token), current=current)
            else:
                self.sessions.pop(self._hash(token), None)
            raise web.HTTPForbidden(text="Standalone unavailable")
        try:
            profile = await self.service.profile(owner)
        except Exception:
            raise web.HTTPServiceUnavailable(text="Customer data unavailable") from None
        if not profile.exists:
            raise web.HTTPForbidden(text="Standalone unavailable")
        return web.json_response({"subscription": public_customer_summary(profile)})

    async def _cancel(self, request: web.Request) -> web.Response:
        self._guard(request, mutate=True)
        data = await self._json(request, keys=frozenset({"challenge"}))
        code = data["challenge"]
        current = self._clock()
        self._prune(current)
        binding = self._binding(request)
        if not isinstance(code, str) or not CHALLENGE_PATTERN.fullmatch(code) or binding is None:
            raise web.HTTPUnauthorized(text="Standalone challenge invalid")
        if self.ledger is not None:
            if not self.ledger.cancel(self._hash(code), binding, current=current):
                raise web.HTTPUnauthorized(text="Standalone challenge invalid")
        else:
            row = self.pending.get(code)
            if row is None or row.binding != binding:
                raise web.HTTPUnauthorized(text="Standalone challenge invalid")
            del self.pending[code]
        response = web.json_response({"state": "cancelled"})
        self._clear_cookie(response, PENDING_COOKIE)
        return response

    async def _logout(self, request: web.Request) -> web.Response:
        self._guard(request, mutate=True)
        await self._json(request, keys=frozenset())
        current = self._clock()
        self._prune(current)
        token = request.cookies.get(SESSION_COOKIE, "")
        binding = self._binding(request)
        if self.ledger is not None:
            self.ledger.logout(
                session_hash=self._hash(token) if token else None,
                binding_hash=binding, current=current,
            )
        else:
            if isinstance(token, str) and token:
                self.sessions.pop(self._hash(token), None)
            if binding:
                for code, row in list(self.pending.items()):
                    if row.binding == binding:
                        del self.pending[code]
        response = web.json_response({"authenticated": False})
        self._clear_cookie(response, SESSION_COOKIE)
        self._clear_cookie(response, PENDING_COOKIE)
        return response


def create_standalone_pilot(**kwargs) -> StandalonePilot:
    """Build disabled-by-default app plus a trusted private-bot approval hook.

    No production listener, bot handler or reverse-proxy route is configured.
    """
    return StandalonePilot(**kwargs)
