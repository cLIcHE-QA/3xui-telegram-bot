"""#887 D2d: ephemeral localhost Nginx TLS ingress and real edge rate tests.

No public network, no Bot API, no operator/VPS credentials. Self-signed TLS
certificate and fake upstream exist only under a temporary private directory.
"""
from __future__ import annotations

import asyncio
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


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "deploy/subpage-staging/nginx-d2d-staging.conf.example"
HOST = "staging.example.invalid"
ORIGIN = "https://" + HOST
START = "/api/subpage/v1/auth/standalone/start"
COMPLETE = "/api/subpage/v1/auth/standalone/complete"
ME = "/api/subpage/v1/standalone/me"


def tls_request(port: int, method: str, path: str, *,
                origin: str = ORIGIN, host: str = HOST, sni: str = HOST,
                source_ip: str = "127.0.0.1",
                body: bytes = b"", extra: dict[str, str] | None = None,
                ) -> tuple[int, dict[str, str], bytes]:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.verify_mode = ssl.CERT_NONE  # LOCAL SYNTHETIC TEST CERT ONLY.
    ctx.check_hostname = False
    headers = {
        "Host": host, "Origin": origin,
        "Content-Type": "application/json", "Content-Length": str(len(body)),
        "Connection": "close",
        **(extra or {}),
    }
    payload = (f"{method} {path} HTTP/1.1\r\n"
               + "".join(f"{k}: {v}\r\n" for k, v in headers.items())
               + "\r\n").encode("ascii") + body
    with socket.create_connection(("127.0.0.1", port), timeout=4,
                                  source_address=(source_ip, 0)) as raw:
        with ctx.wrap_socket(raw, server_hostname=sni) as secured:
            secured.settimeout(4)
            secured.sendall(payload)
            response = http.client.HTTPResponse(secured)
            response.begin()
            return response.status, dict(
                (k.lower(), v) for k, v in response.getheaders()), response.read()


@unittest.skipUnless(shutil.which("nginx") and shutil.which("openssl"),
                     "Nginx/OpenSSL unavailable; real TLS/edge verification PENDING")
class D2dStagingTlsEdgeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="d2d-staging-edge-")
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.root = root

        self.runner = web.AppRunner(web.Application(), access_log=None)
        async def echo(request):
            return web.json_response({
                "host": request.host,
                "origin": request.headers.get("Origin"),
                "xff": request.headers.get("X-Forwarded-For"),
                "xreal": request.headers.get("X-Real-IP"),
                "xfp": request.headers.get("X-Forwarded-Proto"),
                "xfh": request.headers.get("X-Forwarded-Host"),
                "forwarded": request.headers.get("Forwarded"),
                "authorization": request.headers.get("Authorization"),
            })
        for route in (START, COMPLETE,
                      "/api/subpage/v1/auth/standalone/cancel",
                      "/api/subpage/v1/auth/standalone/logout", ME):
            self.runner.app.router.add_route("*", route, echo)
        await self.runner.setup()
        self.addAsyncCleanup(self.runner.cleanup)

        backend = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            backend.bind(("127.0.0.1", 0))
            backend.listen(30)
            backend.setblocking(False)
            backend_port = backend.getsockname()[1]
            await web.SockSite(self.runner, backend).start()
        except BaseException:
            backend.close()
            raise

        cert, secret = root / "cert.pem", root / "key.pem"
        subprocess.run([
            shutil.which("openssl"), "req", "-x509", "-nodes", "-newkey",
            "rsa:2048", "-days", "1", "-subj", f"/CN={HOST}",
            "-keyout", str(secret), "-out", str(cert),
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=20, check=True)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", 0))
            self.port = probe.getsockname()[1]
        static = root / "dist"
        (static / "assets").mkdir(parents=True)
        (static / "index.html").write_text("<html>STAGING-SYNTHETIC</html>", encoding="utf-8")
        (static / "assets" / "app.js").write_text("/* synthetic */", encoding="utf-8")
        snippet = TEMPLATE.read_text(encoding="utf-8")
        replacements = (
            ("listen 443 ssl http2;", f"listen 127.0.0.1:{self.port} ssl http2;"),
            ("/etc/subpage-staging/tls/fullchain.pem", str(cert)),
            ("/etc/subpage-staging/tls/privkey.pem", str(secret)),
            ("root /srv/subpage-staging/dist;", f"root {static};"),
            ("http://127.0.0.1:8827;", f"http://127.0.0.1:{backend_port};"),
        )
        for old, new in replacements:
            if not snippet.count(old):
                raise AssertionError("Missing staging Nginx placeholder")
            snippet = snippet.replace(old, new)
        include = root / "include.conf"
        include.write_text(snippet, encoding="utf-8")
        config = root / "nginx.conf"
        config.write_text(
            f"pid {root / 'nginx.pid'};\nerror_log stderr warn;\n"
            "events { worker_connections 64; }\n"
            f"http {{ access_log off; include {include}; }}\n",
            encoding="utf-8",
        )
        nginx = shutil.which("nginx")
        check = subprocess.run([nginx, "-t", "-p", str(root) + "/", "-c", str(config)],
                               capture_output=True, timeout=12, check=False)
        self.assertEqual(check.returncode, 0,
                         "Synthetic staging Nginx syntax verification failed")
        stderr = (root / "nginx-stderr.txt").open("wb")
        self.addCleanup(stderr.close)
        self.proc = subprocess.Popen(
            [nginx, "-p", str(root) + "/", "-c", str(config),
             "-g", "daemon off;"], stdout=subprocess.DEVNULL, stderr=stderr,
        )
        def stop():
            if self.proc.poll() is None:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
                    self.proc.wait(timeout=5)
        self.addCleanup(stop)

        limit = time.monotonic() + 5
        while time.monotonic() < limit:
            self.assertIsNone(self.proc.poll(), "Synthetic staging Nginx exited")
            try:
                with socket.create_connection(("127.0.0.1", self.port), timeout=.4):
                    break
            except OSError:
                await asyncio.sleep(.05)
        else:
            self.fail("Synthetic staging Nginx did not start")

    async def request(self, method="POST", path=START, **kwargs):
        return await asyncio.to_thread(tls_request, self.port, method, path, **kwargs)

    async def test_tls_only_known_paths_and_security_headers(self):
        status, headers, body = await self.request("GET", "/", body=b"")
        self.assertEqual(status, 200)
        self.assertIn(b"STAGING-SYNTHETIC", body)
        self.assertEqual(headers.get("cache-control"), "no-store")
        self.assertEqual(headers.get("referrer-policy"), "no-referrer")
        self.assertIn("frame-ancestors 'none'", headers.get("content-security-policy", ""))
        status, _, _ = await self.request("GET", "/assets/app.js")
        self.assertEqual(status, 200)
        for path in ("/compat/test", "/api/subpage/v1/auth/standalone/approve",
                     "/admin/subpage/api/session", "/.env", "/client-icons/lib.svg"):
            with self.subTest(path=path):
                status, _, _ = await self.request("GET", path)
                self.assertEqual(status, 404)

    async def test_host_sni_and_excessive_bodies_fail_closed(self):
        for headers in ({"host": "attacker.example.invalid"},
                        {"sni": "attacker.example.invalid"}):
            with self.subTest(headers=headers):
                try:
                    status, _, _ = await self.request(**headers)
                except (OSError, ssl.SSLError, http.client.HTTPException):
                    continue  # Nginx return 444 closes before HTTP response.
                self.assertNotEqual(status, 200)
        status, _, _ = await self.request(body=b"x" * 3000)
        self.assertEqual(status, 413)

    async def test_proxy_headers_scrubbed_before_backend(self):
        status, headers, body = await self.request(
            extra={"X-Forwarded-For": "203.0.113.111",
                   "X-Real-IP": "203.0.113.222",
                   "X-Forwarded-Proto": "http",
                   "X-Forwarded-Host": "attacker.example.invalid",
                   "Forwarded": "for=203.0.113.55;proto=http",
                   "Authorization": "Bearer synthetic-forged"},
            body=b"{}",
        )
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(data["host"], HOST)
        self.assertEqual(data["origin"], ORIGIN)
        self.assertEqual(data["xff"], "127.0.0.1")
        self.assertEqual(data["xreal"], "127.0.0.1")
        self.assertEqual(data["xfp"], "https")
        self.assertEqual(data["xfh"], HOST)
        self.assertIn(data["forwarded"], (None, ""))
        self.assertIn(data["authorization"], (None, ""))
        self.assertEqual(headers.get("cache-control"), "no-store")

    async def test_rate_limits_real_nginx_429_and_second_tcp_peer(self):
        results = []
        for _ in range(8):
            status, _, _ = await self.request(body=b"{}")
            results.append(status)
        self.assertEqual(results[0], 200)
        self.assertIn(429, results[3:])
        # A browser-supplied fake XFF cannot bypass same TCP-peer budget.
        status, _, _ = await self.request(
            extra={"X-Forwarded-For": "198.51.100.55"}, body=b"{}")
        self.assertEqual(status, 429)
        # Distinct synthetic loopback peer must not inherit the other bucket.
        status, _, _ = await self.request(
            source_ip="127.0.0.2", body=b"{}",
            extra={"X-Forwarded-For": "127.0.0.1"})
        self.assertEqual(status, 200)
