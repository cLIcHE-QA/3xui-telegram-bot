#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import os
import stat
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import dotenv_values

from xui import XUIClient, XUIError


INPUT_KEYS = {
    "NODE_ONBOARD_NAME",
    "NODE_ONBOARD_PANEL_URL",
    "NODE_ONBOARD_SYNC_TOKEN",
    "NODE_ONBOARD_VERIFY_TLS",
}


def fail(message: str) -> "NoReturn":
    raise SystemExit(f"ERROR: {message}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Register a direct 3x-ui node from a local mode-0600 enrollment file."
    )
    parser.add_argument("enrollment", type=Path)
    parser.add_argument("--env", dest="env_path", type=Path, default=Path(".env"))
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args()


def require_private_file(path: Path) -> None:
    if not path.is_file():
        fail(f"file not found: {path}")
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        fail(f"{path} must not be readable/writable by group or others; use chmod 600")


def parse_simple_env(path: Path, allowed: set[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in raw:
            fail(f"{path}:{lineno}: expected KEY=VALUE")
        key, value = raw.split("=", 1)
        key = key.strip()
        if key not in allowed:
            fail(f"{path}:{lineno}: unexpected key {key}")
        if key in values:
            fail(f"{path}:{lineno}: duplicate key {key}")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    missing = sorted(allowed - values.keys())
    if missing:
        fail("enrollment is incomplete: " + ", ".join(missing))
    return values


def parse_node_url(raw: str) -> dict[str, object]:
    value = raw.strip()
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname:
        fail("NODE_ONBOARD_PANEL_URL must be an absolute HTTPS URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        fail("NODE_ONBOARD_PANEL_URL must not contain credentials, query or fragment")
    try:
        port = parsed.port or 443
    except ValueError:
        fail("NODE_ONBOARD_PANEL_URL has an invalid port")
    base_path = parsed.path or "/"
    if not base_path.startswith("/"):
        base_path = "/" + base_path
    stripped = base_path.rstrip("/")
    if stripped.lower().endswith("/panel"):
        stripped = stripped[:-len("/panel")]
        base_path = stripped or "/"
    if not base_path.endswith("/"):
        base_path += "/"
    return {
        "scheme": "https",
        "address": parsed.hostname,
        "port": int(port),
        "basePath": base_path,
    }


def endpoint_key(node) -> tuple[str, str, int, str]:
    return (
        str(node.scheme).lower(),
        str(node.address).lower(),
        int(node.port),
        str(node.base_path or "/"),
    )


async def run(args: argparse.Namespace) -> int:
    require_private_file(args.enrollment)
    require_private_file(args.env_path)

    source = parse_simple_env(args.enrollment, INPUT_KEYS)
    name = source["NODE_ONBOARD_NAME"].strip()
    if not (1 <= len(name) <= 64) or "\n" in name or "\r" in name:
        fail("NODE_ONBOARD_NAME must contain 1-64 characters on one line")
    sync_token = source["NODE_ONBOARD_SYNC_TOKEN"].strip()
    if len(sync_token) < 8:
        fail("NODE_ONBOARD_SYNC_TOKEN looks too short")
    verify = source["NODE_ONBOARD_VERIFY_TLS"].strip().lower()
    if verify not in {"1", "true", "yes", "on"}:
        fail("v4.11 local onboarding requires verified HTTPS")

    node_url = parse_node_url(source["NODE_ONBOARD_PANEL_URL"])
    env = dotenv_values(args.env_path)
    master_url = str(env.get("PANEL_URL") or "").strip().rstrip("/")
    master_token = str(env.get("PANEL_API_TOKEN") or "").strip()
    master_verify = str(env.get("VERIFY_TLS") or "true").strip().lower() in {"1", "true", "yes", "on"}
    if not master_url or not master_token:
        fail("bot .env must contain PANEL_URL and PANEL_API_TOKEN")

    client = XUIClient(master_url, master_token, master_verify)
    nodes = await client.nodes_list()
    desired_endpoint = (
        str(node_url["scheme"]),
        str(node_url["address"]).lower(),
        int(node_url["port"]),
        str(node_url["basePath"]),
    )
    name_matches = [n for n in nodes if n.name.strip().casefold() == name.casefold() and not n.transitive]
    endpoint_matches = [n for n in nodes if endpoint_key(n) == desired_endpoint and not n.transitive]

    if name_matches or endpoint_matches:
        candidates = {n.id: n for n in name_matches + endpoint_matches}
        if len(candidates) != 1:
            fail("existing node identity is ambiguous; inspect Nodes before onboarding")
        existing = next(iter(candidates.values()))
        if existing.name.strip().casefold() != name.casefold() or endpoint_key(existing) != desired_endpoint:
            fail("existing node matches only name or endpoint; refusing implicit reassignment")
        print(f"Node already registered. NODE_ID={existing.id}")
        return 0

    payload = {
        "id": 0,
        "name": name,
        "remark": "",
        **node_url,
        "apiToken": sync_token,
        "clearApiToken": False,
        "enable": True,
        "allowPrivateAddress": False,
        "inboundSyncMode": "all",
        "inboundTags": [],
        "outboundTag": "",
        "pinnedCertSha256": "",
        "tlsVerifyMode": "verify",
    }

    result = await client.node_test(payload)
    status = str(result.get("status") or "unknown").lower()
    print(f"Node preflight OK. Panel status={status}.")
    if not args.apply:
        print("No changes made. Re-run with --apply to register the node.")
        return 0

    try:
        node = await client.node_add(payload)
    except XUIError as exc:
        fail(
            "node add did not return confirmed success; mutation was not retried. "
            f"Inspect Nodes before any retry ({type(exc).__name__})."
        )
    print(f"Node registered. NODE_ID={node.id}")
    return 0


def main() -> int:
    args = parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
