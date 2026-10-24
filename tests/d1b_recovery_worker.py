"""Изолированный дочерний процесс DR-проверки #887 с synthetic secrets.

Запускается исключительно тестом из tests/test_d1b_recovery_drill.py.
Получает ТОЛЬКО архив, новый каталог и ключи backup/new по stdin;
исходный каталог, старый Fernet key и production secrets ему не передаются.
Никакого сетевого подключения к production или запуска постоянного listener.
"""
from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import sys
from pathlib import Path

# Python -I исключает PYTHONPATH/cwd и user site; явно подключается код
# проверяемого checkout, а не каталог удалённого source.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aiohttp.test_utils import TestClient, TestServer

from subscription_page_admin import COOKIE, _totp_at, _totp_key, create_editor_app
from subscription_page_admin_recovery import OfflineD1bRecovery
from subscription_page_admin_vault import EncryptedAdminRoster
from subscription_page_admin import EncryptedDrafts


async def _assert_https_contract(app, password: str, seed: str) -> None:
    headers = {"Host": "admin.example.invalid", "Origin": "https://admin.example.invalid"}
    async with TestClient(TestServer(app)) as client:
        # Simulated reverse-proxy headers: no forwarded header can change the
        # origin of the request or bypass the backend's explicit Origin/Host gate.
        payload = {"username": "owner1", "password": password,
                   "otp": _totp_at(_totp_key(seed), int(__import__("time").time() // 30))}
        denied = await client.post("/admin/subpage/api/session", json=payload,
                                   headers={**headers, "Origin": "http://admin.example.invalid"})
        if denied.status != 403:
            raise AssertionError("Insecure origin unexpectedly accepted")
        bad_host = await client.post("/admin/subpage/api/session", json=payload,
                                     headers={**headers, "Host": "wrong.example.invalid"})
        if bad_host.status != 403:
            raise AssertionError("Spoofed Host unexpectedly accepted")
        spoof = await client.post(
            "/admin/subpage/api/session", json=payload,
            headers={**headers, "X-Forwarded-Host": "attacker.invalid",
                     "X-Forwarded-Proto": "http",
                     "X-Forwarded-For": "203.0.113.21"})
        if spoof.status != 200:
            raise AssertionError("Valid proxied HTTPS-origin login failed")
        if COOKIE not in spoof.cookies:
            raise AssertionError("Secure session cookie not issued")
        cookie_header = spoof.headers.getall("Set-Cookie", [])
        if (not cookie_header or
                not all(flag in cookie_header[0] for flag in
                        ("Secure", "HttpOnly", "SameSite=Strict"))):
            raise AssertionError("Cookie security flags missing")
        current = await client.get(
            "/admin/subpage/api/draft",
            headers={**headers, "Cookie": COOKIE + "=" + spoof.cookies[COOKIE].value})
        if current.status != 200:
            raise AssertionError("Recovered revision not readable behind proxy")
        response = await current.json()
        if response["revision"] != 1:
            raise AssertionError("Recovered revision mismatch")


def main() -> int:
    try:
        if len(sys.argv) != 3:
            raise ValueError("Worker requires sealed archive and new private destination")
        archive = Path(sys.argv[1])
        destination = Path(sys.argv[2])
        payload = sys.stdin.read(1025)
        if len(payload) > 1024:
            raise ValueError("Secret channel too large")
        keys = json.loads(payload)
        if not isinstance(keys, dict) or set(keys) != {"backup_key", "new_key"}:
            raise ValueError("Invalid synthetic recovery channel")
        backup_key = keys["backup_key"].encode("ascii")
        new_key = keys["new_key"].encode("ascii")
        result = OfflineD1bRecovery.recover_lost_key(
            archive, backup_key, destination, new_key)
        roster = EncryptedAdminRoster(destination / "private-accounts.enc", new_key)
        revision, accounts = roster.snapshot()
        drafts = EncryptedDrafts(destination / "drafts.sqlite3", new_key)
        draft_revision, document = drafts.current()
        if (revision != 1 or draft_revision != 1 or
                len(accounts) != 2 or accounts[0].username != "owner1" or
                document["brandingSettings"]["title"] != "Synthetic VPN" or
                result.revoked_sessions != 1):
            raise AssertionError("Recovered roster/draft/session mismatch")
        with sqlite3.connect(destination / "drafts.sqlite3") as db:
            if db.execute("SELECT count(*) FROM admin_sessions").fetchone()[0] != 0:
                raise AssertionError("Recovered cookies were not revoked")
            if db.execute("SELECT count(*) FROM draft_proposals").fetchone()[0] != 1:
                raise AssertionError("Proposals lost during disaster recovery")
            if db.execute("SELECT last_step FROM admin_totp_replay WHERE username='owner1'").fetchone()[0] != 17000000:
                raise AssertionError("TOTP anti-replay state lost")
        if destination.stat().st_mode & 0o777 != 0o700:
            raise AssertionError("Recovered directory permissions unsafe")
        for name in ("drafts.sqlite3", "private-accounts.enc"):
            if (destination / name).stat().st_mode & 0o777 != 0o600:
                raise AssertionError("Recovered file permissions unsafe")
        if not destination.with_name(destination.name + "/private-accounts.enc").is_file():
            raise AssertionError("Roster missing")
        app = create_editor_app(
            accounts_loader=roster.load_accounts,
            db_path=destination / "drafts.sqlite3", encryption_key=new_key,
            https_origin="https://admin.example.invalid")
        asyncio.run(_assert_https_contract(
            app, "synthetic-disaster-password", accounts[0].totp_secret_b32))
        # Output only operational metadata, never key, verifier, TOTP, cookie,
        # DB content, private filesystem path, or external URL.
        print(json.dumps({"status": "PASS", "drafts": result.drafts,
                          "sessions_revoked": result.revoked_sessions,
                          "roster_revision": result.revision,
                          "https_origin_contract": "PASS"},
                         sort_keys=True))
        return 0
    except Exception:
        # Operator secrets and internal filesystem paths must not enter logs
        # even when an underlying crypto/SQL error embeds them.
        print("ISOLATED_DRILL_FAIL", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
