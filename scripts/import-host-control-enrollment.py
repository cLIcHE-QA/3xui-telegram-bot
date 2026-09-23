#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ipaddress
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

ALIAS_RE = re.compile(r"^[A-Z0-9][A-Z0-9_]{0,31}$")
HOST_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")
ENROLLMENT_KEYS = {
    "HOST_CONTROL_ALIAS",
    "HOST_CONTROL_NAME",
    "HOST_CONTROL_HOST_ID",
    "HOST_CONTROL_URL",
    "HOST_CONTROL_VERIFY_TLS",
    "HOST_CONTROL_TOKEN",
}


def fail(message: str) -> "NoReturn":
    raise SystemExit(f"ERROR: {message}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Safely import a Host Control enrollment file into bot .env without printing secrets."
    )
    parser.add_argument("enrollment", type=Path)
    parser.add_argument("--env", dest="env_path", type=Path, default=Path(".env"))
    parser.add_argument("--node-id", type=int, default=None)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--recreate-bot", action="store_true")
    parser.add_argument("--project", default="3xui-telegram-bot")
    parser.add_argument("--service", default="bot")
    parser.add_argument("--health-url", default="http://127.0.0.1:18080/healthz")
    return parser.parse_args()


def parse_simple_env(path: Path, *, allowed: set[str] | None = None) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        fail(f"cannot read {path}: {exc}")
    for lineno, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in raw:
            fail(f"{path}:{lineno}: expected KEY=VALUE")
        key, value = raw.split("=", 1)
        key = key.strip()
        if not key:
            fail(f"{path}:{lineno}: empty key")
        if allowed is not None and key not in allowed:
            fail(f"{path}:{lineno}: unexpected key {key}")
        if key in values:
            fail(f"{path}:{lineno}: duplicate key {key}")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def is_private_host(hostname: str) -> bool:
    value = (hostname or "").strip().lower()
    if value == "localhost":
        return True
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    return any(
        address in network
        for network in (
            ipaddress.ip_network("127.0.0.0/8"),
            ipaddress.ip_network("10.0.0.0/8"),
            ipaddress.ip_network("172.16.0.0/12"),
            ipaddress.ip_network("192.168.0.0/16"),
            ipaddress.ip_network("169.254.0.0/16"),
            ipaddress.ip_network("::1/128"),
            ipaddress.ip_network("fc00::/7"),
            ipaddress.ip_network("fe80::/10"),
        )
    )


def validate_target(alias: str, name: str, host_id: str, url: str, token: str, verify_tls: str) -> None:
    if not ALIAS_RE.fullmatch(alias):
        fail(f"invalid alias {alias!r}")
    if not (1 <= len(name) <= 64) or "\n" in name or "\r" in name:
        fail(f"invalid target name for {alias}")
    if not HOST_ID_RE.fullmatch(host_id):
        fail(f"invalid host_id for {alias}")
    if len(token) < 43:
        fail(f"token for {alias} is too short")
    if verify_tls.strip().lower() not in {"1", "true", "yes", "on"}:
        fail(f"VERIFY_TLS must be true for {alias}")

    parsed = urlsplit(url.rstrip("/"))
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        fail(f"URL for {alias} must be absolute http(s)")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        fail(f"URL for {alias} must not contain credentials, query or fragment")
    if parsed.scheme == "http":
        if alias != "MASTER" or not is_private_host(parsed.hostname):
            fail("plain HTTP is allowed only for private/local MASTER")


def enrollment_to_updates(enrollment: dict[str, str]) -> tuple[str, dict[str, str]]:
    missing = sorted(ENROLLMENT_KEYS - enrollment.keys())
    if missing:
        fail("enrollment is incomplete: " + ", ".join(missing))

    alias = enrollment["HOST_CONTROL_ALIAS"].strip().upper()
    name = enrollment["HOST_CONTROL_NAME"].strip()
    host_id = enrollment["HOST_CONTROL_HOST_ID"].strip().lower()
    url = enrollment["HOST_CONTROL_URL"].strip().rstrip("/")
    verify_tls = enrollment["HOST_CONTROL_VERIFY_TLS"].strip()
    token = enrollment["HOST_CONTROL_TOKEN"].strip()
    validate_target(alias, name, host_id, url, token, verify_tls)

    prefix = f"HOST_CONTROL_{alias}_"
    return alias, {
        prefix + "NAME": name,
        prefix + "HOST_ID": host_id,
        prefix + "URL": url,
        prefix + "VERIFY_TLS": "true",
        prefix + "TOKEN": token,
    }


def active_aliases(env: dict[str, str], new_alias: str) -> list[str]:
    aliases: list[str] = []
    for raw in env.get("HOST_CONTROL_TARGETS", "").split(","):
        alias = raw.strip().upper()
        if not alias:
            continue
        if not ALIAS_RE.fullmatch(alias):
            fail(f"invalid existing HOST_CONTROL_TARGETS alias: {raw!r}")
        if alias not in aliases:
            aliases.append(alias)
    if new_alias not in aliases:
        aliases.append(new_alias)
    return aliases


def validate_combined(env: dict[str, str], alias: str, updates: dict[str, str]) -> list[str]:
    combined = dict(env)
    combined.update(updates)
    aliases = active_aliases(combined, alias)
    combined["HOST_CONTROL_TARGETS"] = ",".join(aliases)

    seen_ids: dict[str, str] = {}
    seen_names: dict[str, str] = {}
    seen_tokens: dict[str, str] = {}
    seen_node_ids: dict[int, str] = {}
    for key in aliases:
        prefix = f"HOST_CONTROL_{key}_"
        values = {
            "name": combined.get(prefix + "NAME", "").strip(),
            "host_id": combined.get(prefix + "HOST_ID", "").strip().lower(),
            "url": combined.get(prefix + "URL", "").strip().rstrip("/"),
            "token": combined.get(prefix + "TOKEN", "").strip(),
            "verify_tls": combined.get(prefix + "VERIFY_TLS", "true").strip(),
            "node_id": combined.get(prefix + "NODE_ID", "").strip(),
        }
        missing = [field for field in ("name", "host_id", "url", "token") if not values[field]]
        if missing:
            fail(f"existing target {key} is incomplete: {', '.join(missing)}")
        validate_target(
            key,
            values["name"],
            values["host_id"],
            values["url"],
            values["token"],
            values["verify_tls"],
        )
        node_id = None
        if values["node_id"]:
            try:
                node_id = int(values["node_id"])
            except ValueError:
                fail(f"{prefix}NODE_ID must be a positive integer")
            if node_id <= 0:
                fail(f"{prefix}NODE_ID must be a positive integer")
            other = seen_node_ids.get(node_id)
            if other is not None and other != key:
                fail(f"duplicate host-control node_id: {other} and {key}")
            seen_node_ids[node_id] = key

        folded_name = values["name"].casefold()
        for value, seen, label in (
            (values["host_id"], seen_ids, "host_id"),
            (folded_name, seen_names, "name"),
            (values["token"], seen_tokens, "token"),
        ):
            other = seen.get(value)
            if other is not None and other != key:
                fail(f"duplicate host-control {label}: {other} and {key}")
            seen[value] = key
    return aliases


def render_env(path: Path, updates: dict[str, str]) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    replaced: set[str] = set()
    for raw in lines:
        if "=" in raw and not raw.lstrip().startswith("#"):
            key = raw.split("=", 1)[0].strip()
            if key in updates:
                if key not in replaced:
                    out.append(f"{key}={updates[key]}")
                    replaced.add(key)
                continue
        out.append(raw)
    for key, value in updates.items():
        if key not in replaced:
            out.append(f"{key}={value}")
    return "\n".join(out) + "\n"


def backup_path(env_path: Path) -> Path:
    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    candidate = env_path.with_name(env_path.name + f".before-host-control-{stamp}")
    index = 1
    while candidate.exists():
        candidate = env_path.with_name(env_path.name + f".before-host-control-{stamp}.{index}")
        index += 1
    return candidate


def atomic_write(path: Path, content: str) -> None:
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def compose_cmd(args: argparse.Namespace, *extra: str) -> list[str]:
    return [
        "docker",
        "compose",
        "--project-name",
        args.project,
        "--env-file",
        str(args.env_path),
        "-f",
        "docker-compose.yml",
        *extra,
    ]


def recreate_bot(args: argparse.Namespace, backup: Path) -> None:
    try:
        subprocess.run(compose_cmd(args, "config", "--quiet"), check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        shutil.copy2(backup, args.env_path)
        os.chmod(args.env_path, 0o600)
        fail(f"Compose validation failed; .env restored from {backup}: {exc}")

    try:
        subprocess.run(
            compose_cmd(args, "up", "-d", "--no-deps", "--force-recreate", args.service),
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        fail(f"bot recreate failed; .env backup is {backup}: {exc}")

    for _ in range(30):
        try:
            with urllib.request.urlopen(args.health_url, timeout=2) as response:
                if response.read(32).decode("utf-8", "replace").strip() == "ok":
                    return
        except Exception:
            pass
        time.sleep(1)
    fail(f"bot health check failed; .env backup is {backup}")


def main() -> int:
    args = parse_args()
    if not args.enrollment.is_file():
        fail(f"enrollment file not found: {args.enrollment}")
    if not args.env_path.is_file():
        fail(f"env file not found: {args.env_path}")

    enrollment = parse_simple_env(args.enrollment, allowed=ENROLLMENT_KEYS)
    alias, target_updates = enrollment_to_updates(enrollment)
    if args.node_id is not None:
        if args.node_id <= 0:
            fail("--node-id must be a positive integer")
        if alias == "MASTER":
            fail("--node-id is only valid for direct nodes")
        target_updates[f"HOST_CONTROL_{alias}_NODE_ID"] = str(args.node_id)
    env = parse_simple_env(args.env_path)
    aliases = validate_combined(env, alias, target_updates)

    updates = dict(target_updates)
    updates["HOST_CONTROL_TARGETS"] = ",".join(aliases)
    candidate = render_env(args.env_path, updates)

    if args.check_only:
        print(f"Enrollment preflight OK for alias {alias}. No files changed.")
        return 0

    backup = backup_path(args.env_path)
    shutil.copy2(args.env_path, backup)
    os.chmod(backup, 0o600)
    atomic_write(args.env_path, candidate)

    if args.recreate_bot:
        recreate_bot(args, backup)

    print(f"Host-control enrollment imported for alias {alias}.")
    print(f"Backup: {backup}")
    if not args.recreate_bot:
        print("Bot was not recreated. Recreate only the bot service after validation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
