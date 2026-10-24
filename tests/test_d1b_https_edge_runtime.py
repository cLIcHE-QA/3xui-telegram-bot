"""#887: изолированный TLS/HTTP smoke неактивного D1b Nginx-шаблона."""
from __future__ import annotations

import http.client
import queue
import re
import shutil
import socket
import ssl
import subprocess
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "deploy/subpage-admin/nginx-d1b-admin.conf.example"
CATALOG = ROOT / "web/subscription-page/src/staticSvgPaths.ts"
DOMAIN = "admin.example.invalid"


class SyntheticAdminBackend(BaseHTTPRequestHandler):
    """Без реальных пользователей и секретов; фиксирует только заголовки запроса."""

    def do_GET(self):
        self.respond()

    def do_POST(self):
        self.respond()

    def respond(self):
        size = int(self.headers.get("Content-Length", "0"))
        if size > 1024:
            self.send_error(413)
            return
        self.rfile.read(size)
        self.server.records.put({k.lower(): v for k, v in self.headers.items()})
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"synthetic":true}')

    def log_message(self, *_args):
        pass  # Не журналировать даже тестовые URL/заголовки.


@unittest.skipUnless(shutil.which("nginx") and shutil.which("openssl"),
                     "Для TLS smoke нужны nginx и openssl; static contract запускается отдельно")
class D1bSyntheticHttpsRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="d1b-https-synthetic-")
        cls.addClassCleanup(cls.temp.cleanup)
        root = Path(cls.temp.name)
        cls.site = root / "dist"
        cls.site.mkdir()
        (cls.site / "assets").mkdir()
        (cls.site / "admin.html").write_text("<html>Только синтетический редактор</html>", encoding="utf-8")
        (cls.site / "index.html").write_text("Не является admin-страницей", encoding="utf-8")
        (cls.site / "assets" / "bundle.js").write_text("/* synthetic */", encoding="utf-8")
        cls.icons = re.findall(r':\s*"(/client-icons/[A-Za-z0-9_/-]+\.svg)"',
                               CATALOG.read_text(encoding="utf-8"))
        # Имена взяты из канонического каталога, все файлы ответа синтетические.
        if len(cls.icons) != len(set(cls.icons)) or not cls.icons:
            raise AssertionError("Некорректный synthetic catalog SVG")
        for path in cls.icons:
            dest = cls.site / path.lstrip("/")
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text('<svg xmlns="http://www.w3.org/2000/svg"></svg>', encoding="utf-8")
        for path in ("client-icons/INCY-LICENSE.txt", "client-icons/incy-monochrome.svg",
                     "client-icons/library/.hidden.svg", "client-icons/library/Happ.svg.map",
                     "compat/secret", "private.txt"):
            dest = cls.site / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text("should never be served", encoding="utf-8")

        cls.records = queue.Queue()
        cls.backend = ThreadingHTTPServer(("127.0.0.1", 0), SyntheticAdminBackend)
        cls.backend.records = cls.records
        worker = threading.Thread(target=cls.backend.serve_forever, daemon=True)
        worker.start()

        def stop_backend():
            cls.backend.shutdown()
            cls.backend.server_close()
            worker.join(timeout=3)

        cls.addClassCleanup(stop_backend)
        cert, key = root / "ephemeral.crt", root / "ephemeral.key"
        subprocess.run([shutil.which("openssl"), "req", "-x509", "-nodes",
                        "-newkey", "rsa:2048", "-days", "1", "-subj", f"/CN={DOMAIN}",
                        "-keyout", str(key), "-out", str(cert)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", 0))
            cls.port = probe.getsockname()[1]
        original = EXAMPLE.read_text(encoding="utf-8")
        pairs = (
            ("listen 443 ssl http2;", f"listen 127.0.0.1:{cls.port} ssl http2;"),
            ("/etc/d1b-admin/tls/fullchain.pem", str(cert)),
            ("/etc/d1b-admin/tls/privkey.pem", str(key)),
            ("root /srv/d1b-subscription-editor/dist;", f"root {cls.site};"),
            ("proxy_pass http://127.0.0.1:8817;",
             f"proxy_pass http://127.0.0.1:{cls.backend.server_port};"),
        )
        for old, new in pairs:
            if original.count(old) != 1:
                raise AssertionError("Неожиданная структура шаблона Nginx")
            original = original.replace(old, new)
        snippet = root / "nginx-snippet.conf"
        snippet.write_text(original, encoding="utf-8")
        config = root / "nginx.conf"
        config.write_text(
            f"pid {root / 'nginx.pid'};\nerror_log stderr warn;\n"
            "events { worker_connections 64; }\n"
            "http { access_log off; "
            "types { text/html html; image/svg+xml svg; application/javascript js; } "
            f"include {snippet}; }}\n", encoding="utf-8")
        nginx = shutil.which("nginx")
        checked = subprocess.run([nginx, "-t", "-p", str(root) + "/", "-c", str(config)],
                                 capture_output=True, timeout=12, check=False)
        if checked.returncode:
            raise AssertionError("Synthetic Nginx parser rejected the isolated template")
        stream = (root / "nginx-stderr.txt").open("wb")
        cls.addClassCleanup(stream.close)
        cls.proc = subprocess.Popen([nginx, "-p", str(root) + "/", "-c", str(config),
                                     "-g", "daemon off;"], stdout=subprocess.DEVNULL,
                                    stderr=stream)

        def stop_nginx():
            if cls.proc.poll() is None:
                cls.proc.terminate()
                try:
                    cls.proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    cls.proc.kill()
                    cls.proc.wait(timeout=5)

        cls.addClassCleanup(stop_nginx)
        limit = time.monotonic() + 4
        while time.monotonic() < limit:
            if cls.proc.poll() is not None:
                raise AssertionError("Synthetic Nginx завершился до готовности")
            try:
                with socket.create_connection(("127.0.0.1", cls.port), timeout=0.3):
                    break
            except OSError:
                time.sleep(0.05)
        else:
            raise AssertionError("Synthetic Nginx не открыл временный loopback-порт")

    @classmethod
    def https_request(cls, path: str, *, host: str = DOMAIN, sni: str | None = DOMAIN,
                      method: str = "GET", headers: dict | None = None):
        # Исключительно self-signed fixture: проверка сертификата отключена
        # внутри этого теста, НЕ в production request helpers.
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        with socket.create_connection(("127.0.0.1", cls.port), timeout=2) as raw:
            with context.wrap_socket(raw, server_hostname=sni) as conn:
                conn.settimeout(2)
                lines = [f"{method} {path} HTTP/1.1", f"Host: {host}", "Connection: close"]
                lines.extend(f"{key}: {value}" for key, value in (headers or {}).items())
                if method == "POST":
                    lines.extend(["Content-Type: application/json", "Content-Length: 2"])
                data = "\r\n".join(lines).encode("ascii") + b"\r\n\r\n"
                if method == "POST":
                    data += b"{}"
                try:
                    conn.sendall(data)
                    response = http.client.HTTPResponse(conn)
                    response.begin()
                    return response.status, {k.lower(): v for k, v in response.getheaders()}, response.read()
                except (http.client.RemoteDisconnected, ConnectionResetError, ssl.SSLEOFError):
                    return None  # Nginx return 444 закрывает соединение без HTTP status.

    def test_assets_and_disallowed_routes_over_real_synthetic_tls(self):
        for uri in ["/admin.html", "/assets/bundle.js", *self.icons]:
            with self.subTest(uri=uri):
                response = self.https_request(uri)
                self.assertIsNotNone(response, uri)
                status, headers, body = response
                self.assertEqual(status, 200, uri)
                self.assertTrue(body, uri)
                self.assertEqual(headers.get("cache-control"), "no-store")
                self.assertEqual(headers.get("x-frame-options"), "DENY")
                self.assertIn("frame-ancestors 'none'", headers.get("content-security-policy", ""))
                self.assertIn("nosniff", headers.get("x-content-type-options", ""))
                if uri.endswith(".svg"):
                    self.assertTrue(headers.get("content-type", "").startswith("image/svg+xml"), uri)
        for uri in ("/", "/index.html", "/private.txt", "/compat/secret",
                    "/client-icons/INCY-LICENSE.txt", "/client-icons/incy-monochrome.svg",
                    "/client-icons/library/.hidden.svg", "/client-icons/library/Happ.svg.map",
                    "/client-icons/library/Happ.svg/other"):
            with self.subTest(denied=uri):
                result = self.https_request(uri)
                self.assertIsNotNone(result)
                self.assertEqual(result[0], 404, uri)
                self.assertEqual(result[1].get("cache-control"), "no-store")

    def test_host_sni_rejections_and_proxy_headers(self):
        for host, sni in (("invalid.example", DOMAIN),
                          (DOMAIN, "invalid.example"), (DOMAIN, None)):
            with self.subTest(host=host, sni=sni):
                self.assertIsNone(self.https_request("/admin.html", host=host, sni=sni))
        status, _headers, body = self.https_request(
            "/admin/subpage/api/draft", headers={
                "Origin": "https://untrusted.example",
                "X-Forwarded-For": "203.0.113.77",
                "X-Forwarded-Host": "untrusted.example",
                "X-Forwarded-Proto": "http",
            })
        self.assertEqual(status, 200)
        self.assertIn(b"synthetic", body)
        forwarded = self.records.get(timeout=2)
        self.assertEqual(forwarded["host"], DOMAIN)
        self.assertEqual(forwarded["origin"], "https://untrusted.example")
        self.assertEqual(forwarded["x-forwarded-for"], "127.0.0.1")
        self.assertEqual(forwarded["x-forwarded-host"], DOMAIN)
        self.assertEqual(forwarded["x-forwarded-proto"], "https")

    def test_login_requests_eventually_receive_429(self):
        statuses = [self.https_request("/admin/subpage/api/session", method="POST")[0]
                    for _ in range(9)]
        self.assertIn(200, statuses)
        self.assertIn(429, statuses)


if __name__ == "__main__":
    unittest.main()
