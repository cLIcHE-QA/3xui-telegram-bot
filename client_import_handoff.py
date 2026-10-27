"""Короткоживущий HTTPS handoff для клиентских import URI.

В Telegram попадает только случайный ticket; subscription bearer URI живёт
лишь в памяти бота и выдаётся HTML без внешних запросов. Один ticket — один GET.
"""
from __future__ import annotations

import html
import base64
import hashlib
import re
import secrets
import time
from urllib.parse import urlsplit, urlunsplit

from client_deep_links import IMPORT_CLIENTS, import_uri

AUTO_OPEN_SCRIPT = 'window.addEventListener("load",()=>{document.getElementById("open-client").click()});'
SCRIPT_HASH = base64.b64encode(hashlib.sha256(AUTO_OPEN_SCRIPT.encode("utf-8")).digest()).decode("ascii")

TTL_SECONDS = 90
MAX_TICKETS = 256
_TOKEN = re.compile(r"[A-Za-z0-9_-]{43}\Z")
_TICKETS: dict[str, tuple[float, str, str]] = {}


def issue_handoff(
    url: str, *, client: str, platform: str, uri: str,
    public_template: str, title: object = None,
) -> str | None:
    """Return same-origin HTTPS URL only when it matches configured compat host."""
    if (not isinstance(client, str) or not isinstance(platform, str)
            or not isinstance(uri, str) or not isinstance(public_template, str)
            or public_template.count("{sub_id}") != 1):
        return None
    # The prefix alone cannot bind an import payload to the owner's URL.
    expected = import_uri(client, platform, url, title=title)
    if expected is None or uri != expected:
        return None
    try:
        target = urlsplit(url)
        configured = urlsplit(public_template.format(sub_id="__probe__"))
    except (ValueError, KeyError, IndexError, AttributeError):
        return None
    if (
        target.scheme != "https" or configured.scheme != "https"
        or target.netloc != configured.netloc
        or target.username or target.password or target.query or target.fragment
        or configured.query or configured.fragment
        or not configured.path.endswith("/__probe__")
        or not target.path.startswith(configured.path[:-len("__probe__")])
        or url != urlunsplit(target)
        or len(uri) > 256
        or any(ord(ch) < 33 or ord(ch) > 126 for ch in uri)
    ):
        return None
    # Require exactly /compat/{sub_id}, never allow an arbitrary path to opt in.
    prefix = configured.path[:-len("__probe__")]
    if prefix != "/compat/" or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", target.path[len(prefix):]):
        return None
    now = time.monotonic()
    for token, (expires, _, _) in tuple(_TICKETS.items()):
        if expires <= now:
            _TICKETS.pop(token, None)
    if len(_TICKETS) >= MAX_TICKETS:
        return None
    token = secrets.token_urlsafe(32)
    _TICKETS[token] = (now + TTL_SECONDS, client, uri)
    return urlunsplit(("https", target.netloc, f"/compat/open/{token}", "", ""))


def consume_handoff(token: str) -> tuple[str, str] | None:
    if not isinstance(token, str) or not _TOKEN.fullmatch(token):
        return None
    item = _TICKETS.pop(token, None)
    if not item or item[0] <= time.monotonic():
        return None
    return item[1], item[2]


def handoff_html(client: str, uri: str) -> str:
    """Browser navigation starts only from this user-clickable page."""
    name = html.escape(IMPORT_CLIENTS[client].name, quote=True)
    escaped_uri = html.escape(uri, quote=True)
    return (
        '<!doctype html><html lang="ru"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="referrer" content="no-referrer"><title>Открыть VPN-клиент</title>'
        '<style>body{font:16px system-ui,sans-serif;max-width:34rem;'
        'padding:2rem;margin:10vh auto;line-height:1.6}'
        'a{display:inline-block;padding:1rem;border-radius:.6rem;'
        'background:#1769aa;color:white;text-decoration:none}</style></head>'
        '<body><h1>Импорт подписки</h1>'
        '<p>Нажмите кнопку, чтобы открыть установленный VPN-клиент. '
        'Браузер может запросить подтверждение.</p>'
        f'<p><a id="open-client" rel="noreferrer" href="{escaped_uri}">Открыть в {name}</a></p>'
        f'<script>{AUTO_OPEN_SCRIPT}</script>'
        '<p>Если приложение не открывается, вернитесь в Telegram '
        'и используйте копирование ссылки или QR.</p></body></html>'
    )
