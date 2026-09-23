#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

ALIAS_RE = re.compile(r"^[A-Z0-9][A-Z0-9_]{0,31}$")
INPUT_KEYS = {
    "NODE_ADMIN_ALIAS",
    "NODE_ADMIN_NODE_ID",
    "NODE_ADMIN_NODE_NAME",
    "NODE_ADMIN_PANEL_URL",
    "NODE_ADMIN_API_TOKEN",
    "NODE_ADMIN_VERIFY_TLS",
}


def fail(message: str) -> "NoReturn":
    raise SystemExit(f"ERROR: {message}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Safely import a direct 3x-ui admin target into bot .env without printing its token."
    )
    parser.add_argument("enrollment", type=Path)
    parser.add_argument("--env", dest="env_path", type=Path, default=Path(".env"))
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
        if allowed is not None and key not in allowed:
            fail(f"{path}:{lineno}: unexpected key {key}")
        if not key or key in values:
            fail(f"{path}:{lineno}: invalid or duplicate key")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def active_aliases(env: dict[str, str], new_alias: str) -> list[str]:
    aliases: list[str] = []
    for raw in env.get("NODE_BACKUP_TARGETS", "").split(","):
        alias = raw.strip().upper()
        if not alias:
            continue
        if not ALIAS_RE.fullmatch(alias):
            fail(f"invalid existing NODE_BACKUP_TARGETS alias: {raw!r}")
        if alias not in aliases:
            aliases.append(alias)
    if new_alias not in aliases:
        aliases.append(new_alias)
    return aliases


def enrollment_updates(values: dict[str, str]) -> tuple[str, dict[str, str]]:
    missing = sorted(INPUT_KEYS - values.keys())
    if missing:
        fail("enrollment is incomplete: " + ", ".join(missing))

    alias = values["NODE_ADMIN_ALIAS"].strip().upper()
    if not ALIAS_RE.fullmatch(alias):
        fail(f"invalid alias {alias!r}")

    try:
        node_id = int(values["NODE_ADMIN_NODE_ID"].strip())
    except ValueError:
        fail("NODE_ADMIN_NODE_ID must be a positive integer")
    if node_id <= 0:
        fail("NODE_ADMIN_NODE_ID must be a positive integer")

    name = values["NODE_ADMIN_NODE_NAME"].strip()
    if not (1 <= len(name) <= 64) or "\n" in name or "\r" in name:
        fail("NODE_ADMIN_NODE_NAME must contain 1-64 characters on one line")

    url = values["NODE_ADMIN_PANEL_URL"].strip().rstrip("/")
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        fail("NODE_ADMIN_PANEL_URL must be an absolute http(s) URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        fail("NODE_ADMIN_PANEL_URL must not contain credentials, query or fragment")

    token = values["NODE_ADMIN_API_TOKEN"].strip()
    if len(token) < 8:
        fail("NODE_ADMIN_API_TOKEN looks too short")

    verify_raw = values["NODE_ADMIN_VERIFY_TLS"].strip().lower()
    if verify_raw not in {"1", "true", "yes", "on", "0", "false", "no", "off"}:
        fail("NODE_ADMIN_VERIFY_TLS must be true or false")
    verify = "true" if verify_raw in {"1", "true", "yes", "on"} else "false"
    if parsed.scheme == "https" and verify != "true":
        fail("verified HTTPS is required for direct admin targets")
    if parsed.scheme == "http":
        fail("plain HTTP is not accepted by the v4.11 onboarding importer")

    prefix = f"NODE_BACKUP_{alias}_"
    return alias, {
        prefix + "NODE_NAME": name,
        prefix + "NODE_ID": str(node_id),
        prefix + "PANEL_URL": url,
        prefix + "API_TOKEN": token,
        prefix + "VERIFY_TLS": verify,
    }


def validate_combined(env: dict[str, str], alias: str, updates: dict[str, str]) -> list[str]:
    combined = dict(env)
    combined.update(updates)
    aliases = active_aliases(combined, alias)
    seen_ids: dict[int, str] = {}
    seen_names: dict[str, str] = {}
    seen_tokens: dict[str, str] = {}

    for key in aliases:
        prefix = f"NODE_BACKUP_{key}_"
        name = combined.get(prefix + "NODE_NAME", "").strip()
        raw_id = combined.get(prefix + "NODE_ID", "").strip()
        url = combined.get(prefix + "PANEL_URL", "").strip().rstrip("/")
        token = combined.get(prefix + "API_TOKEN", "").strip()
        verify = combined.get(prefix + "VERIFY_TLS", "true").strip().lower()
        missing = [
            field for field, value in (
                ("NODE_NAME", name),
                ("PANEL_URL", url),
                ("API_TOKEN", token),
            ) if not value
        ]
        if missing:
            fail(f"existing target {key} is incomplete: {', '.join(missing)}")

        if raw_id:
            try:
                node_id = int(raw_id)
            except ValueError:
                fail(f"{prefix}NODE_ID must be a positive integer")
            if node_id <= 0:
                fail(f"{prefix}NODE_ID must be a positive integer")
            other = seen_ids.get(node_id)
            if other is not None and other != key:
                fail(f"duplicate direct-admin node_id: {other} and {key}")
            seen_ids[node_id] = key

        folded = name.casefold()
        other = seen_names.get(folded)
        if other is not None and other != key:
            fail(f"duplicate direct-admin node name: {other} and {key}")
        seen_names[folded] = key

        if token:
            other = seen_tokens.get(token)
            if other is not None and other != key:
                fail(f"direct-admin API tokens must be unique: {other} and {key}")
            seen_tokens[token] = key

        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname:
            fail(f"{prefix}PANEL_URL must use HTTPS")
        if verify not in {"1", "true", "yes", "on"}:
            fail(f"{prefix}VERIFY_TLS=false is forbidden by v4.11 onboarding")
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
    candidate = env_path.with_name(env_path.name + f".before-node-admin-{stamp}")
    index = 1
    while candidate.exists():
        candidate = env_path.with_name(env_path.name + f".before-node-admin-{stamp}.{index}")
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
        "docker", "compose",
        "--project-name", args.project,
        "--env-file", str(args.env_path),
        "-f", "docker-compose.yml",
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

    source = parse_simple_env(args.enrollment, allowed=INPUT_KEYS)
    alias, target_updates = enrollment_updates(source)
    env = parse_simple_env(args.env_path)
    aliases = validate_combined(env, alias, target_updates)

    updates = dict(target_updates)
    updates["NODE_BACKUP_TARGETS"] = ",".join(aliases)
    candidate = render_env(args.env_path, updates)

    if args.check_only:
        print(f"Direct-admin enrollment preflight OK for alias {alias}. No files changed.")
        return 0

    backup = backup_path(args.env_path)
    shutil.copy2(args.env_path, backup)
    os.chmod(backup, 0o600)
    atomic_write(args.env_path, candidate)

    if args.recreate_bot:
        recreate_bot(args, backup)

    print(f"Direct-admin target imported for alias {alias}.")
    print(f"Backup: {backup}")
    if not args.recreate_bot:
        print("Bot was not recreated. Recreate only the bot service after validation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
