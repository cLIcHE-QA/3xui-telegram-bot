from __future__ import annotations

import base64
import binascii
import logging
from urllib.parse import quote, urlsplit

import aiohttp
from aiohttp import web


LOG = logging.getLogger(__name__)

# Headers useful to subscription clients. Hop-by-hop/content headers are rebuilt.
PASSTHROUGH_HEADERS = {
    "subscription-userinfo",
    "profile-update-interval",
    "profile-title",
    "profile-web-page-url",
    "support-url",
    "announce",
}


def _pad_b64(value: str) -> str:
    return value + "=" * (-len(value) % 4)


def _try_decode_subscription(body: bytes) -> tuple[str, bool]:
    """Return (plain_text, was_base64_wrapped)."""
    try:
        text = body.decode("utf-8").strip()
    except UnicodeDecodeError:
        text = ""

    if "://" in text or text.startswith("[Interface]"):
        return text, False

    compact = "".join(text.split())
    if not compact:
        return "", False

    decoders = (
        lambda s: base64.b64decode(_pad_b64(s), validate=True),
        lambda s: base64.urlsafe_b64decode(_pad_b64(s)),
    )
    for decoder in decoders:
        try:
            decoded = decoder(compact).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError, ValueError):
            continue
        if "://" in decoded or decoded.startswith("[Interface]"):
            return decoded.strip(), True

    return text, False


def _decode_awg_payload(payload: str) -> str | None:
    try:
        raw = base64.urlsafe_b64decode(_pad_b64(payload))
        return raw.decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return None


def _awg_remark_from_conf(conf: str) -> str | None:
    """Extract 3x-ui's display comment placed before [Peer]."""
    lines = conf.splitlines()
    peer_index = next((i for i, line in enumerate(lines) if line.strip() == "[Peer]"), None)
    if peer_index is None:
        return None

    for line in reversed(lines[:peer_index]):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("# Name="):
            value = stripped[len("# Name="):].strip()
            return value or None
        if stripped.startswith("# "):
            value = stripped[2:].strip()
            return value or None
        break
    return None


def convert_vpn_to_amneziawg(text: str) -> str:
    """Convert only 3x-ui AmneziaWG vpn:// links to INCY's scheme."""
    out: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("vpn://"):
            out.append(raw_line)
            continue

        rest = line[len("vpn://"):]
        payload, sep, fragment = rest.partition("#")
        if not payload:
            out.append(raw_line)
            continue

        if sep:
            suffix = "#" + fragment
        else:
            conf = _decode_awg_payload(payload)
            remark = _awg_remark_from_conf(conf) if conf else None
            suffix = "#" + quote(remark, safe="") if remark else ""

        out.append(f"amneziawg://{payload}{suffix}")
    return "\n".join(out)


def _encode_like_upstream(text: str, was_base64: bool) -> bytes:
    raw = text.encode("utf-8")
    if was_base64:
        return base64.b64encode(raw)
    return raw


def _wants_html(request: web.Request) -> bool:
    accept = request.headers.get("Accept", "").lower()
    html_flag = request.query.get("html", "").lower() in {"1", "true", "yes"}
    view_flag = request.query.get("view", "").lower() == "html"
    return "text/html" in accept or html_flag or view_flag


def _rewrite_default_page(html: str, upstream_url: str, public_url: str) -> str:
    """Keep 3x-ui's default page, changing only compatibility-facing URLs.

    - AWG direct links become amneziawg:// for INCY mobile.
    - The raw subscription URL shown by 3x-ui becomes the public compat URL.
    - Vite /assets/* requests are moved under /compat/assets/* so the existing
      nginx `location ^~ /compat/` continues to route them to this proxy.
    """
    html = html.replace("vpn://", "amneziawg://")
    if upstream_url and public_url:
        html = html.replace(upstream_url, public_url)
        html = html.replace(upstream_url.replace("/", "\\/"), public_url.replace("/", "\\/"))

    # Vite production bundles use root-absolute /assets/... URLs.
    html = html.replace('src="/assets/', 'src="/compat/assets/')
    html = html.replace("src='/assets/", "src='/compat/assets/")
    html = html.replace('href="/assets/', 'href="/compat/assets/')
    html = html.replace("href='/assets/", "href='/compat/assets/")
    return html


class SubscriptionProxy:
    def __init__(
        self,
        db,
        upstream_template: str,
        public_template: str = "",
        verify_tls: bool = True,
        host: str = "0.0.0.0",
        port: int = 8080,
    ):
        self.db = db
        self.upstream_template = upstream_template
        self.public_template = public_template
        self.verify_tls = verify_tls
        self.host = host
        self.port = port
        self.runner: web.AppRunner | None = None

        sample = upstream_template.format(sub_id="__subid__")
        parts = urlsplit(sample)
        self.upstream_origin = f"{parts.scheme}://{parts.netloc}"

    async def health(self, request: web.Request) -> web.Response:
        return web.Response(text="ok\n", content_type="text/plain")

    async def _fetch(self, url: str, *, headers: dict[str, str], params=None) -> tuple[int, bytes, dict[str, str]]:
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(
                url,
                headers=headers,
                params=params,
                ssl=None if self.verify_tls else False,
                allow_redirects=True,
            ) as resp:
                return resp.status, await resp.read(), dict(resp.headers)

    def _response_headers(self, upstream_headers: dict[str, str]) -> dict[str, str]:
        result = {
            key: value
            for key, value in upstream_headers.items()
            if key.lower() in PASSTHROUGH_HEADERS
        }
        result["Cache-Control"] = "no-store"
        result["X-Subscription-Compat"] = "3x-ui-awg-to-incy"
        return result

    async def subscription(self, request: web.Request) -> web.Response:
        sub_id = request.match_info["sub_id"].strip()
        if not sub_id or len(sub_id) > 128:
            raise web.HTTPNotFound()

        # Only expose subscriptions managed by this bot.
        rec = await self.db.get_by_sub_id(sub_id)
        if rec is None:
            raise web.HTTPNotFound()

        upstream_url = self.upstream_template.format(sub_id=sub_id)
        public_url = (
            self.public_template.format(sub_id=sub_id)
            if self.public_template
            else upstream_url
        )

        # Keep query flags used by 3x-ui's built-in page, especially ?format=info.
        params = list(request.query.items())

        if request.query.get("format", "").lower() == "info":
            accept = request.headers.get("Accept", "application/json")
            try:
                status, body, upstream_headers = await self._fetch(
                    upstream_url,
                    headers={
                        "Accept": accept,
                        "User-Agent": request.headers.get("User-Agent", "3xui-telegram-bot-subproxy/1.1"),
                    },
                    params=params,
                )
            except (aiohttp.ClientError, TimeoutError) as exc:
                LOG.warning("subscription info upstream request failed: %s", exc)
                raise web.HTTPBadGateway(text="subscription upstream unavailable\n")
            if status >= 400:
                raise web.HTTPBadGateway(text="subscription upstream error\n")
            headers = self._response_headers(upstream_headers)
            headers["Content-Type"] = upstream_headers.get("Content-Type", "application/json; charset=utf-8")
            return web.Response(body=body, headers=headers)

        if _wants_html(request):
            try:
                status, body, upstream_headers = await self._fetch(
                    upstream_url,
                    headers={
                        "Accept": "text/html",
                        "User-Agent": request.headers.get("User-Agent", "Mozilla/5.0"),
                    },
                    params=params,
                )
            except (aiohttp.ClientError, TimeoutError) as exc:
                LOG.warning("subscription HTML upstream request failed: %s", exc)
                raise web.HTTPBadGateway(text="subscription upstream unavailable\n")
            if status >= 400:
                raise web.HTTPBadGateway(text="subscription upstream error\n")

            try:
                html = body.decode("utf-8")
            except UnicodeDecodeError:
                raise web.HTTPBadGateway(text="invalid subscription HTML\n")

            html = _rewrite_default_page(html, upstream_url, public_url)
            headers = self._response_headers(upstream_headers)
            headers["Content-Type"] = "text/html; charset=utf-8"
            return web.Response(body=html.encode("utf-8"), headers=headers)

        # Normal VPN client request: fetch raw subscription and adapt AWG only.
        try:
            status, upstream_body, upstream_headers = await self._fetch(
                upstream_url,
                headers={
                    "Accept": "text/plain",
                    "User-Agent": request.headers.get("User-Agent", "3xui-telegram-bot-subproxy/1.1"),
                },
                params=params,
            )
        except (aiohttp.ClientError, TimeoutError) as exc:
            LOG.warning("subscription upstream request failed: %s", exc)
            raise web.HTTPBadGateway(text="subscription upstream unavailable\n")
        if status >= 400:
            LOG.warning("subscription upstream returned HTTP %s", status)
            raise web.HTTPBadGateway(text="subscription upstream error\n")

        plain, was_base64 = _try_decode_subscription(upstream_body)
        converted = convert_vpn_to_amneziawg(plain)
        body = _encode_like_upstream(converted, was_base64)

        headers = self._response_headers(upstream_headers)
        headers["Content-Type"] = "text/plain; charset=utf-8"
        return web.Response(body=body, headers=headers)

    async def asset(self, request: web.Request) -> web.Response:
        tail = request.match_info.get("tail", "").lstrip("/")
        if not tail or any(part == ".." for part in tail.split("/")):
            raise web.HTTPNotFound()

        # /compat/assets/foo.js -> upstream /assets/foo.js
        upstream_url = f"{self.upstream_origin}/assets/{tail}"
        try:
            status, body, upstream_headers = await self._fetch(
                upstream_url,
                headers={
                    "Accept": request.headers.get("Accept", "*/*"),
                    "User-Agent": request.headers.get("User-Agent", "Mozilla/5.0"),
                },
            )
        except (aiohttp.ClientError, TimeoutError) as exc:
            LOG.warning("subscription asset upstream request failed: %s", exc)
            raise web.HTTPBadGateway(text="subscription asset unavailable\n")

        if status == 404:
            raise web.HTTPNotFound()
        if status >= 400:
            raise web.HTTPBadGateway(text="subscription asset upstream error\n")

        headers: dict[str, str] = {}
        if "Content-Type" in upstream_headers:
            headers["Content-Type"] = upstream_headers["Content-Type"]
        if "ETag" in upstream_headers:
            headers["ETag"] = upstream_headers["ETag"]
        headers["Cache-Control"] = upstream_headers.get("Cache-Control", "public, max-age=3600")
        return web.Response(body=body, headers=headers)

    async def start(self) -> None:
        app = web.Application()
        app.router.add_get("/healthz", self.health)
        # Register assets before /compat/{sub_id}.
        app.router.add_get("/compat/assets/{tail:.*}", self.asset)
        app.router.add_get("/compat/{sub_id}", self.subscription)
        self.runner = web.AppRunner(app, access_log=LOG)
        await self.runner.setup()
        site = web.TCPSite(self.runner, self.host, self.port)
        await site.start()
        LOG.info("subscription compatibility proxy listening on %s:%s", self.host, self.port)

    async def stop(self) -> None:
        if self.runner is not None:
            await self.runner.cleanup()
            self.runner = None
