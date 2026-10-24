"""#887: реальный D1b aiohttp API за неактивным Nginx TLS edge на localhost.

Полностью синтетические учетные записи, MFA, Fernet key, SQLite и сертификат.
Никакого VPS, production credentials, публикации или внешних сетевых запросов.
"""
from __future__ import annotations

import asyncio
import base64
import http.client
import json
import shutil
import socket
import ssl
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from aiohttp import web
from cryptography.fernet import Fernet

from subscription_page_admin import (
    COOKIE, AdminAccount, _totp_at, create_editor_app, password_verifier,
)


ROOT = Path(__file__).resolve().parents[1]
NGINX_TEMPLATE = ROOT / "deploy/subpage-admin/nginx-d1b-admin.conf.example"
DOMAIN = "admin.example.invalid"
ORIGIN = "https://" + DOMAIN
API = "/admin/subpage/api"
PASSWORD = "synthetic-admin-password-for-887"
SEEDS = {
    "owner1": b"test owner mfa seed!!",
    "editor1": b"test editor mfa seed!",
    "viewer1": b"test viewer mfa seed!",
}


def synthetic_config() -> dict:
    """Небольшая полноценная схема v1 без пользовательских URL/ключей."""
    localized = lambda s: {lang: s + "-" + lang for lang in ("en", "ru", "zh", "fa", "fr")}
    return {
        "locales": ["en", "ru", "zh", "fa", "fr"], "version": "1",
        "uiConfig": {"subscriptionInfoBlockType": "expanded",
                     "installationGuidesBlockType": "cards"},
        "platforms": {"ios": {
            "displayName": localized("iOS"), "svgIconKey": "AppleIcon",
            "apps": [{"name": "Synthetic", "featured": False,
                      "svgIconKey": "AppleIcon", "blocks": [{
                          "title": localized("Install"),
                          "description": localized("Only synthetic"),
                          "svgIconKey": "Plus", "svgIconColor": "#18a5f9",
                          "buttons": []}]}],
        }},
        "svgLibrary": {"Demo": '<svg xmlns="http://www.w3.org/2000/svg"/>'},
        "baseSettings": {"metaTitle": "DEMO", "metaDescription": "Synthetic",
                         "hideGetLinkButton": False, "showConnectionKeys": False},
        "baseTranslations": {"getLink": localized("Get")},
        "brandingSettings": {"title": "Synthetic", "logoUrl": "", "supportUrl": ""},
    }


def https_request(port: int, method: str, path: str, *,
                  headers: dict[str, str] | None = None,
                  payload: dict | None = None) -> tuple[int, dict[str, str], bytes]:
    """Sync HTTPS клиент только localhost; вызывается через asyncio.to_thread."""
    # Исключение проверки self-signed certificate применяется ТОЛЬКО к
    # синтетическому сертификату этого одноразового теста, не к runtime.
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    tls.check_hostname = False
    tls.verify_mode = ssl.CERT_NONE
    body = json.dumps(payload, separators=(",", ":")).encode() if payload is not None else b""
    request_headers = {
        "Host": DOMAIN, "Connection": "close",
        **(headers or {}),
    }
    if payload is not None:
        request_headers["Content-Type"] = "application/json"
        request_headers["Content-Length"] = str(len(body))
    elif method in ("POST", "PUT", "DELETE"):
        request_headers["Content-Length"] = "0"
    lines = [f"{method} {path} HTTP/1.1"]
    lines.extend(f"{name}: {value}" for name, value in request_headers.items())
    message = "\r\n".join(lines).encode("ascii") + b"\r\n\r\n" + body
    with socket.create_connection(("127.0.0.1", port), timeout=4) as raw:
        with tls.wrap_socket(raw, server_hostname=DOMAIN) as secured:
            secured.settimeout(4)
            secured.sendall(message)
            response = http.client.HTTPResponse(secured)
            response.begin()
            return (response.status,
                    {name.lower(): value for name, value in response.getheaders()},
                    response.read())


@unittest.skipUnless(shutil.which("nginx") and shutil.which("openssl"),
                     "Nginx/OpenSSL недоступны; full TLS→real API check PENDING")
class D1bRealAdminHttpsTests(unittest.IsolatedAsyncioTestCase):
    """Проверки через настоящее TLS соединение и действительный D1b API."""

    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="d1b-api-edge-synthetic-")
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)  # TemporaryDirectory: 0700.
        self.password = PASSWORD
        self.accounts = [
            AdminAccount(user, password_verifier(PASSWORD), role,
                         base64.b32encode(SEEDS[user]).decode("ascii"))
            for user, role in (("owner1", "owner"), ("editor1", "editor"),
                               ("viewer1", "viewer"))
        ]
        app = create_editor_app(
            accounts=self.accounts, db_path=root / "drafts.sqlite3",
            encryption_key=Fernet.generate_key(),
            https_origin=ORIGIN, session_ttl=120)
        self.runner = web.AppRunner(app, access_log=None, handle_signals=False)
        await self.runner.setup()
        self.addAsyncCleanup(self.runner.cleanup)

        backend_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            backend_socket.bind(("127.0.0.1", 0))
            backend_socket.listen(100)
            backend_socket.setblocking(False)
            self.backend_port = backend_socket.getsockname()[1]
            self.site = web.SockSite(self.runner, backend_socket)
            await self.site.start()
        except BaseException:
            backend_socket.close()
            raise

        cert, private = root / "cert.pem", root / "key.pem"
        subprocess.run(
            [shutil.which("openssl"), "req", "-x509", "-nodes", "-newkey",
             "rsa:2048", "-days", "1", "-subj", f"/CN={DOMAIN}",
             "-keyout", str(private), "-out", str(cert)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=20, check=True)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", 0))
            self.port = probe.getsockname()[1]
        dist = root / "dist"
        dist.mkdir()
        (dist / "admin.html").write_text("<html>synthetic admin</html>", encoding="utf-8")
        # Условно заменяются только три location-specific пути и два порта.
        snippet = NGINX_TEMPLATE.read_text(encoding="utf-8")
        replacements = (
            ("listen 443 ssl http2;", f"listen 127.0.0.1:{self.port} ssl http2;"),
            ("/etc/d1b-admin/tls/fullchain.pem", str(cert)),
            ("/etc/d1b-admin/tls/privkey.pem", str(private)),
            ("root /srv/d1b-subscription-editor/dist;", f"root {dist};"),
            ("proxy_pass http://127.0.0.1:8817;",
             f"proxy_pass http://127.0.0.1:{self.backend_port};"),
        )
        for old, new in replacements:
            if snippet.count(old) != 1:
                raise AssertionError("Изменился контракт тестового Nginx-шаблона")
            snippet = snippet.replace(old, new)
        include_file = root / "include.conf"
        include_file.write_text(snippet, encoding="utf-8")
        config_file = root / "nginx.conf"
        config_file.write_text(
            f"pid {root / 'nginx.pid'};\nerror_log stderr warn;\n"
            "events { worker_connections 64; }\n"
            f"http {{ access_log off; include {include_file}; }}\n",
            encoding="utf-8")
        nginx = shutil.which("nginx")
        syntax = subprocess.run(
            [nginx, "-t", "-p", str(root) + "/", "-c", str(config_file)],
            capture_output=True, timeout=12, check=False)
        self.assertEqual(syntax.returncode, 0, "Synthetic nginx -t failed")
        # Только ephemeral logfile в private temp-dir, НЕ CI stdout/artifact.
        error_stream = (root / "nginx-stderr.txt").open("wb")
        self.addCleanup(error_stream.close)
        self.proc = subprocess.Popen(
            [nginx, "-p", str(root) + "/", "-c", str(config_file),
             "-g", "daemon off;"], stdout=subprocess.DEVNULL, stderr=error_stream)

        def stop_nginx():
            if self.proc.poll() is None:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
                    self.proc.wait(timeout=5)

        self.addCleanup(stop_nginx)
        ready_until = time.monotonic() + 5
        while time.monotonic() < ready_until:
            self.assertIsNone(self.proc.poll(), "Synthetic Nginx exited unexpectedly")
            try:
                with socket.create_connection(("127.0.0.1", self.port), timeout=0.3):
                    break
            except OSError:
                await asyncio.sleep(0.05)
        else:
            self.fail("Synthetic Nginx did not open its temporary loopback port")

    async def request(self, method: str, path: str, **kwargs):
        return await asyncio.to_thread(https_request, self.port, method, API + path, **kwargs)

    def otp(self, username: str) -> str:
        return _totp_at(SEEDS[username], int(time.time() // 30))

    async def login(self, username: str) -> tuple[str, str]:
        status, headers, body = await self.request(
            "POST", "/session",
            headers={"Origin": ORIGIN},
            payload={"username": username, "password": PASSWORD,
                     "otp": self.otp(username)})
        self.assertEqual(status, 200)
        cookie_line = headers.get("set-cookie", "")
        self.assertTrue(cookie_line.startswith(COOKIE + "="))
        self.assertIn("Secure", cookie_line)
        self.assertIn("HttpOnly", cookie_line)
        self.assertIn("SameSite=Strict", cookie_line)
        data = json.loads(body)
        self.assertEqual(data["username"], username)
        self.assertEqual(data["role"], next(a.role for a in self.accounts if a.username == username))
        self.assertNotIn("password", data)
        return cookie_line.split(";", 1)[0], data["csrfToken"]

    @staticmethod
    def headers(cookie: str, csrf: str | None = None, etag: str | None = None,
                *, origin: str = ORIGIN) -> dict[str, str]:
        headers = {"Origin": origin, "Cookie": cookie}
        if csrf is not None:
            headers["X-CSRF-Token"] = csrf
        if etag is not None:
            headers["If-Match"] = etag
        return headers

    async def test_guest_foreign_origin_mfa_and_cors_denied(self):
        for path in ("/draft", "/history", "/session"):
            with self.subTest(guest_path=path):
                status, headers, _ = await self.request("GET", path)
                self.assertEqual(status, 401)
                self.assertEqual(headers.get("cache-control"), "no-store")
                self.assertNotIn("access-control-allow-origin", headers)
        status, _, _ = await self.request(
            "GET", "/draft", headers={"Authorization": "Bearer synthetic-subscription-token"})
        self.assertEqual(status, 401)
        credentials = {"username": "owner1", "password": PASSWORD, "otp": self.otp("owner1")}
        no_origin, _, _ = await self.request("POST", "/session", payload=credentials)
        self.assertEqual(no_origin, 403)
        foreign, _, _ = await self.request(
            "POST", "/session", payload=credentials,
            headers={"Origin": "https://untrusted.example",
                     "X-Forwarded-Host": DOMAIN,
                     "X-Forwarded-Proto": "https",
                     "X-Forwarded-For": "127.0.0.1"})
        self.assertEqual(foreign, 403)
        no_mfa, _, _ = await self.request(
            "POST", "/session", headers={"Origin": ORIGIN},
            payload={"username": "owner1", "password": PASSWORD})
        self.assertEqual(no_mfa, 401)
        preflight, response_headers, _ = await self.request(
            "OPTIONS", "/draft", headers={"Origin": "https://untrusted.example",
                                           "Access-Control-Request-Method": "PUT"})
        self.assertEqual(preflight, 405)
        self.assertNotIn("access-control-allow-origin", response_headers)
        for path in ("/publish", "/rollback", "/../../compat/synthetic"):
            status, _, _ = await self.request("POST", path)
            self.assertIn(status, (403, 404), path)
        direct_compat = await asyncio.to_thread(
            https_request, self.port, "GET", "/compat/synthetic")
        self.assertEqual(direct_compat[0], 404)

    async def test_real_roles_csrf_revision_and_proposal(self):
        owner_cookie, owner_csrf = await self.login("owner1")
        editor_cookie, editor_csrf = await self.login("editor1")
        viewer_cookie, viewer_csrf = await self.login("viewer1")
        status, headers, data = await self.request(
            "GET", "/draft", headers={"Cookie": viewer_cookie})
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("etag"), '"rev-0"')
        self.assertIsNone(json.loads(data)["config"])

        blocked, _, _ = await self.request(
            "PUT", "/draft", headers=self.headers(viewer_cookie, viewer_csrf, '"rev-0"'),
            payload={"config": synthetic_config()})
        self.assertEqual(blocked, 403)
        no_csrf, _, _ = await self.request(
            "PUT", "/draft", headers=self.headers(editor_cookie, etag='"rev-0"'),
            payload={"config": synthetic_config()})
        self.assertEqual(no_csrf, 403)
        wrong_csrf, _, _ = await self.request(
            "PUT", "/draft",
            headers=self.headers(editor_cookie, "wrong-csrf", '"rev-0"'),
            payload={"config": synthetic_config()})
        self.assertEqual(wrong_csrf, 403)
        cross_origin, _, _ = await self.request(
            "PUT", "/draft",
            headers=self.headers(editor_cookie, editor_csrf, '"rev-0"',
                                 origin="https://untrusted.example"),
            payload={"config": synthetic_config()})
        self.assertEqual(cross_origin, 403)
        no_revision, _, _ = await self.request(
            "PUT", "/draft", headers=self.headers(editor_cookie, editor_csrf),
            payload={"config": synthetic_config()})
        self.assertEqual(no_revision, 428)
        headers = self.headers(editor_cookie, editor_csrf, '"rev-0"')
        headers.update({"X-Forwarded-For": "203.0.113.77",
                        "X-Forwarded-Host": "untrusted.example",
                        "X-Forwarded-Proto": "http"})
        saved, response_headers, payload = await self.request(
            "PUT", "/draft", headers=headers, payload={"config": synthetic_config()})
        self.assertEqual(saved, 200)
        self.assertEqual(json.loads(payload)["revision"], 1)
        self.assertEqual(response_headers.get("cache-control"), "no-store")
        stale, _, _ = await self.request(
            "PUT", "/draft", headers=self.headers(editor_cookie, editor_csrf, '"rev-0"'),
            payload={"config": synthetic_config()})
        self.assertEqual(stale, 409)
        current, current_headers, content = await self.request(
            "GET", "/draft", headers={"Cookie": viewer_cookie})
        self.assertEqual(current, 200)
        self.assertEqual(current_headers.get("etag"), '"rev-1"')
        self.assertEqual(json.loads(content)["config"], synthetic_config())
        wrong_role, _, _ = await self.request(
            "POST", "/proposals", headers=self.headers(editor_cookie, editor_csrf, '"rev-1"'))
        self.assertEqual(wrong_role, 403)
        proposed, _, body = await self.request(
            "POST", "/proposals", headers=self.headers(owner_cookie, owner_csrf, '"rev-1"'))
        self.assertEqual(proposed, 202)
        self.assertEqual(json.loads(body)["state"], "pending_manual_review")
        for path in ("/publish", "/rollback"):
            unavailable, _, _ = await self.request(
                "POST", path, headers=self.headers(owner_cookie, owner_csrf))
            self.assertEqual(unavailable, 404)

    async def test_otp_replay_and_revocation_through_tls(self):
        owner_cookie, owner_csrf = await self.login("owner1")
        # Повторный пароль+TOTP через ТОТ ЖЕ HTTPS origin: не даёт 2-ю сессию.
        replay, _, _ = await self.request(
            "POST", "/session", headers={"Origin": ORIGIN},
            payload={"username": "owner1", "password": PASSWORD,
                     "otp": self.otp("owner1")})
        self.assertEqual(replay, 401)
        owner_alive, _, _ = await self.request(
            "GET", "/session", headers={"Cookie": owner_cookie})
        self.assertEqual(owner_alive, 200)
        editor_cookie, editor_csrf = await self.login("editor1")
        viewer_cookie, viewer_csrf = await self.login("viewer1")

        no_csrf, _, _ = await self.request(
            "POST", "/sessions/revoke",
            headers=self.headers(editor_cookie), payload={"username": "viewer1"})
        self.assertEqual(no_csrf, 403)
        not_owner, _, _ = await self.request(
            "POST", "/sessions/revoke",
            headers=self.headers(editor_cookie, editor_csrf),
            payload={"username": "viewer1"})
        self.assertEqual(not_owner, 403)
        owner_revoked, _, _ = await self.request(
            "POST", "/sessions/revoke",
            headers=self.headers(owner_cookie, owner_csrf),
            payload={"username": "viewer1"})
        self.assertEqual(owner_revoked, 200)
        invalidated, _, _ = await self.request(
            "GET", "/draft", headers={"Cookie": viewer_cookie})
        self.assertEqual(invalidated, 401)
        editor_alive, _, _ = await self.request(
            "GET", "/session", headers={"Cookie": editor_cookie})
        self.assertEqual(editor_alive, 200)
        without_token, _, _ = await self.request(
            "DELETE", "/session", headers=self.headers(owner_cookie))
        self.assertEqual(without_token, 403)
        logged_out, headers, _ = await self.request(
            "DELETE", "/session", headers=self.headers(owner_cookie, owner_csrf))
        self.assertEqual(logged_out, 200)
        self.assertIn("Max-Age=0", headers.get("set-cookie", ""))
        no_session, _, _ = await self.request(
            "GET", "/draft", headers={"Cookie": owner_cookie})
        self.assertEqual(no_session, 401)


if __name__ == "__main__":
    unittest.main()
