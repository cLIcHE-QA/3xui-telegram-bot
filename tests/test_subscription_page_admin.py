"""#887 D1b: fail-closed admin API, encrypted drafts, CSRF, roles, conflicts.

Synthetic fixtures only. Never log/export real URLs or customer tokens.
"""
from __future__ import annotations

import base64
import hashlib
import copy
import json
import time
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from aiohttp.test_utils import TestClient, TestServer
from cryptography.fernet import Fernet

from subscription_page_admin import (
    COOKIE, AdminAccount, EncryptedDrafts, SessionCapacityReached, StaleDraft, create_editor_app,
    password_verifier, _account_binding, _totp_at,
)


TEST_MFA_SEEDS = {
    "owner1": b"test owner mfa seed!!",
    "editor1": b"test editor mfa seed!",
    "viewer1": b"test viewer mfa seed!",
}
TEST_MFA_B32 = {name: base64.b32encode(value).decode("ascii")
                 for name, value in TEST_MFA_SEEDS.items()}


def current_otp(username: str = "owner1") -> str:
    return _totp_at(TEST_MFA_SEEDS[username], int(time.time() // 30))


def fixture() -> dict:
    loc = lambda value: {code: value + "-" + code for code in ("en", "ru", "zh", "fa", "fr")}
    return {
        "locales": ["en", "ru", "zh", "fa", "fr"], "version": "1",
        "uiConfig": {"subscriptionInfoBlockType": "expanded", "installationGuidesBlockType": "cards"},
        "platforms": {
            "ios": {"displayName": loc("iOS"), "svgIconKey": "AppleIcon", "apps": [
                {"name": "Synthetic", "featured": True, "svgIconKey": "Demo", "blocks": [
                    {"title": loc("Install"), "description": loc("Only synthetic"),
                     "svgIconKey": "Plus", "svgIconColor": "#18a5f9", "buttons": [
                        {"link": "https://example.invalid/demo", "type": "external",
                         "text": loc("Download"), "svgIconKey": "ExternalLink"},
                        {"link": "client://import/{{SUBSCRIPTION_LINK}}", "type": "subscriptionLink",
                         "text": loc("Import"), "svgIconKey": "Plus"}]}
                ]}
            ]}
        },
        "svgLibrary": {"Demo": '<svg xmlns="http://www.w3.org/2000/svg"/>'},
        "baseSettings": {"metaTitle": "DEMO", "metaDescription": "Synthetic",
                         "hideGetLinkButton": False, "showConnectionKeys": False},
        "baseTranslations": {"getLink": loc("Get")},
        "brandingSettings": {"title": "Synthetic VPN", "logoUrl": "", "supportUrl": ""},
    }


class DraftStoreTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = Path(self.dir.name) / "drafts.sqlite3"
        self.key = Fernet.generate_key()
        self.store = EncryptedDrafts(self.path, self.key)
        self.binding = "a" * 64
        self.bindings = {"owner1": self.binding, "editor1": self.binding}

    def issue(self, store, *args, **kwargs):
        return store.issue_session(*args, account_binding=self.binding, **kwargs)

    def touch(self, store, token_hash):
        return store.touch_session(token_hash, self.bindings)

    def test_revisions_are_encrypted_and_lossless(self):
        doc = fixture()
        rev, original = self.store.current()
        self.assertEqual((rev, original), (0, None))
        stored = self.store.save("alice", 0, doc)
        self.assertEqual(stored["revision"], 1)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.store.current(), (1, doc))
        raw = self.path.read_bytes()
        self.assertNotIn(b"example.invalid", raw)
        self.assertNotIn(b"Synthetic VPN", raw)
        self.assertNotIn(b"SUBSCRIPTION_LINK", raw)
        self.assertNotIn(b"<svg", raw)
        self.assertEqual(self.store.history()[0]["actor"], "alice")
        self.assertEqual(self.store.history()[0]["digest"], stored["digest"])
        self.assertNotIn("content", self.store.history()[0])

    def test_totp_replay_ledger_persists_across_connections(self):
        # Never persist an MFA secret/code; only account identity and used step.
        other = EncryptedDrafts(self.path, self.key)
        self.assertTrue(self.issue(self.store, "owner1", 1000, "token-a", "csrf-a", 120))
        self.assertFalse(self.issue(other, "owner1", 1000, "token-b", "csrf-b", 120))
        self.assertFalse(self.issue(self.store, "owner1", 999, "token-c", "csrf-c", 120))
        self.assertTrue(self.issue(other, "owner1", 1001, "token-d", "csrf-d", 120))
        self.assertTrue(self.issue(self.store, "editor1", 1000, "token-e", "csrf-e", 120))
        with sqlite3.connect(self.path) as db:
            rows = db.execute(
                "SELECT username,last_step FROM admin_totp_replay ORDER BY username"
            ).fetchall()
        self.assertEqual(rows, [("editor1", 1000), ("owner1", 1001)])


    def test_concurrent_instances_only_accept_one_totp_step(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        replica = EncryptedDrafts(self.path, self.key)
        barrier = Barrier(2)

        def issue(store, suffix):
            barrier.wait(timeout=5)
            return self.issue(store, "owner1", 77777, "token-" + suffix,
                                       "csrf-" + suffix, 120)

        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(issue, self.store, "first")
            b = pool.submit(issue, replica, "second")
            self.assertEqual([a.result(), b.result()].count(True), 1)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute(
                "SELECT count(*) FROM admin_sessions WHERE username='owner1'"
            ).fetchone()[0], 1)

    def test_shared_sessions_are_encrypted_and_revoked_across_connections(self):
        cookie = "synthetic-cookie-not-to-store"
        token_hash = hashlib.sha256(cookie.encode()).hexdigest()
        csrf = "synthetic-private-csrf-must-be-encrypted"
        self.assertTrue(self.issue(self.store, "owner1", 100, token_hash, csrf, 120))
        raw = self.path.read_bytes()
        self.assertNotIn(cookie.encode(), raw)
        self.assertNotIn(csrf.encode(), raw)
        replica = EncryptedDrafts(self.path, self.key)
        username, token, deadline, last_seen = self.touch(replica, token_hash)
        self.assertEqual((username, token), ("owner1", csrf))
        self.assertGreater(deadline, last_seen)
        with sqlite3.connect(self.path) as db:
            fields = db.execute(
                "SELECT token_hash,username,csrf_ciphertext FROM admin_sessions"
            ).fetchone()
            self.assertEqual(fields[0], token_hash)
            self.assertEqual(fields[1], "owner1")
            self.assertNotIn(csrf.encode(), fields[2])
        replica.revoke_session(token_hash)
        self.assertIsNone(self.touch(self.store, token_hash))

    def test_session_rotation_keeps_old_token_when_totp_replayed(self):
        self.assertTrue(self.issue(self.store, "owner1", 1000, "old-hash", "first-csrf", 120))
        self.assertFalse(self.issue(self.store, 
            "owner1", 1000, "new-hash", "bad-csrf", 120, "old-hash"))
        self.assertEqual(self.touch(self.store, "old-hash")[1], "first-csrf")
        self.assertIsNone(self.touch(self.store, "new-hash"))
        self.assertTrue(self.issue(self.store, 
            "owner1", 1001, "new-hash", "new-csrf", 120, "old-hash"))
        self.assertIsNone(self.touch(self.store, "old-hash"))
        self.assertEqual(self.touch(self.store, "new-hash")[1], "new-csrf")

    def test_capacity_denial_does_not_consume_mfa_step(self):
        with patch("subscription_page_admin.MAX_LIVE_SESSIONS", 1):
            self.assertTrue(self.issue(self.store, "owner1", 100, "first", "c1", 120))
            with self.assertRaises(SessionCapacityReached):
                self.issue(self.store, "editor1", 200, "second", "c2", 120)
            with sqlite3.connect(self.path) as db:
                self.assertIsNone(db.execute(
                    "SELECT last_step FROM admin_totp_replay WHERE username='editor1'"
                ).fetchone())
            self.store.revoke_session("first")
            self.assertTrue(self.issue(self.store, "editor1", 200, "second", "c2", 120))

    def test_expired_and_idle_sessions_are_removed(self):
        self.assertTrue(self.issue(self.store, "owner1", 100, "idle-hash", "csrf", 120))
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE admin_sessions SET last_seen_at = last_seen_at - 400")
        self.assertIsNone(self.touch(self.store, "idle-hash"))
        self.assertTrue(self.issue(self.store, "owner1", 101, "expiry-hash", "csrf2", 120))
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE admin_sessions SET expires_at = expires_at - 1000")
        self.assertIsNone(self.touch(self.store, "expiry-hash"))

    def test_tampered_session_secret_is_fail_closed_and_evicted(self):
        self.assertTrue(self.issue(self.store, "owner1", 100, "tamper-hash", "csrf", 120))
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE admin_sessions SET csrf_ciphertext=? WHERE token_hash=?",
                       (b"invalid-token", "tamper-hash"))
        self.assertIsNone(self.touch(self.store, "tamper-hash"))
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute(
                "SELECT count(*) FROM admin_sessions WHERE token_hash='tamper-hash'"
            ).fetchone()[0], 0)

    def test_optimistic_lock_and_proposal_do_not_publish(self):
        doc = fixture()
        self.store.save("alice", 0, doc)
        with self.assertRaises(StaleDraft):
            self.store.save("bob", 0, doc)
        self.assertEqual(self.store.current(), (1, doc))
        proposal = self.store.propose("alice", 1)
        self.assertEqual(proposal["state"], "pending_manual_review")
        self.assertEqual(proposal["revision"], 1)
        with self.assertRaises(StaleDraft):
            self.store.propose("alice", 0)
        revised = copy.deepcopy(doc)
        revised["brandingSettings"]["title"] = "Safe change"
        self.assertEqual(self.store.save("bob", 1, revised)["revision"], 2)
        with sqlite3.connect(self.path) as db:
            proposals = db.execute("SELECT state FROM draft_proposals").fetchall()
            self.assertEqual(proposals, [("pending_manual_review",)])

    def test_forbid_symlink_and_overly_permissive_db(self):
        target = Path(self.dir.name) / "regular"
        target.write_text("fake")
        link = Path(self.dir.name) / "link"
        link.symlink_to(target)
        with self.assertRaises(ValueError):
            EncryptedDrafts(link, self.key)
        os.chmod(self.path, 0o644)
        with self.assertRaises(ValueError):
            EncryptedDrafts(self.path, self.key)

    def test_bad_password_and_fails_closed_setup(self):
        with self.assertRaises(ValueError):
            password_verifier("short")
        with self.assertRaises(ValueError):
            create_editor_app(accounts=[], db_path=self.path, encryption_key=self.key,
                              https_origin="https://admin.example.test")
        with self.assertRaises(ValueError):
            create_editor_app(accounts=[AdminAccount("root", password_verifier("strong-test-password"), "owner")],
                              db_path=self.path, encryption_key=self.key,
                              https_origin="http://admin.example.test")


class AdminApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.key = Fernet.generate_key()
        password = "strong-test-password"
        self.verifiers = {name: password_verifier(password) for name in TEST_MFA_B32}
        accounts = [
            AdminAccount(name, self.verifiers[name], role, TEST_MFA_B32[name])
            for name, role in (("owner1", "owner"), ("editor1", "editor"), ("viewer1", "viewer"))
        ]
        self.app = create_editor_app(
            accounts=accounts, db_path=Path(self.dir.name) / "drafts.sqlite3",
            encryption_key=self.key, https_origin="https://admin.example.test",
            session_ttl=120)
        self.client = TestClient(TestServer(self.app))
        await self.client.start_server()
        self.url = "/admin/subpage/api"
        self.origin = {"Origin": "https://admin.example.test", "Host": "admin.example.test"}
        self.auth: dict[str, tuple[str, str]] = {}

    async def asyncTearDown(self):
        await self.client.close()

    async def login(self, username: str, password: str = "strong-test-password",
                    otp: str | None = None):
        resp = await self.client.post(self.url + "/session", json={"username": username, "password": password, "otp": otp if otp is not None else current_otp(username)},
                                      headers=self.origin)
        if resp.status != 200:
            return resp
        payload = await resp.json()
        cookie_value = resp.cookies[COOKIE].value
        cookie_attributes = resp.cookies[COOKIE]
        self.assertTrue(cookie_attributes["secure"])
        self.assertTrue(cookie_attributes["httponly"])
        self.assertEqual(cookie_attributes["samesite"], "Strict")
        self.auth[username] = (cookie_value, payload["csrfToken"])
        self.assertNotIn("password", str(payload))
        return resp

    def headers(self, username: str, *, csrf: bool = False, revision: int | None = None) -> dict:
        cookie, token = self.auth[username]
        result = dict(self.origin, Cookie=f"{COOKIE}={cookie}")
        if csrf:
            result["X-CSRF-Token"] = token
        if revision is not None:
            result["If-Match"] = f'"rev-{revision}"'
        return result

    async def test_no_guest_access_and_security_headers(self):
        for method, path in [("get", "/draft"), ("get", "/history"), ("get", "/session")]:
            r = await self.client.request(method, self.url + path)
            self.assertEqual(r.status, 401, path)
            self.assertEqual(r.headers.get("Cache-Control"), "no-store")
            self.assertEqual(r.headers.get("X-Frame-Options"), "DENY")
            self.assertIn("default-src 'none'", r.headers.get("Content-Security-Policy", ""))
        r = await self.client.put(self.url + "/draft", json={"config": fixture()}, headers=self.origin)
        self.assertEqual(r.status, 401)
        # A bearer-like subscription token is not an independent web-admin login.
        bearer = await self.client.get(self.url + "/draft", headers={**self.origin, "Authorization": "Bearer synthetic-subscription-token"})
        self.assertEqual(bearer.status, 401)
        r = await self.client.post(self.url + "/proposals", json={}, headers=self.origin)
        self.assertEqual(r.status, 401)
        r = await self.client.post(self.url + "/publish", json={}, headers=self.origin)
        self.assertEqual(r.status, 404)

    async def test_login_denial_and_rate_limit(self):
        missing_origin = await self.client.post(
            self.url + "/session", json={"username": "owner1", "password": "strong-test-password", "otp": current_otp()})
        self.assertEqual(missing_origin.status, 403)
        wrong_origin = await self.client.post(
            self.url + "/session", json={"username": "owner1", "password": "strong-test-password", "otp": current_otp()},
            headers={"Origin": "https://evil.example", "Host": "admin.example.test"})
        self.assertEqual(wrong_origin.status, 403)
        for _ in range(5):
            r = await self.client.post(self.url + "/session",
                                       json={"username": "owner1", "password": "wrong"}, headers=self.origin)
            self.assertEqual(r.status, 401)
        locked = await self.client.post(
            self.url + "/session", json={"username": "owner1", "password": "strong-test-password", "otp": current_otp()},
            headers=self.origin)
        self.assertEqual(locked.status, 429)

    async def test_roles_csrf_revision_and_export(self):
        await self.login("owner1")
        await self.login("editor1")
        await self.login("viewer1")
        guest = await self.client.get(self.url + "/draft")
        self.assertEqual(guest.status, 401)
        viewer_read = await self.client.get(self.url + "/draft", headers=self.headers("viewer1"))
        self.assertEqual(viewer_read.status, 200)
        self.assertEqual((await viewer_read.json())["config"], None)
        self.assertEqual(viewer_read.headers["ETag"], '"rev-0"')
        viewer_write = await self.client.put(self.url + "/draft", json={"config": fixture()},
                                             headers=self.headers("viewer1", csrf=True, revision=0))
        self.assertEqual(viewer_write.status, 403)
        no_csrf = await self.client.put(self.url + "/draft", json={"config": fixture()},
                                        headers=self.headers("editor1", revision=0))
        self.assertEqual(no_csrf.status, 403)
        wrong_csrf = await self.client.put(self.url + "/draft", json={"config": fixture()},
                                           headers={**self.headers("editor1", csrf=True, revision=0), "X-CSRF-Token": "invalid"})
        self.assertEqual(wrong_csrf.status, 403)
        foreign_origin = await self.client.put(self.url + "/draft", json={"config": fixture()},
                                               headers={**self.headers("editor1", csrf=True, revision=0),
                                                        "Origin": "https://evil.example"})
        self.assertEqual(foreign_origin.status, 403)
        missing_version = await self.client.put(self.url + "/draft", json={"config": fixture()},
                                                headers=self.headers("editor1", csrf=True))
        self.assertEqual(missing_version.status, 428)
        created = await self.client.put(self.url + "/draft", json={"config": fixture()},
                                        headers=self.headers("editor1", csrf=True, revision=0))
        self.assertEqual(created.status, 200)
        self.assertEqual((await created.json())["revision"], 1)
        stale = await self.client.put(self.url + "/draft", json={"config": fixture()},
                                      headers=self.headers("editor1", csrf=True, revision=0))
        self.assertEqual(stale.status, 409)
        current = await self.client.get(self.url + "/draft", headers=self.headers("viewer1"))
        self.assertEqual((await current.json())["config"], fixture())
        self.assertEqual(current.headers["ETag"], '"rev-1"')
        history = await self.client.get(self.url + "/history", headers=self.headers("viewer1"))
        self.assertEqual((await history.json())["revisions"][0]["actor"], "editor1")
        no_owner = await self.client.post(self.url + "/proposals", headers=self.headers("editor1", csrf=True, revision=1))
        self.assertEqual(no_owner.status, 403)
        approved = await self.client.post(self.url + "/proposals", headers=self.headers("owner1", csrf=True, revision=1))
        self.assertEqual(approved.status, 202)
        self.assertEqual((await approved.json())["state"], "pending_manual_review")
        self.assertEqual((await self.client.post(self.url + "/publish", headers=self.headers("owner1", csrf=True))).status, 404)
        logout = await self.client.delete(self.url + "/session", headers=self.headers("viewer1", csrf=True))
        self.assertEqual(logout.status, 200)
        expired = await self.client.get(self.url + "/draft", headers=self.headers("viewer1"))
        self.assertEqual(expired.status, 401)

    async def test_bad_json_prototype_poison_unsafe_uri_remain_inert(self):
        await self.login("owner1")
        invalid = copy.deepcopy(fixture())
        invalid["__proto__"] = {"isAdmin": True}
        r = await self.client.put(self.url + "/draft", json={"config": invalid},
                                  headers=self.headers("owner1", csrf=True, revision=0))
        self.assertEqual(r.status, 400)
        incompatible = copy.deepcopy(fixture())
        incompatible["version"] = "2"
        r = await self.client.put(self.url + "/draft", json={"config": incompatible},
                                  headers=self.headers("owner1", csrf=True, revision=0))
        self.assertEqual(r.status, 400)
        payload = copy.deepcopy(fixture())
        payload["platforms"]["ios"]["apps"][0]["blocks"][0]["buttons"][0]["link"] = (
            "javascript:alert('do-not-run')")
        # A draft preserves operator input; it does not authorize URL execution.
        r = await self.client.put(self.url + "/draft", json={"config": payload},
                                  headers=self.headers("owner1", csrf=True, revision=0))
        self.assertEqual(r.status, 200)
        self.assertEqual((await self.client.get(self.url + "/draft", headers=self.headers("owner1"))).status, 200)

    async def test_mfa_required_and_one_time_code_replay_rejected(self):
        for otp in [None, "12345", "invalid"]:
            credentials = {"username": "owner1", "password": "strong-test-password"}
            if otp is not None:
                credentials["otp"] = otp
            response = await self.client.post(self.url + "/session",
                json=credentials, headers=self.origin)
            self.assertEqual(response.status, 401)
        one_time_code = current_otp("owner1")
        self.assertEqual((await self.login("owner1", otp=one_time_code)).status, 200)
        replay = await self.client.post(self.url + "/session",
            json={"username": "owner1", "password": "strong-test-password", "otp": one_time_code},
            headers=self.origin)
        self.assertEqual(replay.status, 401)

    async def test_mfa_replay_rejected_across_process_like_instances(self):
        # A new aiohttp application with the same SQLite DB models a restart
        # or a second worker, not merely another session in the same process.
        otp = current_otp("owner1")
        self.assertEqual((await self.login("owner1", otp=otp)).status, 200)
        other_app = create_editor_app(
            accounts=[AdminAccount(
                "owner1", password_verifier("strong-test-password"),
                "owner", TEST_MFA_B32["owner1"])],
            db_path=Path(self.dir.name) / "drafts.sqlite3",
            encryption_key=self.key,
            https_origin="https://admin.example.test",
            session_ttl=120)
        async with TestClient(TestServer(other_app)) as other_client:
            replay = await other_client.post(
                self.url + "/session",
                json={"username": "owner1", "password": "strong-test-password", "otp": otp},
                headers=self.origin)
            self.assertEqual(replay.status, 401)
        # The durable record also rejects replay in the original instance.
        again = await self.client.post(
            self.url + "/session",
            json={"username": "owner1", "password": "strong-test-password", "otp": otp},
            headers=self.origin)
        self.assertEqual(again.status, 401)

    async def test_mfa_replay_storage_failure_fails_closed(self):
        with patch.object(EncryptedDrafts, "issue_session",
                          side_effect=sqlite3.OperationalError("synthetic failure")):
            response = await self.client.post(
                self.url + "/session",
                json={"username": "owner1", "password": "strong-test-password",
                      "otp": current_otp("owner1")},
                headers=self.origin)
        self.assertEqual(response.status, 503)


    async def test_session_survives_new_api_instance_and_remote_logout(self):
        self.assertEqual((await self.login("owner1")).status, 200)
        account = AdminAccount(
            "owner1", self.verifiers["owner1"],
            "owner", TEST_MFA_B32["owner1"])
        other = create_editor_app(
            accounts=[account], db_path=Path(self.dir.name) / "drafts.sqlite3",
            encryption_key=self.key, https_origin="https://admin.example.test",
            session_ttl=120)
        async with TestClient(TestServer(other)) as second:
            status = await second.get(self.url + "/session",
                                      headers=self.headers("owner1"))
            self.assertEqual(status.status, 200)
            self.assertEqual((await status.json())["role"], "owner")
            draft = await second.get(self.url + "/draft", headers=self.headers("owner1"))
            self.assertEqual(draft.status, 200)
            deleted = await second.delete(self.url + "/session",
                                           headers=self.headers("owner1", csrf=True))
            self.assertEqual(deleted.status, 200)
        original = await self.client.get(self.url + "/draft", headers=self.headers("owner1"))
        self.assertEqual(original.status, 401)

    async def test_changed_role_invalidates_old_session_on_updated_instance(self):
        self.assertEqual((await self.login("owner1")).status, 200)
        demoted = create_editor_app(
            accounts=[AdminAccount(
                "owner1", self.verifiers["owner1"],
                "viewer", TEST_MFA_B32["owner1"])],
            db_path=Path(self.dir.name) / "drafts.sqlite3",
            encryption_key=self.key, https_origin="https://admin.example.test")
        async with TestClient(TestServer(demoted)) as second:
            status = await second.get(self.url + "/session",
                                      headers=self.headers("owner1"))
            self.assertEqual(status.status, 401)
            attempted = await second.post(
                self.url + "/proposals", headers=self.headers("owner1", csrf=True, revision=1))
            self.assertEqual(attempted.status, 401)
        # Updated worker deletes the shared token, so old workers also reject it.
        old = await self.client.get(self.url + "/session", headers=self.headers("owner1"))
        self.assertEqual(old.status, 401)

    async def test_removed_account_invalidates_shared_session(self):
        self.assertEqual((await self.login("owner1")).status, 200)
        removed = create_editor_app(
            accounts=[AdminAccount(
                "viewer1", self.verifiers["viewer1"],
                "viewer", TEST_MFA_B32["viewer1"])],
            db_path=Path(self.dir.name) / "drafts.sqlite3",
            encryption_key=self.key, https_origin="https://admin.example.test")
        async with TestClient(TestServer(removed)) as second:
            access = await second.get(self.url + "/session", headers=self.headers("owner1"))
            self.assertEqual(access.status, 401)
        old = await self.client.get(self.url + "/session", headers=self.headers("owner1"))
        self.assertEqual(old.status, 401)

    async def test_session_sqlite_failure_fails_closed(self):
        self.assertEqual((await self.login("viewer1")).status, 200)
        with patch.object(EncryptedDrafts, "touch_session",
                          side_effect=sqlite3.OperationalError("synthetic unavailable")):
            denied = await self.client.get(
                self.url + "/draft", headers=self.headers("viewer1"))
        self.assertEqual(denied.status, 503)
        # A failed logout must not return a false positive with a cleared cookie.
        with patch.object(EncryptedDrafts, "revoke_session",
                          side_effect=sqlite3.OperationalError("synthetic unavailable")):
            failed_logout = await self.client.delete(
                self.url + "/session", headers=self.headers("viewer1", csrf=True))
        self.assertEqual(failed_logout.status, 503)
        still = await self.client.get(self.url + "/session", headers=self.headers("viewer1"))
        self.assertEqual(still.status, 200)

    async def test_cross_host_authenticated_requests_fail(self):
        await self.login("viewer1")
        foreign = await self.client.get(self.url + "/draft",
            headers={**self.headers("viewer1"), "Host": "evil.example"})
        self.assertEqual(foreign.status, 403)
        foreign_write = await self.client.delete(self.url + "/session",
            headers={**self.headers("viewer1", csrf=True), "Host": "evil.example"})
        self.assertEqual(foreign_write.status, 403)

    def test_reject_duplicate_admin_totp_secrets(self):
        with self.assertRaises(ValueError):
            create_editor_app(accounts=[
                AdminAccount("owner1", password_verifier("strong-test-password"),
                             "owner", TEST_MFA_B32["owner1"]),
                AdminAccount("viewer1", password_verifier("strong-test-password"),
                             "viewer", TEST_MFA_B32["owner1"]),
            ], db_path=Path(self.dir.name) / "duplicate-seeds.sqlite3",
               encryption_key=self.key, https_origin="https://admin.example.test")

    def test_admin_mfa_mandatory_even_for_viewer(self):
        with self.assertRaises(ValueError):
            create_editor_app(accounts=[AdminAccount("viewer1",
                password_verifier("strong-test-password"), "viewer")],
                db_path=Path(self.dir.name) / "mfa.sqlite3",
                encryption_key=self.key, https_origin="https://admin.example.test")


if __name__ == "__main__":
    unittest.main()
