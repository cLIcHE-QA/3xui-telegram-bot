from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import io
import json
import re
import socket
from typing import Iterable
from urllib.parse import quote, urljoin, urlsplit
import xml.etree.ElementTree as ET

import dns.resolver
import qrcode

from website_monitoring import (
    MAX_RESPONSE_BYTES,
    MAX_SITEMAP_BYTES,
    MAX_SITEMAP_DOCUMENTS,
    MAX_SITEMAP_URLS,
    SafeOutboundHttpClient,
    WebsiteMonitoringError,
    canonicalize_public_url,
)


class WebsiteDiagnosticsError(RuntimeError):
    def __init__(self, message: str, *, code: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class DnsRecord:
    record_type: str
    value: str


@dataclass(frozen=True)
class WhoisSummary:
    domain: str
    registrar: str
    created_at: str
    expires_at: str
    age_days: int | None
    statuses: tuple[str, ...]


@dataclass(frozen=True)
class HttpSummary:
    requested_url: str
    final_url: str
    status: int
    latency_ms: int
    content_type: str
    server: str
    redirects: tuple[str, ...]


@dataclass(frozen=True)
class SeoSummary:
    robots_txt_available: bool
    root_disallowed: bool
    meta_noindex: bool
    header_noindex: bool


@dataclass(frozen=True)
class PageSpeedSummary:
    enabled: bool
    performance_score: int | None
    category: str


def normalize_domain(raw: str) -> str:
    value = (raw or "").strip().rstrip(".")
    if "://" in value:
        try:
            value = urlsplit(value).hostname or ""
        except ValueError as exc:
            raise WebsiteDiagnosticsError("Некорректный домен.", code="invalid_domain") from exc
    if not value or "/" in value or "@" in value or ":" in value:
        raise WebsiteDiagnosticsError("Некорректный домен.", code="invalid_domain")
    try:
        ascii_value = value.encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise WebsiteDiagnosticsError("Некорректный домен.", code="invalid_domain") from exc
    labels = ascii_value.split(".")
    if len(labels) < 2 or len(ascii_value) > 253:
        raise WebsiteDiagnosticsError("Нужен публичный домен.", code="invalid_domain")
    label_re = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
    if any(not label_re.fullmatch(label) for label in labels):
        raise WebsiteDiagnosticsError("Некорректный домен.", code="invalid_domain")
    if ascii_value in {"localhost", "metadata.google.internal"} or ascii_value.endswith(".local"):
        raise WebsiteDiagnosticsError("Локальные домены запрещены.", code="unsafe_domain")
    return ascii_value


async def dns_summary(raw_domain: str) -> tuple[DnsRecord, ...]:
    domain = normalize_domain(raw_domain)

    def _query() -> tuple[DnsRecord, ...]:
        resolver = dns.resolver.Resolver(configure=True)
        resolver.lifetime = 5.0
        resolver.timeout = 2.5
        records: list[DnsRecord] = []
        for record_type in ("A", "AAAA", "CNAME", "MX", "NS", "TXT"):
            try:
                answers = resolver.resolve(domain, record_type, raise_on_no_answer=False)
            except (dns.resolver.NXDOMAIN, dns.resolver.NoNameservers, dns.resolver.LifetimeTimeout):
                continue
            except Exception:
                continue
            if answers.rrset is None:
                continue
            for item in list(answers)[:20]:
                value = item.to_text().strip()
                if record_type == "TXT":
                    value = value[:500]
                records.append(DnsRecord(record_type=record_type, value=value))
                if len(records) >= 60:
                    return tuple(records)
        return tuple(records)

    return await asyncio.to_thread(_query)


def _rdap_event(events: object, action: str) -> str:
    if not isinstance(events, list):
        return ""
    for item in events:
        if not isinstance(item, dict):
            continue
        if str(item.get("eventAction") or "").lower() != action:
            continue
        return str(item.get("eventDate") or "")
    return ""


def _rdap_registrar(entities: object) -> str:
    if not isinstance(entities, list):
        return ""
    for entity in entities:
        if not isinstance(entity, dict):
            continue
        roles = entity.get("roles")
        if not isinstance(roles, list) or "registrar" not in roles:
            continue
        vcard = entity.get("vcardArray")
        if not (isinstance(vcard, list) and len(vcard) > 1 and isinstance(vcard[1], list)):
            continue
        for field in vcard[1]:
            if (
                isinstance(field, list)
                and len(field) >= 4
                and field[0] == "fn"
            ):
                return str(field[3] or "")[:200]
    return ""


_MSK = timezone(timedelta(hours=3))


def _parse_rdap_date(value: str) -> datetime | None:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _format_rdap_timestamp_msk(value: str) -> str:
    parsed = _parse_rdap_date(value)
    if parsed is None:
        return ""
    return parsed.astimezone(_MSK).strftime("%d.%m.%Y %H:%M MSK")


async def whois_summary(
    raw_domain: str,
    client: SafeOutboundHttpClient,
) -> WhoisSummary:
    """Use RDAP as the bounded modern WHOIS transport.

    rdap.org is used only as a bootstrap redirector. Every redirect is still
    validated by SafeOutboundHttpClient before connection.
    """
    domain = normalize_domain(raw_domain)
    url = f"https://rdap.org/domain/{quote(domain, safe='')}"
    response = await client.fetch(url, max_body_bytes=MAX_RESPONSE_BYTES)
    if response.status != 200:
        raise WebsiteDiagnosticsError(
            f"RDAP вернул HTTP {response.status}.",
            code="whois_unavailable",
        )
    try:
        payload = json.loads(response.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WebsiteDiagnosticsError("Некорректный RDAP response.", code="invalid_response") from exc
    if not isinstance(payload, dict):
        raise WebsiteDiagnosticsError("Некорректный RDAP response.", code="invalid_response")

    created_raw = _rdap_event(payload.get("events"), "registration")
    expires_raw = _rdap_event(payload.get("events"), "expiration")
    created = _parse_rdap_date(created_raw)
    age_days = None
    if created is not None:
        age_days = max(0, (datetime.now(timezone.utc) - created).days)

    statuses_raw = payload.get("status")
    statuses = tuple(
        str(item)[:120]
        for item in statuses_raw[:12]
        if isinstance(item, str)
    ) if isinstance(statuses_raw, list) else ()

    return WhoisSummary(
        domain=domain,
        registrar=_rdap_registrar(payload.get("entities")),
        created_at=_format_rdap_timestamp_msk(created_raw),
        expires_at=_format_rdap_timestamp_msk(expires_raw),
        age_days=age_days,
        statuses=statuses,
    )


async def http_summary(
    raw_url: str,
    client: SafeOutboundHttpClient,
) -> HttpSummary:
    response = await client.fetch(raw_url, max_body_bytes=MAX_RESPONSE_BYTES)
    return HttpSummary(
        requested_url=response.requested_url,
        final_url=response.final_url,
        status=response.status,
        latency_ms=response.latency_ms,
        content_type=response.headers.get("content-type", ""),
        server=response.headers.get("server", ""),
        redirects=response.redirects,
    )


def detect_cms(body: bytes, headers: dict[str, str] | object = ()) -> str:
    text = body[:MAX_RESPONSE_BYTES].decode("utf-8", errors="ignore").lower()
    header_text = " ".join(
        f"{k}:{v}" for k, v in dict(headers).items()
    ).lower() if headers else ""
    haystack = text + "\n" + header_text
    signatures = (
        ("WordPress", ("wp-content/", "wp-includes/", 'name="generator" content="wordpress')),
        ("Drupal", ("drupal-settings-json", "/sites/default/files/", 'content="drupal')),
        ("Joomla", ("/media/system/js/", 'content="joomla')),
        ("Bitrix", ("/bitrix/", "x-powered-cms: bitrix")),
        ("Shopify", ("cdn.shopify.com", "shopify.theme")),
    )
    for label, needles in signatures:
        if any(needle in haystack for needle in needles):
            return label
    return "не определена"


async def cms_summary(
    raw_url: str,
    client: SafeOutboundHttpClient,
) -> tuple[HttpSummary, str]:
    response = await client.fetch(raw_url, max_body_bytes=MAX_RESPONSE_BYTES)
    summary = HttpSummary(
        requested_url=response.requested_url,
        final_url=response.final_url,
        status=response.status,
        latency_ms=response.latency_ms,
        content_type=response.headers.get("content-type", ""),
        server=response.headers.get("server", ""),
        redirects=response.redirects,
    )
    return summary, detect_cms(response.body, response.headers)


def _robots_root_disallowed(text: str) -> bool:
    active_star = False
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, value = (part.strip() for part in line.split(":", 1))
        key = key.lower()
        if key == "user-agent":
            active_star = value == "*"
            continue
        if active_star and key == "disallow" and value == "/":
            return True
    return False


def _meta_noindex(body: bytes) -> bool:
    text = body[:MAX_RESPONSE_BYTES].decode("utf-8", errors="ignore")
    for match in re.finditer(
        r"<meta\b[^>]*\bname\s*=\s*['\"](?:robots|googlebot)['\"][^>]*>",
        text,
        flags=re.IGNORECASE,
    ):
        tag = match.group(0)
        content = re.search(
            r"\bcontent\s*=\s*['\"]([^'\"]+)['\"]",
            tag,
            flags=re.IGNORECASE,
        )
        if content and "noindex" in content.group(1).lower():
            return True
    return False


async def seo_summary(
    raw_url: str,
    client: SafeOutboundHttpClient,
) -> SeoSummary:
    page = await client.fetch(raw_url, max_body_bytes=MAX_RESPONSE_BYTES)
    root = urlsplit(page.final_url)
    robots_url = f"{root.scheme}://{root.netloc}/robots.txt"
    robots_available = False
    root_disallowed = False
    try:
        robots = await client.fetch(robots_url, max_body_bytes=256 * 1024)
        robots_available = robots.status == 200
        if robots_available:
            root_disallowed = _robots_root_disallowed(
                robots.body.decode("utf-8", errors="ignore")
            )
    except WebsiteMonitoringError:
        pass

    xrobots = page.headers.get("x-robots-tag", "").lower()
    return SeoSummary(
        robots_txt_available=robots_available,
        root_disallowed=root_disallowed,
        meta_noindex=_meta_noindex(page.body),
        header_noindex="noindex" in xrobots,
    )


def format_url_list(raw: str) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for line in (raw or "").splitlines():
        value = line.strip()
        if not value:
            continue
        try:
            canonical = canonicalize_public_url(value)
        except Exception:
            continue
        if canonical in seen:
            continue
        seen.add(canonical)
        result.append(canonical)
        if len(result) >= MAX_SITEMAP_URLS:
            break
    return tuple(result)


def _xml_locations(body: bytes) -> tuple[str, tuple[str, ...]]:
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        raise WebsiteDiagnosticsError("Некорректный sitemap XML.", code="invalid_sitemap") from exc
    name = root.tag.rsplit("}", 1)[-1].lower()
    locations: list[str] = []
    for node in root.iter():
        if node.tag.rsplit("}", 1)[-1].lower() == "loc" and node.text:
            locations.append(node.text.strip())
    return name, tuple(locations)


async def sitemap_urls(
    raw_url: str,
    client: SafeOutboundHttpClient,
) -> tuple[str, ...]:
    canonical = canonicalize_public_url(raw_url)
    if not urlsplit(canonical).path.lower().endswith(".xml"):
        root = urlsplit(canonical)
        canonical = f"{root.scheme}://{root.netloc}/sitemap.xml"

    queue = [canonical]
    seen_docs: set[str] = set()
    urls: list[str] = []
    seen_urls: set[str] = set()

    while queue and len(seen_docs) < MAX_SITEMAP_DOCUMENTS:
        current = canonicalize_public_url(queue.pop(0))
        if current in seen_docs:
            continue
        seen_docs.add(current)
        response = await client.fetch(current, max_body_bytes=MAX_SITEMAP_BYTES)
        if response.status != 200:
            raise WebsiteDiagnosticsError(
                f"Sitemap вернул HTTP {response.status}.",
                code="sitemap_unavailable",
            )
        kind, locations = _xml_locations(response.body)
        if kind == "sitemapindex":
            for location in locations:
                if len(seen_docs) + len(queue) >= MAX_SITEMAP_DOCUMENTS:
                    break
                queue.append(canonicalize_public_url(urljoin(response.final_url, location)))
            continue
        for location in locations:
            try:
                value = canonicalize_public_url(urljoin(response.final_url, location))
            except Exception:
                continue
            if value in seen_urls:
                continue
            seen_urls.add(value)
            urls.append(value)
            if len(urls) >= MAX_SITEMAP_URLS:
                return tuple(urls)
    return tuple(urls)


def qr_png(value: str) -> bytes:
    text = (value or "").strip()
    if not text or len(text) > 2048:
        raise WebsiteDiagnosticsError("QR input должен содержать 1–2048 символов.", code="invalid_qr")
    image = qrcode.make(text)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


async def pagespeed_summary(
    raw_url: str,
    client: SafeOutboundHttpClient,
    *,
    api_key: str,
) -> PageSpeedSummary:
    key = (api_key or "").strip()
    if not key:
        return PageSpeedSummary(enabled=False, performance_score=None, category="")
    target = canonicalize_public_url(raw_url)
    endpoint = (
        "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
        f"?url={quote(target, safe='')}"
        f"&key={quote(key, safe='')}"
        "&category=performance"
        "&fields=lighthouseResult/categories/performance/score,loadingExperience/overall_category"
    )
    response = await client.fetch(endpoint, max_body_bytes=MAX_RESPONSE_BYTES)
    if response.status != 200:
        raise WebsiteDiagnosticsError(
            f"PageSpeed вернул HTTP {response.status}.",
            code="pagespeed_unavailable",
        )
    try:
        payload = json.loads(response.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WebsiteDiagnosticsError("Некорректный PageSpeed response.", code="invalid_response") from exc
    performance = payload.get("lighthouseResult", {}).get("categories", {}).get("performance", {})
    raw_score = performance.get("score") if isinstance(performance, dict) else None
    score = None
    if isinstance(raw_score, (int, float)):
        score = max(0, min(100, round(float(raw_score) * 100)))
    loading = payload.get("loadingExperience")
    category = str(loading.get("overall_category") or "") if isinstance(loading, dict) else ""
    return PageSpeedSummary(enabled=True, performance_score=score, category=category)
