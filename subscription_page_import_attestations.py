"""#887 D3h: проверка offline evidence для client/version Copy/QR.

Реестр не подключён к app_runtime и не включает выдачу URL.
Прошлые результаты #473 — только кандидаты, не D3h аттестация.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from subscription_page_import_issuer import ReviewedImportClient

MANIFEST_PATH = "docs/assets/subpage-d3h-client-attestations.json"
_KEYS = frozenset(("platform", "clientId", "clientVersion"))
_CANDIDATE = _KEYS | {"priorIssue"}
_REVIEWED = _KEYS | {"reviewIssue", "allowCopy", "allowQr", "evidence"}
_PROOF = frozenset((
    "auditPath", "buildSha", "testedAt", "deviceModel", "osVersion",
    "clientVersion", "clientBuild", "browserVersion", "telegramVersion", "native",
    "webview", "privacy",
))
_VERSION = re.compile(r"[0-9]+(?:\.[0-9]+){1,3}(?:[-+][a-z0-9._-]+)?\Z")
_ID = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}\Z")
_SHA = re.compile(r"[0-9a-f]{40}\Z")
_AUDIT = re.compile(r"docs/audits/[0-9]{4}-[0-9]{2}-[0-9]{2}-[a-z0-9-]+\.md\Z")
_STATES = frozenset({"PASS", "PENDING", "FAIL", "BLOCKED"})


def _valid_string(value: object) -> bool:
    return (type(value) is str and 1 <= len(value) <= 96
            and value == value.strip()
            and all(0x20 <= ord(char) <= 0x7e for char in value))


def _key(record: object, *, candidate: bool) -> tuple[str, str, str | None]:
    required = _CANDIDATE if candidate else _REVIEWED
    if type(record) is not dict or set(record) != required:
        raise ValueError("Некорректная запись D3h")
    platform, client, version = (record[name] for name in _KEY_ORDER)
    if (platform not in ("ios", "android") or not isinstance(client, str)
            or not _ID.fullmatch(client)
            or (version is None and not candidate)
            or (version is not None and
                (not isinstance(version, str) or not _VERSION.fullmatch(version)))):
        raise ValueError("Неподтверждённая client/platform/version")
    return platform, client, version


_KEY_ORDER = ("platform", "clientId", "clientVersion")


def _outcome(value: object, *, required: bool) -> None:
    if (type(value) is not dict or set(value) != {"copy", "qr"}
            or any(type(status) is not str or status not in _STATES
                   for status in value.values())):
        raise ValueError("Некорректный результат Copy/QR")
    if required and value["copy"] != "PASS" and value["qr"] != "PASS":
        raise ValueError("Нет проверенного метода")


def _evidence(evidence: object, *, root: Path, version: str,
              copy: bool, qr: bool) -> None:
    if type(evidence) is not dict or set(evidence) != _PROOF:
        raise ValueError("Не хватает полей device evidence")
    for field in ("deviceModel", "osVersion", "clientBuild",
                  "browserVersion", "telegramVersion"):
        if not _valid_string(evidence[field]):
            raise ValueError("Нет точной версии/физического устройства")
    if evidence["clientVersion"] != version:
        raise ValueError("Версия в аттестации не совпадает")
    if not isinstance(evidence["buildSha"], str) or not _SHA.fullmatch(evidence["buildSha"]):
        raise ValueError("Нет immutable build SHA")
    if not isinstance(evidence["testedAt"], str):
        raise ValueError("Нет даты проверки")
    try:
        tested_at = datetime.fromisoformat(evidence["testedAt"].replace("Z", "+00:00"))
        if tested_at.tzinfo is None or tested_at.utcoffset() is None:
            raise ValueError()
    except ValueError:
        raise ValueError("Требуется дата с часовым поясом") from None
    if not isinstance(evidence["auditPath"], str) or not _AUDIT.fullmatch(evidence["auditPath"]):
        raise ValueError("Требуется канонический dated audit")
    for context in ("native", "webview"):
        _outcome(evidence[context], required=True)
        if ((copy and evidence[context]["copy"] != "PASS") or
                (qr and evidence[context]["qr"] != "PASS")):
            raise ValueError("Не завершён physical device/WebView smoke")
    privacy = evidence["privacy"]
    if (type(privacy) is not dict
            or set(privacy) != {"ownerDenied", "replayDenied", "cacheNoStore", "logsRedacted"}
            or any(status != "PASS" for status in privacy.values())):
        raise ValueError("Не завершены privacy/ownership проверки")
    # Структурная проверка ссылок — не независимая аттестация устройства.
    # Ревьюер отдельно проверяет источник и подлинность обезличенного evidence.
    try:
        audit = (root / evidence["auditPath"]).read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        raise ValueError("Нет доступного датированного audit") from None
    if ("<!-- audit-schema: 1 -->" not in audit
            or "#887" not in audit or evidence["buildSha"] not in audit):
        raise ValueError("D3h audit не связан с проверенным build SHA")


def reviewed_clients_from_manifest(document: object, *, root: Path) -> tuple[ReviewedImportClient, ...]:
    """Компилирует *только* явно reviewed записи, без повышения кандидатов.

    Это offline API для будущего security review. Factory HTTP по-прежнему
    delivery_enabled=False, reviewed_clients=(), UI allowlist=[].
    """
    if (type(document) is not dict or set(document) != {"schema", "issue", "candidates", "reviewed"}
            or type(document["schema"]) is not int or document["schema"] != 1
            or document["issue"] != "#887"
            or type(document["candidates"]) is not list
            or type(document["reviewed"]) is not list):
        raise ValueError("Некорректный контракт D3h")
    candidates: set[tuple[str, str, str | None]] = set()
    for item in document["candidates"]:
        key = _key(item, candidate=True)
        if item["priorIssue"] != "#473" or key in candidates:
            raise ValueError("Дубли или неподтверждённое происхождение кандидата")
        candidates.add(key)
    approved: set[tuple[str, str, str | None]] = set()
    result: list[ReviewedImportClient] = []
    for item in document["reviewed"]:
        key = _key(item, candidate=False)
        copy, qr = item["allowCopy"], item["allowQr"]
        if (key not in candidates or key in approved or item["reviewIssue"] != "#887"
                or type(copy) is not bool or type(qr) is not bool or not (copy or qr)):
            raise ValueError("Отказ в повышении client/version")
        _evidence(item["evidence"], root=root, version=key[2], copy=copy, qr=qr)
        approved.add(key)
        result.append(ReviewedImportClient(key[0], key[1], key[2], "#887", copy, qr))
    return tuple(result)


def load_reviewed_clients(*, root: Path) -> tuple[ReviewedImportClient, ...]:
    """Read-only offline intake; не используется при создании runtime app."""
    try:
        data = json.loads((root / MANIFEST_PATH).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        raise ValueError("Реестр D3h недоступен") from None
    return reviewed_clients_from_manifest(data, root=root)

# D3h: read-only source preflight. No network, Telegram, HTTP, QR or secrets.
_STAGING_LOCATIONS = frozenset({
    "= /",
    "^~ /assets/",
    "= /api/subpage/v1/auth/standalone/start",
    "= /api/subpage/v1/auth/standalone/complete",
    "~ ^/api/subpage/v1/(auth/standalone/(cancel|logout)|standalone/me)$",
    "/",
})


def _read_contract(root: Path, relative: str) -> str:
    try:
        return (root / relative).read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        raise ValueError("D3h: недоступен source contract") from None


def inspect_d3h_staging_readiness(*, root: Path) -> dict[str, object]:
    """Fail-closed offline source readiness, not a physical device attestation.

    No PASS is inferred from matching metadata; human verification is required.
    On unexpected activation or ingress change: fail instead of running probes.
    """
    approved = load_reviewed_clients(root=root)
    try:
        manifest = json.loads(_read_contract(root, MANIFEST_PATH))
    except (ValueError, TypeError):
        raise ValueError("D3h: реестр недоступен") from None
    frontend = _read_contract(root, "web/subscription-page/src/main.tsx")
    reviewed = _read_contract(root, "web/subscription-page/src/reviewedCapabilities.ts")
    issuer = _read_contract(root, "subscription_page_import_http.py")
    staging = _read_contract(root, "subscription_page_staging.py")
    wiring = _read_contract(root, "subscription_page_pilot_wiring.py")
    runtime = _read_contract(root, "app_runtime.py")
    ingress = _read_contract(root, "deploy/subpage-staging/nginx-d2d-staging.conf.example")

    if (not all(s in frontend for s in (
            'VITE_D3G_MANUAL_IMPORT_UI === "true"',
            'clientVersion=""',
            "pilotEnabled={false}",
        )) or "Object.freeze([])" not in reviewed
            or "delivery_enabled: bool = False" not in issuer
            or "reviewed_clients: tuple[ReviewedImportClient, ...] = ()" not in issuer
            or "subscription_page_import_http" in staging
            or "create_import_preflight_app" in wiring
            or "subscription_page_import_http" in runtime
            or "subscription_page_import_attestations" in runtime):
        raise ValueError("D3h: flags/wiring изменены без отдельного security review")

    locations = re.findall(r"(?m)^\s*location\s+(.+?)\s*\{", ingress)
    # Existing D2d edge offers only standalone auth, assets, and default 404.
    # It cannot transport D3g /import/preflight/{csrf,issue,deliver}.
    if (len(locations) != len(_STAGING_LOCATIONS)
            or set(locations) != _STAGING_LOCATIONS
            or not re.search(r"location /\s*\{\s*return 404;", ingress)):
        raise ValueError("D3h: ingress изменён без отдельного security review")

    return {
        "schema": 1,
        "scope": "D3h",
        "status": "BLOCKED",
        "candidate_count": len(manifest["candidates"]),
        "reviewed_count": len(approved),
        "device_evidence": "PENDING" if not approved else "INDEPENDENT_REVIEW_REQUIRED",
        "staging_import_routes": "NOT_WIRED",
        "frontend_import": "OFF",
        "server_delivery": "OFF",
        "live_requests_sent": 0,
        "next_gate": "isolated_staging_review_and_physical_device_smoke",
    }


def _offline_main() -> int:
    import sys
    # No credentials, hostnames or private config paths may be passed to CLI.
    if sys.argv[1:] != ["--offline-readiness"]:
        print("Использование: python subscription_page_import_attestations.py --offline-readiness")
        return 2
    try:
        report = inspect_d3h_staging_readiness(root=Path(__file__).resolve().parent)
    except ValueError:
        print(json.dumps({
            "scope": "D3h", "status": "BLOCKED",
            "reason": "repository_security_review_required",
        }, sort_keys=True))
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(_offline_main())
