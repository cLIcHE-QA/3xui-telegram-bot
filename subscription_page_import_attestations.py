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

# D3j: D3h + D3i offline integration check.
# Every check reads only repository sources, never network, Bot API, URL or device.
# The result is always BLOCKED until independent staging and physical acceptance.
_D2D_LOCATIONS = frozenset({
    "= /",
    "^~ /assets/",
    "= /api/subpage/v1/auth/standalone/start",
    "= /api/subpage/v1/auth/standalone/complete",
    "~ ^/api/subpage/v1/(auth/standalone/(cancel|logout)|standalone/me)$",
    "/",
})
_D3I_LOCATIONS = _D2D_LOCATIONS | frozenset({
    "= /api/subpage/v1/import/preflight/csrf",
    "= /api/subpage/v1/import/preflight/issue",
    "= /api/subpage/v1/import/preflight/consume",
    "= /api/subpage/v1/import/preflight/deliver",
})


def _read_contract(root: Path, relative: str) -> str:
    try:
        return (root / relative).read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        raise ValueError("D3j: недоступен обязательный source contract") from None


def _check_locations(ingress: str, expected: frozenset[str]) -> bool:
    locations = re.findall(r"(?m)^\s*location\s+(.+?)\s*\{", ingress)
    return (len(locations) == len(expected) and set(locations) == expected
            and re.search(r"location /\s*\{\s*return 404;", ingress) is not None)


def inspect_d3h_staging_readiness(*, root: Path) -> dict[str, object]:
    """Offline-only D3j contract gate; never a staging or device PASS.

    Structural checks detect known safety regressions but cannot prove that
    source, TLS ingress, client hardware, owners or manual evidence are genuine.
    Even an approved-looking manifest does not activate any runtime allowlist.
    """
    approved = load_reviewed_clients(root=root)
    try:
        manifest = json.loads(_read_contract(root, MANIFEST_PATH))
    except (ValueError, TypeError):
        raise ValueError("D3j: недоступен реестр кандидатов") from None

    frontend = _read_contract(root, "web/subscription-page/src/main.tsx")
    manual = _read_contract(root, "web/subscription-page/src/manualImportClient.ts")
    panel = _read_contract(root, "web/subscription-page/src/ManualImportPanel.tsx")
    reviewed = _read_contract(root, "web/subscription-page/src/reviewedCapabilities.ts")
    issuer = _read_contract(root, "subscription_page_import_http.py")
    isolated = _read_contract(root, "subscription_page_import_staging.py")
    standalone = _read_contract(root, "subscription_page_staging.py")
    wiring = _read_contract(root, "subscription_page_pilot_wiring.py")
    runtime = _read_contract(root, "app_runtime.py")
    d2d_edge = _read_contract(root, "deploy/subpage-staging/nginx-d2d-staging.conf.example")
    d3i_edge = _read_contract(root, "deploy/subpage-staging/nginx-d3i-import-staging.conf.example")

    # Shipping frontend and runtime remain inactive, independently of manifest.
    if (not all(token in frontend for token in (
            'VITE_D3G_MANUAL_IMPORT_UI === "true"',
            'clientVersion=""', "pilotEnabled={false}",
        )) or "Object.freeze([])" not in reviewed
            or "delivery_enabled: bool = False" not in issuer
            or "reviewed_clients: tuple[ReviewedImportClient, ...] = ()" not in issuer
            or "subscription_page_import_http" in standalone
            or "subscription_page_import_staging" in standalone
            or "create_import_preflight_app" in wiring
            or any(token in runtime for token in (
                "subscription_page_import_http",
                "subscription_page_import_attestations",
                "subscription_page_import_staging",
            ))):
        raise ValueError("D3j: shipping default-off / runtime isolation нарушены")

    # D3i browser fix: read-only GET may omit Origin, but explicit foreign
    # Origin is denied; every mutating POST still requires exact Origin + CSRF.
    if not all(token in issuer for token in (
        'origin = request.headers.get("Origin")',
        'if (origin is not None and origin != https_origin) or (mutate and origin != https_origin):',
        'site not in ("same-origin", "none")',
        'guard_csrf(request, mode, cookie)',
        'if not enabled or not delivery_enabled:',
    )):
        raise ValueError("D3j: Origin/CSRF/delivery guard требует review")

    # ClipboardItem is queued synchronously inside a trusted click and a
    # Promise<Blob> is resolved only after successful owner-bound HTTP.
    # No writeText after network, no custom scheme handoff in WebView.
    if (not all(token in manual for token in (
            'method: "GET"', 'BASE + "/csrf"',
            'referrerPolicy: "no-referrer"',
            'export async function copyManualImportOnGesture(',
            'writing = enqueue(content);',
            'const result = await requestManualImport(',
            'if (!stillCurrent() || result.method !== "copy")',
        )) or not all(token in panel for token in (
            'await copyManualImportOnGesture(',
            'navigator.clipboard.write([new ClipboardItem({"text/plain": content})])',
            'requestEpoch.current',
            'await requestManualImport(',
            'URL.createObjectURL',
            'URL.revokeObjectURL',
        )) or 'navigator.clipboard.writeText' in panel):
        raise ValueError("D3j: Clipboard/QR source safety требует review")

    # D3i is a source-only factory with a separate, private single-host ledger
    # and synthetic service. No trusted reviewed clients or bearer routes.
    if not all(token in isolated for token in (
            'preflight_enabled: bool = False',
            'type(pilot.service) is not _SyntheticCustomer',
            'type(pilot.flags) is not _SyntheticFlags',
            'pilot.service.owners != pilot.pilot_ids',
            'pilot.ledger is None',
            'target.name != _LEDGER or target.parent != pilot.ledger.path.parent',
            'enabled=preflight_enabled, now=pilot.now',
            'delivery_enabled=False, subscription_origin=None',
            'reviewed_clients=()',
            '_LOOPBACK = "127.0.0.1"',
            'host != _LOOPBACK',
            'explicitly_enabled is not True',
        )) or "load_reviewed_clients(" in isolated
            or "reviewed_clients=approved" in isolated):
        raise ValueError("D3j: staging synthetic/no-delivery boundary нарушена")

    # Old D2d ingress stays unchanged: no import routes or blob QR CSP.
    if (not _check_locations(d2d_edge, _D2D_LOCATIONS)
            or "img-src 'self' data:;" not in d2d_edge):
        raise ValueError("D3j: D2d ingress изменён без независимого review")

    # New D3i ingress is TEMPLATE ONLY. Exact path/method allowlisting, no
    # catch-all proxy; /deliver is denied on the edge even if misconfigured.
    if (not _check_locations(d3i_edge, _D3I_LOCATIONS)
            or "img-src 'self' data: blob:;" not in d3i_edge
            or "access_log off;" not in d3i_edge
            or "client_max_body_size 2k;" not in d3i_edge
            or 'if ($ssl_server_name != "staging.example.invalid")' not in d3i_edge
            or not re.search(
                r"location = /api/subpage/v1/import/preflight/deliver\s*\{\s*return 404;\s*\}",
                d3i_edge)
            or d3i_edge.count('if ($request_method != GET) { return 405; }') != 1
            or d3i_edge.count('if ($request_method != POST) { return 405; }') != 2
            or d3i_edge.count("proxy_pass http://127.0.0.1:8828;") != 3):
        raise ValueError("D3j: D3i ingress deny/allowlist требует review")

    return {
        "schema": 1,
        "scope": "D3j",
        "status": "BLOCKED",
        "candidate_count": len(manifest["candidates"]),
        "reviewed_count": len(approved),
        "device_evidence": "PENDING" if not approved else "INDEPENDENT_REVIEW_REQUIRED",
        "staging_import_routes": "TEMPLATE_ONLY_NO_RUNTIME",
        "csrf_origin_compat": "SOURCE_GUARDED_DEVICE_PENDING",
        "qr_blob_csp": "TEMPLATE_ONLY_DEVICE_PENDING",
        "clipboard_activation": "SOURCE_GUARDED_DEVICE_PENDING",
        "frontend_import": "OFF",
        "server_delivery": "OFF",
        "staging_delivery": "DENIED",
        "live_requests_sent": 0,
        "next_gate": "independent_staging_security_and_physical_device_review",
    }


def _offline_main() -> int:
    import sys
    # Never accept hostnames, bearer tokens, device IDs or secret file paths.
    if sys.argv[1:] != ["--offline-readiness"]:
        print("Использование: python subscription_page_import_attestations.py --offline-readiness")
        return 2
    try:
        report = inspect_d3h_staging_readiness(root=Path(__file__).resolve().parent)
    except ValueError:
        print(json.dumps({
            "scope": "D3j", "status": "BLOCKED",
            "reason": "repository_security_review_required",
        }, sort_keys=True))
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(_offline_main())
