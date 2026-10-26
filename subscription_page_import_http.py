"""#887 D3e: isolated default-off HTTP preflight; never returns subscription URLs."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time
import io
from typing import Callable
from urllib.parse import urlsplit

from aiohttp import web
from subscription_page_customer import COOKIE as MINI_COOKIE, MiniAppSessions, PATH
from subscription_page_standalone import SESSION_COOKIE as STANDALONE_COOKIE, StandalonePilot
from subscription_page_import_preflight import check_import_eligibility
from subscription_page_import_sqlite import ImportSQLiteLedger
from subscription_page_import_issuer import (ReviewedImportClient,
    owner_bound_subscription_url, reviewed_import_methods)

BASE = PATH + "/import/preflight"


def create_import_preflight_app(
    *, https_origin: str, ledger: ImportSQLiteLedger,
    mini_sessions: MiniAppSessions, standalone: StandalonePilot,
    customer_service: object, feature_flags: object, pilot_ids: frozenset[int],
    enabled: bool = False, now: Callable[[], float] = time.time,
    csrf_secret: bytes,
    delivery_enabled: bool = False,
    subscription_origin: str | None = None,
    reviewed_clients: tuple[ReviewedImportClient, ...] = (),
) -> web.Application:
    """Offline factory. Real TLS, edge throttling and multi-host remain unverified."""
    url = urlsplit(https_origin)
    if (url.scheme != "https" or not url.netloc or not url.hostname
            or url.username or url.password or url.path or url.query or url.fragment
            or url.hostname.endswith(".") or https_origin != "https://" + url.netloc):
        raise ValueError("Exact HTTPS origin required")
    if (not isinstance(ledger, ImportSQLiteLedger)
            or ledger.https_origin != https_origin
            or not isinstance(mini_sessions, MiniAppSessions)
            or not isinstance(standalone, StandalonePilot)
            or standalone.https_origin != https_origin or type(enabled) is not bool
            or not isinstance(pilot_ids, frozenset) or not pilot_ids
            or any(type(x) is not int or not 0 < x < 2**52 for x in pilot_ids)
            or not callable(now) or not callable(getattr(customer_service, "profile", None))
            or not callable(getattr(feature_flags, "snapshot", None))
            or not isinstance(csrf_secret, bytes) or len(csrf_secret) < 32):
        raise ValueError("Trusted isolated preflight configuration required")

    if type(delivery_enabled) is not bool:
        raise ValueError("Explicit URL delivery feature gate required")
    approved_clients = reviewed_import_methods(reviewed_clients)
    if delivery_enabled and (not enabled or not approved_clients or
                             not isinstance(subscription_origin, str) or
                             not subscription_origin.startswith("https://")):
        raise ValueError("URL delivery requires separate reviewed gates")

    app = web.Application(client_max_size=1024)

    def clock() -> float:
        value = now()
        if type(value) not in (int, float) or not 0 < value < 10**12:
            raise web.HTTPServiceUnavailable(text="Preflight unavailable")
        return float(value)

    def session(request: web.Request, now_at: float) -> tuple[str, str, int]:
        mini = MINI_COOKIE in request.cookies
        standalone_cookie = STANDALONE_COOKIE in request.cookies
        if mini == standalone_cookie:
            raise web.HTTPUnauthorized(text="Authentication required")
        try:
            if mini:
                cookie = request.cookies[MINI_COOKIE]
                owner = mini_sessions.user(cookie, now_at)
                mode = "telegram-mini-app"
            else:
                cookie = request.cookies[STANDALONE_COOKIE]
                owner = standalone.session_owner_from_cookie(cookie, now_at)
                mode = "standalone"
        except Exception:
            owner = None
        if type(owner) is not int or not 0 < owner < 2**52:
            raise web.HTTPUnauthorized(text="Authentication required")
        return mode, cookie, owner

    def session_key(mode: str, cookie: str) -> bytes:
        return hashlib.sha256((mode + ":" + cookie).encode("utf-8")).digest()

    def owner_key(owner: int) -> bytes:
        return hmac.new(csrf_secret, str(owner).encode("ascii"), hashlib.sha256).digest()

    def csrf(mode: str, cookie: str) -> str:
        material = b"d3e-csrf:" + mode.encode("ascii") + b":" + cookie.encode("ascii")
        return hmac.new(csrf_secret, material, hashlib.sha256).hexdigest()

    def guard(request: web.Request, *, mutate: bool) -> None:
        if request.host != url.netloc or request.query_string:
            raise web.HTTPForbidden(text="Preflight denied")
        if request.headers.get("Origin") != https_origin:
            raise web.HTTPForbidden(text="Preflight denied")
        site = request.headers.get("Sec-Fetch-Site")
        if site is not None and site not in ("same-origin", "none"):
            raise web.HTTPForbidden(text="Preflight denied")
        if mutate and request.content_type != "application/json":
            raise web.HTTPUnsupportedMediaType(text="JSON required")

    @web.middleware
    async def secure(request: web.Request, handler):
        error = False
        try:
            result = await handler(request)
        except web.HTTPException as exc:
            result = exc
            error = True
        for k, v in {
            "Cache-Control": "no-store", "Pragma": "no-cache",
            "Referrer-Policy": "no-referrer", "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
            "Cross-Origin-Resource-Policy": "same-origin",
        }.items():
            result.headers[k] = v
        if error:
            raise result
        return result

    app.middlewares.append(secure)

    async def eligible(owner: int) -> bool:
        verdict = await check_import_eligibility(
            authenticated_owner=owner, customer_service=customer_service,
            feature_flags=feature_flags, pilot_ids=pilot_ids,
            explicitly_enabled=enabled,
        )
        return verdict.permitted is True

    def guard_csrf(request: web.Request, mode: str, cookie: str) -> None:
        given = request.headers.get("X-CSRF-Token", "")
        target = csrf(mode, cookie)
        if len(given) != len(target) or not hmac.compare_digest(given, target):
            raise web.HTTPForbidden(text="Preflight denied")

    async def body(request: web.Request, fields: frozenset[str]) -> dict:
        try:
            parsed = await request.json()
        except (ValueError, UnicodeError):
            raise web.HTTPBadRequest(text="Invalid request") from None
        if not isinstance(parsed, dict) or set(parsed) != fields:
            raise web.HTTPBadRequest(text="Invalid request")
        return parsed

    async def csrf_route(request: web.Request) -> web.Response:
        guard(request, mutate=False)
        if not enabled:
            raise web.HTTPNotFound(text="Preflight unavailable")
        mode, cookie, owner = session(request, clock())
        if not await eligible(owner):
            raise web.HTTPForbidden(text="Preflight unavailable")
        return web.json_response({"csrfToken": csrf(mode, cookie)})

    async def issue(request: web.Request) -> web.Response:
        guard(request, mutate=True)
        if not enabled:
            raise web.HTTPNotFound(text="Preflight unavailable")
        mode, cookie, owner = session(request, clock())
        guard_csrf(request, mode, cookie)
        await body(request, frozenset())
        current = clock()
        key = session_key(mode, cookie)
        try:
            if not ledger.reserve(key, "issue", current=current):
                raise web.HTTPTooManyRequests(text="Preflight limited")
            if not await eligible(owner):
                raise web.HTTPForbidden(text="Preflight unavailable")
            fresh = clock()
            if session(request, fresh) != (mode, cookie, owner):
                raise web.HTTPUnauthorized(text="Authentication required")
            proof = secrets.token_urlsafe(32)
            if not ledger.issue(hashlib.sha256(proof.encode("ascii")).digest(),
                                owner_key(owner), key, mode, issued=fresh, expires=fresh + 45):
                raise web.HTTPServiceUnavailable(text="Preflight unavailable")
        except ValueError:
            raise web.HTTPServiceUnavailable(text="Preflight unavailable") from None
        return web.json_response({"proof": proof, "expiresIn": 45})

    async def consume(request: web.Request) -> web.Response:
        guard(request, mutate=True)
        if not enabled:
            raise web.HTTPNotFound(text="Preflight unavailable")
        mode, cookie, owner = session(request, clock())
        guard_csrf(request, mode, cookie)
        parsed = await body(request, frozenset({"proof"}))
        proof = parsed["proof"]
        if (not isinstance(proof, str) or len(proof) != 43
                or not all(c.isascii() and (c.isalnum() or c in "-_") for c in proof)):
            raise web.HTTPBadRequest(text="Invalid request")
        current = clock()
        key = session_key(mode, cookie)
        try:
            if not ledger.reserve(key, "consume", current=current):
                raise web.HTTPTooManyRequests(text="Preflight limited")
            if not ledger.consume(hashlib.sha256(proof.encode("ascii")).digest(),
                                  owner_key(owner), key, mode, current=current):
                raise web.HTTPForbidden(text="Preflight unavailable")
            if not await eligible(owner):
                raise web.HTTPForbidden(text="Preflight unavailable")
            fresh = clock()
            if session(request, fresh) != (mode, cookie, owner):
                raise web.HTTPUnauthorized(text="Authentication required")
        except ValueError:
            raise web.HTTPServiceUnavailable(text="Preflight unavailable") from None
        return web.json_response({"preflight": True})

    async def deliver(request: web.Request) -> web.Response:
        """Explicitly gated bearer disclosure; consumes proof before awaiting provider.

        The browser can choose only a reviewed client tuple, never an owner,
        subscription ID or provider URL. No URL is ever stored in SQLite.
        """
        guard(request, mutate=True)
        if not enabled or not delivery_enabled:
            raise web.HTTPNotFound(text="Import unavailable")
        mode, cookie, owner = session(request, clock())
        guard_csrf(request, mode, cookie)
        parsed = await body(request, frozenset({"proof", "platform", "clientId", "clientVersion", "method"}))
        proof = parsed["proof"]
        client = (parsed["platform"], parsed["clientId"], parsed["clientVersion"])
        method = parsed["method"]
        if (not isinstance(proof, str) or len(proof) != 43
                or not all(c.isascii() and (c.isalnum() or c in "-_") for c in proof)
                or any(not isinstance(value, str) for value in client)
                or method not in ("copy", "qr")):
            raise web.HTTPBadRequest(text="Invalid request")
        current = clock()
        key = session_key(mode, cookie)
        try:
            if not ledger.reserve(key, "consume", current=current):
                raise web.HTTPTooManyRequests(text="Import limited")
            # Burn valid one-time proof before any async authorization/URL reads.
            if not ledger.consume(hashlib.sha256(proof.encode("ascii")).digest(),
                                  owner_key(owner), key, mode, current=current):
                raise web.HTTPForbidden(text="Import unavailable")
            permissions = approved_clients.get(client)
            if (permissions is None or
                    not (permissions[0] if method == "copy" else permissions[1])
                    or not await eligible(owner)):
                raise web.HTTPForbidden(text="Import unavailable")
            fresh = clock()
            if session(request, fresh) != (mode, cookie, owner):
                raise web.HTTPUnauthorized(text="Authentication required")
            # This service re-reads entitlement/provider state via subscription_card
            # (not weak profile(read_access=False)). Do NOT log the resulting URL.
            url_value = await owner_bound_subscription_url(
                customer_service=customer_service,
                authenticated_owner=owner,
                expected_origin=subscription_origin,
            )
            final = clock()
            if (url_value is None or
                    session(request, final) != (mode, cookie, owner) or
                    not await eligible(owner)):
                raise web.HTTPForbidden(text="Import unavailable")
            final_check = clock()
            if session(request, final_check) != (mode, cookie, owner):
                raise web.HTTPUnauthorized(text="Authentication required")
        except ValueError:
            raise web.HTTPServiceUnavailable(text="Import unavailable") from None
        # A bearer credential only for a reviewed client and single authorized
        # request. Real HTTPS ingress/log-redaction/device smoke still PENDING.
        if method == "qr":
            # The QR contains the same bearer URL and MUST remain owner-gated.
            # Encode only in memory; never write the payload to logs or disk.
            try:
                import qrcode
                qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M,
                                   box_size=5, border=4)
                qr.add_data(url_value)
                qr.make(fit=True)
                output = io.BytesIO()
                qr.make_image(fill_color="black", back_color="white").save(output, format="PNG")
                return web.Response(body=output.getvalue(), content_type="image/png")
            except Exception:
                raise web.HTTPServiceUnavailable(text="Import unavailable") from None
        return web.json_response({"subscriptionUrl": url_value})

    app.router.add_get(BASE + "/csrf", csrf_route)
    app.router.add_post(BASE + "/issue", issue)
    app.router.add_post(BASE + "/consume", consume)
    app.router.add_post(BASE + "/deliver", deliver)
    return app
