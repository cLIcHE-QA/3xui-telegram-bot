from __future__ import annotations

import asyncio
from dataclasses import dataclass
import ipaddress
import json
import re
from typing import Any

import aiohttp


MAX_TARGET_LENGTH = 255
MAX_RESPONSE_BYTES = 1024 * 1024
MAX_CONCURRENCY = 4
_DOMAIN_LABEL_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$", re.IGNORECASE)


class CheburcheckError(RuntimeError):
    def __init__(self, message: str, *, code: str = "error") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ComplaintDay:
    date: str
    count: int


@dataclass(frozen=True)
class CheburcheckResult:
    target: str
    target_type: str
    blocked: bool
    ips: tuple[str, ...]
    reverse_lookup: tuple[str, ...]
    blocked_subnets: tuple[str, ...]
    location: str
    asn: str
    organisation: str
    rkn_domain: str
    subnet_size: str
    complaints: tuple[ComplaintDay, ...]


def normalize_target(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        raise CheburcheckError("Введи домен, IP-адрес, подсеть или ASN.", code="invalid_target")
    if len(raw) > MAX_TARGET_LENGTH:
        raise CheburcheckError("Цель слишком длинная.", code="invalid_target")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in raw):
        raise CheburcheckError("Цель содержит недопустимые управляющие символы.", code="invalid_target")
    if "://" in raw:
        raise CheburcheckError("Введи домен без http:// или https://.", code="invalid_target")

    upper = raw.upper()
    if upper.startswith("AS") and upper[2:].isdigit():
        asn = int(upper[2:])
        if not 1 <= asn <= 4_294_967_295:
            raise CheburcheckError("ASN должен быть в диапазоне AS1..AS4294967295.", code="invalid_target")
        return f"AS{asn}"

    if "/" in raw:
        try:
            network = ipaddress.ip_network(raw, strict=False)
        except ValueError as exc:
            raise CheburcheckError("Некорректная IP-подсеть.", code="invalid_target") from exc
        if network.version == 4 and network.prefixlen < 8:
            raise CheburcheckError("IPv4-подсеть должна быть не шире /8.", code="invalid_target")
        if network.version == 6 and network.prefixlen < 32:
            raise CheburcheckError("IPv6-подсеть должна быть не шире /32.", code="invalid_target")
        if not network.network_address.is_global:
            raise CheburcheckError("Разрешены только публичные IP-подсети.", code="invalid_target")
        return str(network)

    try:
        address = ipaddress.ip_address(raw)
    except ValueError:
        address = None
    if address is not None:
        if not address.is_global:
            raise CheburcheckError("Разрешены только публичные IP-адреса.", code="invalid_target")
        return str(address)

    domain = raw.rstrip(".").lower()
    try:
        ascii_domain = domain.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise CheburcheckError("Некорректное доменное имя.", code="invalid_target") from exc
    if len(ascii_domain) > 253 or "." not in ascii_domain:
        raise CheburcheckError("Введи полное доменное имя.", code="invalid_target")
    labels = ascii_domain.split(".")
    if any(not label or not _DOMAIN_LABEL_RE.fullmatch(label) for label in labels):
        raise CheburcheckError("Некорректное доменное имя.", code="invalid_target")
    return ascii_domain


def _str_list(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value if isinstance(item, (str, int, float)))


def parse_response(data: dict[str, Any]) -> CheburcheckResult:
    if not isinstance(data, dict):
        raise CheburcheckError("Cheburcheck вернул некорректный ответ.", code="invalid_response")
    if "target" not in data or "target_type" not in data or "blocked" not in data:
        raise CheburcheckError("Cheburcheck вернул неполный ответ.", code="invalid_response")

    geo = data.get("geo") if isinstance(data.get("geo"), dict) else {}
    complaints_raw = data.get("complaints") if isinstance(data.get("complaints"), list) else []
    complaints: list[ComplaintDay] = []
    for item in complaints_raw[:14]:
        if not isinstance(item, dict):
            continue
        date = str(item.get("date") or "")
        try:
            count = max(0, int(item.get("count") or 0))
        except (TypeError, ValueError):
            count = 0
        if date:
            complaints.append(ComplaintDay(date=date, count=count))

    return CheburcheckResult(
        target=str(data.get("target") or ""),
        target_type=str(data.get("target_type") or ""),
        blocked=bool(data.get("blocked")),
        ips=_str_list(data.get("ips")),
        reverse_lookup=_str_list(data.get("reverse_lookup")),
        blocked_subnets=_str_list(data.get("blocked_subnets")),
        location=str(geo.get("location") or ""),
        asn=str(geo.get("asn") or ""),
        organisation=str(geo.get("organisation") or ""),
        rkn_domain=str(data.get("rkn_domain") or ""),
        subnet_size=str(data.get("subnet_size") or ""),
        complaints=tuple(complaints),
    )


class CheburcheckClient:
    def __init__(
        self,
        base_url: str,
        *,
        verify_tls: bool = True,
        max_concurrency: int = MAX_CONCURRENCY,
    ) -> None:
        self.base_url = (base_url or "").strip().rstrip("/")
        self.verify_tls = bool(verify_tls)
        self._semaphore = asyncio.Semaphore(max(1, int(max_concurrency)))

    @property
    def enabled(self) -> bool:
        return bool(self.base_url)

    async def check(self, target: str) -> CheburcheckResult:
        if not self.enabled:
            raise CheburcheckError("Cheburcheck не настроен.", code="disabled")
        normalized = normalize_target(target)
        timeout = aiohttp.ClientTimeout(total=10, connect=3, sock_read=7)
        async with self._semaphore:
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(
                        f"{self.base_url}/api/v1/check",
                        params={"target": normalized},
                        headers={"Accept": "application/json"},
                        ssl=None if self.verify_tls else False,
                        allow_redirects=False,
                    ) as response:
                        if response.status == 429:
                            raise CheburcheckError(
                                "Cheburcheck временно ограничил частоту запросов.",
                                code="rate_limited",
                            )
                        if response.status == 404:
                            raise CheburcheckError(
                                "Цель не найдена в источниках Cheburcheck.",
                                code="not_found",
                            )
                        if response.status in {400, 403}:
                            raise CheburcheckError(
                                "Cheburcheck отклонил эту цель.",
                                code="rejected",
                            )
                        if response.status >= 500:
                            raise CheburcheckError(
                                "Сервис Cheburcheck временно недоступен.",
                                code="unavailable",
                            )
                        if response.status != 200:
                            raise CheburcheckError(
                                f"Cheburcheck вернул HTTP {response.status}.",
                                code="upstream_error",
                            )
                        if response.content_length is not None and response.content_length > MAX_RESPONSE_BYTES:
                            raise CheburcheckError(
                                "Ответ Cheburcheck превышает допустимый размер.",
                                code="response_too_large",
                            )
                        body = bytearray()
                        async for chunk in response.content.iter_chunked(16 * 1024):
                            body.extend(chunk)
                            if len(body) > MAX_RESPONSE_BYTES:
                                raise CheburcheckError(
                                    "Ответ Cheburcheck превышает допустимый размер.",
                                    code="response_too_large",
                                )
            except CheburcheckError:
                raise
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                raise CheburcheckError(
                    "Не удалось связаться с сервисом Cheburcheck.",
                    code="unavailable",
                ) from exc

        try:
            data = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CheburcheckError("Cheburcheck вернул некорректный JSON.", code="invalid_response") from exc
        return parse_response(data)
