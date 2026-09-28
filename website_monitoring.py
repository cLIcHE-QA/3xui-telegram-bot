from __future__ import annotations

import asyncio
from dataclasses import dataclass
import ipaddress
import re
import socket
import ssl
import time
from typing import Mapping
from urllib.parse import urljoin, urlsplit, urlunsplit

import aiohttp
from aiohttp.abc import AbstractResolver
import aiosqlite


MAX_REDIRECTS = 5
MAX_RESPONSE_BYTES = 1024 * 1024
MAX_SITEMAP_BYTES = 2 * 1024 * 1024
MAX_SITEMAP_DOCUMENTS = 10
MAX_SITEMAP_URLS = 5000
MAX_MONITORS_PER_ADMIN = 10
NORMAL_CHECK_INTERVAL = 10 * 60
DOWN_CHECK_INTERVAL = 3 * 60
CONFIRMATION_DELAY = 2
RESPONSE_TIME_THRESHOLD = 5.0
FIRST_REPEAT_ALERT_INTERVAL = 30 * 60
LATER_REPEAT_ALERT_INTERVAL = 320 * 60
MAX_CONCURRENCY = 8

_REDIRECT_STATUSES = {301, 302, 303, 307, 308}
_METADATA_HOSTS = {
    "metadata",
    "metadata.google.internal",
    "instance-data",
    "instance-data.ec2.internal",
}


class WebsiteMonitoringError(RuntimeError):
    def __init__(self, message: str, *, code: str):
        super().__init__(message)
        self.code = code


class UnsafeTargetError(WebsiteMonitoringError):
    pass


@dataclass(frozen=True)
class SafeHttpResponse:
    requested_url: str
    final_url: str
    status: int
    latency_ms: int
    headers: Mapping[str, str]
    body: bytes
    redirects: tuple[str, ...]


@dataclass(frozen=True)
class WebsiteCheckOutcome:
    kind: str  # success | failure | checker_error
    http_status: int = 0
    latency_ms: int = 0
    error_kind: str = ""


@dataclass(frozen=True)
class MonitorTransition:
    next_state: str
    open_incident: bool = False
    resolve_incident: bool = False
    needs_recheck: bool = False
    notify_kind: str = ""


@dataclass(frozen=True)
class WebsiteMonitorRecord:
    id: int
    canonical_url: str
    hostname: str
    enabled: int
    state: str
    last_check_at: int
    next_check_at: int
    last_http_status: int
    last_latency_ms: int
    last_error_kind: str
    consecutive_failures: int
    created_at: int
    updated_at: int


@dataclass(frozen=True)
class WebsiteIncidentRecord:
    id: int
    monitor_id: int
    opened_at: int
    resolved_at: int
    reason_kind: str
    first_http_status: int
    last_http_status: int
    alert_count: int
    last_alert_at: int


def _normalized_host(hostname: str) -> str:
    value = (hostname or "").strip().rstrip(".")
    if not value:
        raise UnsafeTargetError("URL должен содержать hostname.", code="invalid_target")
    try:
        ascii_value = value.encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise UnsafeTargetError("Некорректное имя хоста.", code="invalid_target") from exc
    labels = ascii_value.split(".")
    label_re = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
    if (
        len(ascii_value) > 253
        or any(
            not label
            or len(label) > 63
            or label_re.fullmatch(label) is None
            for label in labels
        )
    ):
        raise UnsafeTargetError("Некорректное имя хоста.", code="invalid_target")
    return ascii_value


def _validate_public_address(value: str) -> str:
    try:
        address = ipaddress.ip_address(value)
    except ValueError as exc:
        raise UnsafeTargetError("Некорректный IP-адрес.", code="unsafe_target") from exc
    if (
        not address.is_global
        or address.is_loopback
        or address.is_private
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    ):
        raise UnsafeTargetError(
            "Локальные, служебные и непубличные адреса запрещены.",
            code="unsafe_target",
        )
    return str(address)


def _validate_hostname_policy(hostname: str) -> str:
    host = _normalized_host(hostname)
    if host in _METADATA_HOSTS or host.endswith(".metadata.google.internal"):
        raise UnsafeTargetError(
            "Cloud metadata endpoints запрещены.",
            code="unsafe_target",
        )
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return host
    _validate_public_address(host)
    return host


def canonicalize_public_url(raw: str) -> str:
    value = (raw or "").strip()
    if not value:
        raise UnsafeTargetError("URL не указан.", code="invalid_target")
    if "://" not in value:
        value = "https://" + value

    try:
        parsed = urlsplit(value)
    except ValueError as exc:
        raise UnsafeTargetError("Некорректный URL.", code="invalid_target") from exc

    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"} or not parsed.hostname:
        raise UnsafeTargetError(
            "Разрешены только абсолютные http/https URL.",
            code="invalid_target",
        )
    if parsed.username is not None or parsed.password is not None:
        raise UnsafeTargetError(
            "Credentials/userinfo в URL запрещены.",
            code="invalid_target",
        )

    host = _validate_hostname_policy(parsed.hostname)
    try:
        port = parsed.port
    except ValueError as exc:
        raise UnsafeTargetError("Некорректный порт URL.", code="invalid_target") from exc

    expected_port = 80 if scheme == "http" else 443
    if port is not None and port != expected_port:
        raise UnsafeTargetError(
            "Разрешены только стандартные HTTP/HTTPS порты.",
            code="unsafe_target",
        )

    host_for_netloc = f"[{host}]" if ":" in host else host
    netloc = host_for_netloc if port is None else f"{host_for_netloc}:{port}"
    path = parsed.path or "/"
    return urlunsplit((scheme, netloc, path, parsed.query, ""))


class SafePublicResolver(AbstractResolver):
    async def resolve(
        self,
        host: str,
        port: int = 0,
        family: int = socket.AF_UNSPEC,
    ) -> list[dict[str, object]]:
        normalized = _validate_hostname_policy(host)
        try:
            literal = ipaddress.ip_address(normalized)
        except ValueError:
            literal = None

        if literal is not None:
            addresses = [(literal.version, str(literal))]
        else:
            loop = asyncio.get_running_loop()
            try:
                infos = await loop.getaddrinfo(
                    normalized,
                    port,
                    family=family,
                    type=socket.SOCK_STREAM,
                )
            except socket.gaierror as exc:
                raise OSError(f"DNS resolution failed for {normalized}") from exc
            addresses = []
            seen: set[str] = set()
            for fam, _type, _proto, _canon, sockaddr in infos:
                address = _validate_public_address(str(sockaddr[0]))
                if address in seen:
                    continue
                seen.add(address)
                version = 6 if fam == socket.AF_INET6 else 4
                addresses.append((version, address))

        if not addresses:
            raise OSError(f"No public addresses resolved for {normalized}")

        result: list[dict[str, object]] = []
        for version, address in addresses:
            result.append({
                "hostname": normalized,
                "host": address,
                "port": int(port),
                "family": socket.AF_INET6 if version == 6 else socket.AF_INET,
                "proto": 0,
                "flags": 0,
            })
        return result

    async def close(self) -> None:
        return None


async def validate_public_url_resolution(raw_url: str) -> str:
    canonical = canonicalize_public_url(raw_url)
    parsed = urlsplit(canonical)
    host = parsed.hostname or ""
    port = parsed.port or (80 if parsed.scheme == "http" else 443)
    resolver = SafePublicResolver()
    await resolver.resolve(host, port)
    return canonical


class SafeOutboundHttpClient:
    def __init__(self, *, max_concurrency: int = MAX_CONCURRENCY):
        self._semaphore = asyncio.Semaphore(max(1, int(max_concurrency)))

    async def fetch(
        self,
        raw_url: str,
        *,
        max_body_bytes: int = MAX_RESPONSE_BYTES,
    ) -> SafeHttpResponse:
        requested_url = canonicalize_public_url(raw_url)
        timeout = aiohttp.ClientTimeout(total=10, connect=3, sock_read=7)
        connector = aiohttp.TCPConnector(
            resolver=SafePublicResolver(),
            use_dns_cache=False,
            ttl_dns_cache=0,
            limit=max(1, MAX_CONCURRENCY),
        )
        current_url = requested_url
        redirects: list[str] = []
        started = time.monotonic()

        async with self._semaphore:
            try:
                async with aiohttp.ClientSession(
                    timeout=timeout,
                    connector=connector,
                    trust_env=False,
                    auto_decompress=True,
                ) as session:
                    for redirect_index in range(MAX_REDIRECTS + 1):
                        current_url = canonicalize_public_url(current_url)
                        async with session.get(
                            current_url,
                            allow_redirects=False,
                            headers={
                                "User-Agent": "3xui-telegram-bot/website-monitor",
                                "Accept": "*/*",
                            },
                        ) as response:
                            if response.status in _REDIRECT_STATUSES:
                                location = response.headers.get("Location", "").strip()
                                if not location:
                                    raise WebsiteMonitoringError(
                                        "Redirect без Location.",
                                        code="invalid_redirect",
                                    )
                                if redirect_index >= MAX_REDIRECTS:
                                    raise WebsiteMonitoringError(
                                        "Превышен лимит redirect.",
                                        code="too_many_redirects",
                                    )
                                next_url = canonicalize_public_url(
                                    urljoin(current_url, location)
                                )
                                redirects.append(next_url)
                                current_url = next_url
                                continue

                            chunks: list[bytes] = []
                            size = 0
                            async for chunk in response.content.iter_chunked(65536):
                                size += len(chunk)
                                if size > max(1, int(max_body_bytes)):
                                    raise WebsiteMonitoringError(
                                        "HTTP response превышает допустимый размер.",
                                        code="response_too_large",
                                    )
                                chunks.append(bytes(chunk))
                            latency_ms = int((time.monotonic() - started) * 1000)
                            selected_headers = {
                                key.lower(): value[:512]
                                for key, value in response.headers.items()
                                if key.lower() in {
                                    "content-type",
                                    "server",
                                    "cache-control",
                                    "x-robots-tag",
                                }
                            }
                            return SafeHttpResponse(
                                requested_url=requested_url,
                                final_url=current_url,
                                status=int(response.status),
                                latency_ms=max(0, latency_ms),
                                headers=selected_headers,
                                body=b"".join(chunks),
                                redirects=tuple(redirects),
                            )
            except UnsafeTargetError:
                raise
            except WebsiteMonitoringError:
                raise
            except asyncio.TimeoutError as exc:
                raise WebsiteMonitoringError(
                    "HTTP check превысил timeout.",
                    code="timeout",
                ) from exc
            except (aiohttp.ClientConnectorCertificateError, ssl.SSLError) as exc:
                raise WebsiteMonitoringError(
                    "TLS validation failed.",
                    code="tls",
                ) from exc
            except aiohttp.ClientConnectorError as exc:
                code = "dns" if isinstance(exc.os_error, socket.gaierror) else "connect"
                raise WebsiteMonitoringError(
                    "Не удалось подключиться к target.",
                    code=code,
                ) from exc
            except aiohttp.ClientError as exc:
                raise WebsiteMonitoringError(
                    "HTTP transport error.",
                    code="transport",
                ) from exc

        raise WebsiteMonitoringError("HTTP check не завершён.", code="internal")


def classify_http_response(response: SafeHttpResponse) -> WebsiteCheckOutcome:
    if response.status == 200 and response.latency_ms <= int(RESPONSE_TIME_THRESHOLD * 1000):
        return WebsiteCheckOutcome(
            kind="success",
            http_status=response.status,
            latency_ms=response.latency_ms,
        )
    error_kind = "http_status" if response.status != 200 else "slow"
    return WebsiteCheckOutcome(
        kind="failure",
        http_status=response.status,
        latency_ms=response.latency_ms,
        error_kind=error_kind,
    )


def classify_check_error(exc: Exception) -> WebsiteCheckOutcome:
    if isinstance(exc, UnsafeTargetError):
        return WebsiteCheckOutcome(kind="checker_error", error_kind=exc.code)
    if isinstance(exc, WebsiteMonitoringError):
        if exc.code in {"timeout", "dns", "connect", "tls"}:
            return WebsiteCheckOutcome(kind="failure", error_kind=exc.code)
        return WebsiteCheckOutcome(kind="checker_error", error_kind=exc.code)
    return WebsiteCheckOutcome(kind="checker_error", error_kind="internal")


def transition_monitor(
    current_state: str,
    outcome: WebsiteCheckOutcome,
    *,
    confirmed: bool = False,
) -> MonitorTransition:
    state = current_state if current_state in {"unknown", "up", "suspect", "down"} else "unknown"

    if outcome.kind == "checker_error":
        return MonitorTransition(next_state=state)

    if outcome.kind == "success":
        if state == "down":
            return MonitorTransition(
                next_state="up",
                resolve_incident=True,
                notify_kind="recovered",
            )
        return MonitorTransition(next_state="up")

    if outcome.kind != "failure":
        return MonitorTransition(next_state=state)

    if state == "down":
        return MonitorTransition(next_state="down", notify_kind="repeat")
    if state == "suspect" or confirmed:
        return MonitorTransition(
            next_state="down",
            open_incident=True,
            notify_kind="opened",
        )
    return MonitorTransition(next_state="suspect", needs_recheck=True)


class WebsiteMonitoringRepository:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def add_watcher(
        self,
        raw_url: str,
        telegram_id: int,
        *,
        max_targets: int = MAX_MONITORS_PER_ADMIN,
    ) -> WebsiteMonitorRecord:
        canonical = canonicalize_public_url(raw_url)
        hostname = _normalized_host(urlsplit(canonical).hostname or "")
        now = int(time.time())

        async with aiosqlite.connect(self.db_path, timeout=15) as db:
            db.row_factory = aiosqlite.Row
            await db.execute("BEGIN IMMEDIATE")
            existing = await db.execute(
                """
                SELECT m.*
                FROM website_monitors AS m
                JOIN website_monitor_watchers AS w ON w.monitor_id = m.id
                WHERE m.canonical_url = ? AND w.telegram_id = ?
                """,
                (canonical, int(telegram_id)),
            )
            row = await existing.fetchone()
            if row:
                await db.rollback()
                return WebsiteMonitorRecord(**dict(row))

            count_cur = await db.execute(
                "SELECT COUNT(*) FROM website_monitor_watchers WHERE telegram_id = ?",
                (int(telegram_id),),
            )
            watcher_count = int((await count_cur.fetchone())[0])
            if watcher_count >= max(1, int(max_targets)):
                await db.rollback()
                raise WebsiteMonitoringError(
                    "Достигнут лимит сайтов для администратора.",
                    code="monitor_limit",
                )

            monitor_cur = await db.execute(
                "SELECT * FROM website_monitors WHERE canonical_url = ?",
                (canonical,),
            )
            monitor_row = await monitor_cur.fetchone()
            if monitor_row is None:
                cur = await db.execute(
                    """
                    INSERT INTO website_monitors(
                        canonical_url, hostname, enabled, state, last_check_at,
                        next_check_at, last_http_status, last_latency_ms,
                        last_error_kind, consecutive_failures, created_at, updated_at
                    ) VALUES (?, ?, 1, 'unknown', 0, ?, 0, 0, '', 0, ?, ?)
                    """,
                    (canonical, hostname, now, now, now),
                )
                monitor_id = int(cur.lastrowid)
            else:
                monitor_id = int(monitor_row["id"])

            await db.execute(
                """
                INSERT INTO website_monitor_watchers(
                    monitor_id, telegram_id, notifications_enabled, created_at,
                    monitoring_enabled
                ) VALUES (?, ?, 1, ?, 1)
                """,
                (monitor_id, int(telegram_id), now),
            )
            await db.commit()

        record = await self.get_monitor(monitor_id)
        if record is None:
            raise WebsiteMonitoringError("Monitor disappeared after insert.", code="internal")
        return record

    async def get_monitor(self, monitor_id: int) -> WebsiteMonitorRecord | None:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM website_monitors WHERE id = ?",
                (int(monitor_id),),
            )
            row = await cur.fetchone()
            return WebsiteMonitorRecord(**dict(row)) if row else None

    async def due_monitors(self, *, now: int | None = None, limit: int = 50) -> list[WebsiteMonitorRecord]:
        timestamp = int(time.time()) if now is None else int(now)
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT m.*
                FROM website_monitors AS m
                WHERE m.enabled = 1
                  AND m.next_check_at <= ?
                  AND EXISTS (
                      SELECT 1
                      FROM website_monitor_watchers AS w
                      WHERE w.monitor_id = m.id
                        AND w.monitoring_enabled = 1
                  )
                ORDER BY m.next_check_at, m.id
                LIMIT ?
                """,
                (timestamp, max(1, min(200, int(limit)))),
            )
            rows = await cur.fetchall()
            return [WebsiteMonitorRecord(**dict(row)) for row in rows]

    async def watchers(self, monitor_id: int, *, enabled_only: bool = True) -> tuple[int, ...]:
        query = "SELECT telegram_id FROM website_monitor_watchers WHERE monitor_id = ?"
        if enabled_only:
            query += " AND notifications_enabled = 1 AND monitoring_enabled = 1"
        query += " ORDER BY telegram_id"
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(query, (int(monitor_id),))
            return tuple(int(row[0]) for row in await cur.fetchall())

    async def remove_watcher(self, monitor_id: int, telegram_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "DELETE FROM website_monitor_watchers WHERE monitor_id = ? AND telegram_id = ?",
                (int(monitor_id), int(telegram_id)),
            )
            await db.commit()
            removed = bool(cur.rowcount)
        if removed:
            await self.cleanup_orphan_monitor(monitor_id)
        return removed

    async def store_check(
        self,
        monitor_id: int,
        *,
        state: str,
        outcome: WebsiteCheckOutcome,
        next_check_at: int,
        checked_at: int | None = None,
    ) -> None:
        if state not in {"unknown", "up", "suspect", "down"}:
            raise ValueError("invalid monitor state")
        now = int(time.time()) if checked_at is None else int(checked_at)
        failures_delta = 1 if outcome.kind == "failure" else 0
        async with aiosqlite.connect(self.db_path) as db:
            if outcome.kind == "success":
                await db.execute(
                    """
                    UPDATE website_monitors
                    SET state = ?, last_check_at = ?, next_check_at = ?,
                        last_http_status = ?, last_latency_ms = ?,
                        last_error_kind = '', consecutive_failures = 0, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        state, now, int(next_check_at), int(outcome.http_status),
                        max(0, int(outcome.latency_ms)), now, int(monitor_id),
                    ),
                )
            else:
                await db.execute(
                    """
                    UPDATE website_monitors
                    SET state = ?, last_check_at = ?, next_check_at = ?,
                        last_http_status = ?, last_latency_ms = ?,
                        last_error_kind = ?,
                        consecutive_failures = consecutive_failures + ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        state, now, int(next_check_at), int(outcome.http_status),
                        max(0, int(outcome.latency_ms)), outcome.error_kind[:64],
                        failures_delta, now, int(monitor_id),
                    ),
                )
            await db.commit()

    async def open_incident(
        self,
        monitor_id: int,
        outcome: WebsiteCheckOutcome,
        *,
        opened_at: int | None = None,
    ) -> int:
        now = int(time.time()) if opened_at is None else int(opened_at)
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                """
                SELECT id FROM website_incidents
                WHERE monitor_id = ? AND resolved_at = 0
                ORDER BY id DESC LIMIT 1
                """,
                (int(monitor_id),),
            )
            row = await cur.fetchone()
            if row:
                return int(row[0])
            created = await db.execute(
                """
                INSERT INTO website_incidents(
                    monitor_id, opened_at, resolved_at, reason_kind,
                    first_http_status, last_http_status, alert_count, last_alert_at
                ) VALUES (?, ?, 0, ?, ?, ?, 0, 0)
                """,
                (
                    int(monitor_id), now, outcome.error_kind[:64],
                    int(outcome.http_status), int(outcome.http_status),
                ),
            )
            await db.commit()
            return int(created.lastrowid)

    async def resolve_incident(self, monitor_id: int, *, resolved_at: int | None = None) -> int | None:
        now = int(time.time()) if resolved_at is None else int(resolved_at)
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                """
                SELECT id FROM website_incidents
                WHERE monitor_id = ? AND resolved_at = 0
                ORDER BY id DESC LIMIT 1
                """,
                (int(monitor_id),),
            )
            row = await cur.fetchone()
            if not row:
                return None
            incident_id = int(row[0])
            await db.execute(
                "UPDATE website_incidents SET resolved_at = ? WHERE id = ?",
                (now, incident_id),
            )
            await db.commit()
            return incident_id

    async def record_notification(
        self,
        incident_id: int,
        telegram_id: int,
        *,
        kind: str,
        sequence: int = 0,
        sent_at: int | None = None,
    ) -> bool:
        if kind not in {"opened", "repeat", "recovered"}:
            raise ValueError("invalid notification kind")
        now = int(time.time()) if sent_at is None else int(sent_at)
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                """
                INSERT OR IGNORE INTO website_incident_notifications(
                    incident_id, telegram_id, kind, sequence, sent_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    int(incident_id), int(telegram_id), kind,
                    max(0, int(sequence)), now,
                ),
            )
            await db.commit()
            return bool(cur.rowcount)


    async def list_for_watcher(self, telegram_id: int) -> list[WebsiteMonitorRecord]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT m.*
                FROM website_monitors AS m
                JOIN website_monitor_watchers AS w ON w.monitor_id = m.id
                WHERE w.telegram_id = ?
                ORDER BY m.hostname COLLATE NOCASE, m.id
                """,
                (int(telegram_id),),
            )
            rows = await cur.fetchall()
            return [WebsiteMonitorRecord(**dict(row)) for row in rows]

    async def is_watcher(self, monitor_id: int, telegram_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                """
                SELECT 1 FROM website_monitor_watchers
                WHERE monitor_id = ? AND telegram_id = ?
                """,
                (int(monitor_id), int(telegram_id)),
            )
            return await cur.fetchone() is not None

    async def monitoring_enabled(self, monitor_id: int, telegram_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                """
                SELECT monitoring_enabled
                FROM website_monitor_watchers
                WHERE monitor_id = ? AND telegram_id = ?
                """,
                (int(monitor_id), int(telegram_id)),
            )
            row = await cur.fetchone()
            return bool(row and int(row[0]))

    async def set_monitoring_enabled(
        self,
        monitor_id: int,
        telegram_id: int,
        enabled: bool,
    ) -> bool:
        now = int(time.time())
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("BEGIN IMMEDIATE")
            cur = await db.execute(
                """
                UPDATE website_monitor_watchers
                SET monitoring_enabled = ?
                WHERE monitor_id = ? AND telegram_id = ?
                """,
                (1 if enabled else 0, int(monitor_id), int(telegram_id)),
            )
            changed = bool(cur.rowcount)
            if changed and enabled:
                await db.execute(
                    """
                    UPDATE website_monitors
                    SET next_check_at = CASE
                        WHEN next_check_at = 0 OR next_check_at > ? THEN ?
                        ELSE next_check_at
                    END,
                    updated_at = ?
                    WHERE id = ?
                    """,
                    (now, now, now, int(monitor_id)),
                )
            await db.commit()
            return changed

    async def list_all_monitors(self, *, limit: int = 100) -> list[WebsiteMonitorRecord]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT * FROM website_monitors
                ORDER BY hostname COLLATE NOCASE, id
                LIMIT ?
                """,
                (max(1, min(500, int(limit))),),
            )
            rows = await cur.fetchall()
            return [WebsiteMonitorRecord(**dict(row)) for row in rows]

    async def watcher_count(self, monitor_id: int) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "SELECT COUNT(*) FROM website_monitor_watchers WHERE monitor_id = ?",
                (int(monitor_id),),
            )
            return int((await cur.fetchone())[0])

    async def delete_monitor_global(self, monitor_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("BEGIN IMMEDIATE")
            incident_cur = await db.execute(
                "SELECT id FROM website_incidents WHERE monitor_id = ?",
                (int(monitor_id),),
            )
            incident_ids = [int(row[0]) for row in await incident_cur.fetchall()]
            if incident_ids:
                placeholders = ",".join("?" for _ in incident_ids)
                await db.execute(
                    f"DELETE FROM website_incident_notifications WHERE incident_id IN ({placeholders})",
                    tuple(incident_ids),
                )
            await db.execute(
                "DELETE FROM website_incidents WHERE monitor_id = ?",
                (int(monitor_id),),
            )
            await db.execute(
                "DELETE FROM website_monitor_watchers WHERE monitor_id = ?",
                (int(monitor_id),),
            )
            deleted = await db.execute(
                "DELETE FROM website_monitors WHERE id = ?",
                (int(monitor_id),),
            )
            await db.commit()
            return bool(deleted.rowcount)

    async def notifications_enabled(self, monitor_id: int, telegram_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                """
                SELECT notifications_enabled
                FROM website_monitor_watchers
                WHERE monitor_id = ? AND telegram_id = ?
                """,
                (int(monitor_id), int(telegram_id)),
            )
            row = await cur.fetchone()
            return bool(row and int(row[0]))

    async def set_notifications_enabled(
        self,
        monitor_id: int,
        telegram_id: int,
        enabled: bool,
    ) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                """
                UPDATE website_monitor_watchers
                SET notifications_enabled = ?
                WHERE monitor_id = ? AND telegram_id = ?
                """,
                (1 if enabled else 0, int(monitor_id), int(telegram_id)),
            )
            await db.commit()
            return bool(cur.rowcount)

    async def list_incidents(
        self,
        monitor_id: int,
        *,
        limit: int = 10,
    ) -> list[WebsiteIncidentRecord]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT * FROM website_incidents
                WHERE monitor_id = ?
                ORDER BY opened_at DESC, id DESC
                LIMIT ?
                """,
                (int(monitor_id), max(1, min(50, int(limit)))),
            )
            rows = await cur.fetchall()
            return [WebsiteIncidentRecord(**dict(row)) for row in rows]

    async def get_incident(self, incident_id: int) -> WebsiteIncidentRecord | None:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM website_incidents WHERE id = ?",
                (int(incident_id),),
            )
            row = await cur.fetchone()
            return WebsiteIncidentRecord(**dict(row)) if row else None

    async def mark_incident_alert(
        self,
        incident_id: int,
        *,
        sent_at: int | None = None,
    ) -> WebsiteIncidentRecord | None:
        now = int(time.time()) if sent_at is None else int(sent_at)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE website_incidents
                SET alert_count = alert_count + 1, last_alert_at = ?
                WHERE id = ?
                """,
                (now, int(incident_id)),
            )
            await db.commit()
        return await self.get_incident(incident_id)

    async def cleanup_orphan_monitor(self, monitor_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "SELECT COUNT(*) FROM website_monitor_watchers WHERE monitor_id = ?",
                (int(monitor_id),),
            )
            if int((await cur.fetchone())[0]) > 0:
                return False
            incident_cur = await db.execute(
                "SELECT id FROM website_incidents WHERE monitor_id = ?",
                (int(monitor_id),),
            )
            incident_ids = [int(row[0]) for row in await incident_cur.fetchall()]
            if incident_ids:
                placeholders = ",".join("?" for _ in incident_ids)
                await db.execute(
                    f"DELETE FROM website_incident_notifications WHERE incident_id IN ({placeholders})",
                    tuple(incident_ids),
                )
            await db.execute(
                "DELETE FROM website_incidents WHERE monitor_id = ?",
                (int(monitor_id),),
            )
            deleted = await db.execute(
                "DELETE FROM website_monitors WHERE id = ?",
                (int(monitor_id),),
            )
            await db.commit()
            return bool(deleted.rowcount)


async def check_once(client: SafeOutboundHttpClient, url: str) -> WebsiteCheckOutcome:
    try:
        response = await client.fetch(url)
    except Exception as exc:
        return classify_check_error(exc)
    return classify_http_response(response)


@dataclass(frozen=True)
class MonitorCheckExecution:
    monitor_id: int
    previous_state: str
    final_state: str
    outcome: WebsiteCheckOutcome
    incident_id: int | None
    notify_kind: str


class WebsiteMonitoringService:
    def __init__(
        self,
        repository: WebsiteMonitoringRepository,
        client: SafeOutboundHttpClient | None = None,
    ):
        self.repository = repository
        self.client = client or SafeOutboundHttpClient()
        self._locks: dict[int, asyncio.Lock] = {}

    def _lock_for(self, monitor_id: int) -> asyncio.Lock:
        key = int(monitor_id)
        lock = self._locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[key] = lock
        return lock

    @staticmethod
    def _next_check_at(state: str, now: int) -> int:
        interval = DOWN_CHECK_INTERVAL if state == "down" else NORMAL_CHECK_INTERVAL
        return int(now) + interval

    async def check_monitor(
        self,
        monitor_id: int,
        *,
        sleep=asyncio.sleep,
    ) -> MonitorCheckExecution:
        lock = self._lock_for(monitor_id)
        async with lock:
            monitor = await self.repository.get_monitor(monitor_id)
            if monitor is None:
                raise WebsiteMonitoringError("Monitor not found.", code="not_found")
            if not monitor.enabled:
                raise WebsiteMonitoringError("Monitor is disabled.", code="disabled")

            previous_state = monitor.state
            first = await check_once(self.client, monitor.canonical_url)
            transition = transition_monitor(previous_state, first)
            final_outcome = first
            final_transition = transition

            if transition.needs_recheck:
                suspect_at = int(time.time())
                await self.repository.store_check(
                    monitor.id,
                    state="suspect",
                    outcome=first,
                    next_check_at=suspect_at + CONFIRMATION_DELAY,
                    checked_at=suspect_at,
                )
                await sleep(CONFIRMATION_DELAY)
                second = await check_once(self.client, monitor.canonical_url)
                final_outcome = second

                if second.kind == "checker_error":
                    stable = previous_state if previous_state in {"up", "down"} else "unknown"
                    final_transition = MonitorTransition(next_state=stable)
                else:
                    final_transition = transition_monitor(
                        "suspect",
                        second,
                        confirmed=True,
                    )

            now = int(time.time())
            final_state = final_transition.next_state
            await self.repository.store_check(
                monitor.id,
                state=final_state,
                outcome=final_outcome,
                next_check_at=self._next_check_at(final_state, now),
                checked_at=now,
            )

            incident_id: int | None = None
            if final_transition.open_incident:
                incident_id = await self.repository.open_incident(
                    monitor.id,
                    final_outcome,
                    opened_at=now,
                )
            elif final_transition.resolve_incident:
                incident_id = await self.repository.resolve_incident(
                    monitor.id,
                    resolved_at=now,
                )
            elif final_state == "down":
                async with aiosqlite.connect(self.repository.db_path) as db:
                    cur = await db.execute(
                        """
                        SELECT id FROM website_incidents
                        WHERE monitor_id = ? AND resolved_at = 0
                        ORDER BY id DESC LIMIT 1
                        """,
                        (monitor.id,),
                    )
                    row = await cur.fetchone()
                    incident_id = int(row[0]) if row else None

            return MonitorCheckExecution(
                monitor_id=monitor.id,
                previous_state=previous_state,
                final_state=final_state,
                outcome=final_outcome,
                incident_id=incident_id,
                notify_kind=final_transition.notify_kind,
            )

    async def check_due_once(
        self,
        *,
        now: int | None = None,
        limit: int = 50,
    ) -> tuple[MonitorCheckExecution | Exception, ...]:
        monitors = await self.repository.due_monitors(now=now, limit=limit)
        if not monitors:
            return ()
        results = await asyncio.gather(
            *(self.check_monitor(item.id) for item in monitors),
            return_exceptions=True,
        )
        return tuple(results)
