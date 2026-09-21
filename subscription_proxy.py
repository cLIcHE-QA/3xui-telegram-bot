from __future__ import annotations

import base64
import binascii
import logging
from urllib.parse import quote

import aiohttp
from aiohttp import web


LOG = logging.getLogger(__name__)

# Headers useful to subscription clients. Hop-by-hop/content headers are rebuilt.
PASSTHROUGH_HEADERS = {
    "subscription-userinfo",
    "profile-update-interval",
    "profile-web-page-url",
    "support-url",
}


def _pad_b64(value: str) -> str:
    return value + "=" * (-len(value) % 4)


def _try_decode_subscription(body: bytes) -> tuple[str, bool]:
    """Return (plain_text, was_base64_wrapped).

    3x-ui normally base64-wraps the whole raw subscription when subEncrypt=true.
    With subEncrypt=false it returns one URI per line as plain text.
    """
    try:
        text = body.decode("utf-8").strip()
    except UnicodeDecodeError:
        text = ""

    # If it already looks like a raw subscription, keep it plain.
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

    # Unknown response: return it untouched rather than corrupting it.
    return text, False


def _decode_awg_payload(payload: str) -> str | None:
    try:
        raw = base64.urlsafe_b64decode(_pad_b64(payload))
        return raw.decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return None


def _awg_remark_from_conf(conf: str) -> str | None:
    """Extract 3x-ui's '# <remark>' comment placed before [Peer]."""
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
        # Only consider the comment immediately preceding the [Peer] block.
        break
    return None


def convert_vpn_to_amneziawg(text: str) -> str:
    """Convert only 3x-ui AmneziaWG vpn:// links to INCY's canonical scheme."""
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

        # Keep 3x-ui's RawURLEncoding payload exactly as generated. INCY accepts
        # URL-safe base64 with optional padding. Add a display-name fragment when
        # possible so the AWG entry keeps the inbound remark.
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


class SubscriptionProxy:
    def __init__(
        self,
        db,
        upstream_template: str,
        verify_tls: bool = True,
        host: str = "0.0.0.0",
        port: int = 8080,
    ):
        self.db = db
        self.upstream_template = upstream_template
        self.verify_tls = verify_tls
        self.host = host
        self.port = port
        self.runner: web.AppRunner | None = None

    async def health(self, request: web.Request) -> web.Response:
        return web.Response(text="ok\n", content_type="text/plain")

    async def subscription(self, request: web.Request) -> web.Response:
        sub_id = request.match_info["sub_id"].strip()
        if not sub_id or len(sub_id) > 128:
            raise web.HTTPNotFound()

        # Do not turn the proxy into a public oracle for arbitrary 3x-ui sub IDs.
        rec = await self.db.get_by_sub_id(sub_id)
        if rec is None:
            raise web.HTTPNotFound()

        upstream_url = self.upstream_template.format(sub_id=sub_id)
        timeout = aiohttp.ClientTimeout(total=20)
        headers = {
            "Accept": "text/plain",
            "User-Agent": request.headers.get("User-Agent", "3xui-telegram-bot-subproxy/1.0"),
        }

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    upstream_url,
                    headers=headers,
                    ssl=None if self.verify_tls else False,
                    allow_redirects=True,
                ) as resp:
                    upstream_body = await resp.read()
                    if resp.status >= 400:
                        LOG.warning("subscription upstream returned HTTP %s", resp.status)
                        raise web.HTTPBadGateway(text="subscription upstream error\n")
                    upstream_headers = dict(resp.headers)
        except web.HTTPException:
            raise
        except (aiohttp.ClientError, TimeoutError) as exc:
            LOG.warning("subscription upstream request failed: %s", exc)
            raise web.HTTPBadGateway(text="subscription upstream unavailable\n")

        plain, was_base64 = _try_decode_subscription(upstream_body)
        converted = convert_vpn_to_amneziawg(plain)
        body = _encode_like_upstream(converted, was_base64)

        response_headers = {
            key: value
            for key, value in upstream_headers.items()
            if key.lower() in PASSTHROUGH_HEADERS
        }
        response_headers["Cache-Control"] = "no-store"
        response_headers["X-Subscription-Compat"] = "3x-ui-awg-to-incy"

        return web.Response(
            body=body,
            headers=response_headers,
            content_type="text/plain",
            charset="utf-8",
        )

    async def start(self) -> None:
        app = web.Application()
        app.router.add_get("/healthz", self.health)
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
