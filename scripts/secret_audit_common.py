from __future__ import annotations

import hashlib
import re
from pathlib import PurePosixPath


_PLACEHOLDER = re.compile(
    r"(?i)(example|sample|dummy|placeholder|changeme|change-me|your[-_ ]|replace[-_ ]|"
    r"not[-_ ]a[-_ ]real|fake|test[-_ ]only|redacted|<[^>]+>|\*{3,})"
)

_PRIVATE_IPV4 = re.compile(
    r"(?<!\d)(?:10\.(?:\d{1,3}\.){2}\d{1,3}|"
    r"192\.168\.(?:\d{1,3}\.)\d{1,3}|"
    r"172\.(?:1[6-9]|2\d|3[01])\.(?:\d{1,3}\.)\d{1,3})(?!\d)"
)

_TELEGRAM_ID = re.compile(
    r"(?i)\b(?:telegram(?:_user)?_id|telegram_id|admin_telegram_ids?|tg_id)\b"
    r"[^\n]{0,32}?(-?\d{5,15})"
)

_PRIVATE_ENDPOINT = re.compile(
    r"(?i)\b(?:xui_base_url|host_control_url|deploy_agent_url|public_base_url|"
    r"subscription_url|private_host|private_hostname|domain|hostname)\b"
    r"\s*[:=]\s*[\"']?([^\s\"']+)"
)

_HIGH_CONFIDENCE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "private-key",
        re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
    ),
    (
        "github-token",
        re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
    ),
    (
        "telegram-bot-token",
        re.compile(r"\b\d{8,12}:[A-Za-z0-9_-]{30,}\b"),
    ),
    (
        "aws-access-key",
        re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    ),
    (
        "jwt",
        re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
    ),
    (
        "url-credentials",
        re.compile(r"\b[a-zA-Z][a-zA-Z0-9+.-]*://[^/\s:@]+:[^/\s@]{4,}@"),
    ),
    (
        "generic-secret-assignment",
        re.compile(
            r"(?i)\b(?:token|secret|password|passwd|api[_-]?key|auth[_-]?key|private[_-]?key)"
            r"\b\s*[:=]\s*[\"']?([A-Za-z0-9+/_=:@.-]{16,})"
        ),
    ),
)


def fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()[:16]


def looks_placeholder(value: str) -> bool:
    return bool(_PLACEHOLDER.search(value))


def scan_high_confidence(text: str):
    for detector, pattern in _HIGH_CONFIDENCE_PATTERNS:
        for match in pattern.finditer(text):
            value = match.group(1) if match.lastindex else match.group(0)
            if looks_placeholder(value):
                continue
            yield detector, fingerprint(value)


def scan_sensitive_metadata(text: str):
    for match in _PRIVATE_IPV4.finditer(text):
        value = match.group(0)
        yield "private-ipv4", fingerprint(value)

    for match in _TELEGRAM_ID.finditer(text):
        value = match.group(1)
        if looks_placeholder(value):
            continue
        yield "telegram-id", fingerprint(value)

    for match in _PRIVATE_ENDPOINT.finditer(text):
        value = match.group(1).rstrip(",);")
        if looks_placeholder(value):
            continue
        if value.startswith(("http://127.0.0.1", "https://127.0.0.1", "http://localhost", "https://localhost")):
            continue
        yield "private-endpoint-candidate", fingerprint(value)


def sensitive_path_reason(path: str) -> str | None:
    normalized = path.replace("\\", "/")
    p = PurePosixPath(normalized)
    name = p.name.lower()
    suffixes = "".join(p.suffixes).lower()

    if name == ".env":
        return "env-file"
    if name in {"id_rsa", "id_ed25519", "credentials.json", "secrets.json", "service-account.json"}:
        return "credential-file"
    if p.suffix.lower() in {".pem", ".key", ".p12", ".pfx", ".jks", ".keystore", ".kdbx", ".db", ".sqlite", ".sqlite3"}:
        return "sensitive-file"
    if "backup" in name and suffixes.endswith((".tar", ".tar.gz", ".tgz", ".zip", ".7z")):
        return "backup-archive"
    if "enrollment" in name and p.suffix.lower() not in {".py", ".md"}:
        return "enrollment-artifact"
    return None
