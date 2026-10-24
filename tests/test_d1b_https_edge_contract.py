"""D1b #887 HTTPS edge design contract (example config, NOT deployed)."""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


EXAMPLE = (Path(__file__).resolve().parents[1] / "deploy" /
           "subpage-admin" / "nginx-d1b-admin.conf.example")


class D1bHttpsEdgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conf = EXAMPLE.read_text(encoding="utf-8")

    def test_tls_is_mandatory_and_example_domain_unusable(self):
        s = self.conf
        self.assertIn("listen 443 ssl;", s)
        self.assertIn("http2 on;", s)
        self.assertNotRegex(s, r"(?m)^\s*listen 80\b")
        self.assertNotRegex(s, r"(?m)^\s*listen .*default_server")
        self.assertIn("server_name admin.example.invalid;", s)
        self.assertIn('if ($ssl_server_name != "admin.example.invalid") { return 444; }', s)
        self.assertIn('if ($host != "admin.example.invalid") { return 444; }', s)
        self.assertIn("ssl_protocols TLSv1.2 TLSv1.3;", s)
        self.assertIn("ssl_session_tickets off;", s)
        self.assertIn("ssl_certificate_key /etc/d1b-admin/tls/privkey.pem;", s)

    def test_only_loopback_api_and_explicit_editor_assets(self):
        s = self.conf
        self.assertIn("proxy_pass http://127.0.0.1:8817;", s)
        self.assertNotRegex(s, r"proxy_pass\s+https?://(0\.0\.0\.0|\[::\]|localhost|\$)")
        self.assertIn("location ^~ /admin/subpage/api/ {", s)
        self.assertIn("location = /admin.html {", s)
        self.assertIn("location ^~ /assets/ {", s)
        self.assertIn("location / {\n        return 404;", s)
        self.assertNotIn("location /compat/", s)
        self.assertNotIn("proxy_pass http://0.0.0.0", s)
        self.assertIn("autoindex off;", s)

    def test_rate_limit_and_client_origin_are_not_forged(self):
        s = self.conf
        self.assertIn('"POST:/admin/subpage/api/session" $binary_remote_addr;', s)
        self.assertIn("limit_req_zone $d1b_login_key zone=d1b_login:10m rate=5r/m;", s)
        self.assertIn("limit_req zone=d1b_login burst=4 nodelay;", s)
        self.assertIn("limit_req zone=d1b_api burst=20 nodelay;", s)
        self.assertIn("limit_req_status 429;", s)
        self.assertIn("limit_conn d1b_connection 5;", s)
        self.assertIn("proxy_set_header Host admin.example.invalid;", s)
        self.assertIn("proxy_set_header X-Forwarded-For $remote_addr;", s)
        self.assertIn("proxy_set_header X-Forwarded-Proto https;", s)
        self.assertNotRegex(s, r"(?m)^\s*proxy_set_header\s+Origin\b")
        self.assertNotRegex(s, r"(?m)^\s*set_real_ip_from\b")
        self.assertNotIn("Access-Control-Allow-Origin: *", s)

    def test_protects_html_cookie_transport_and_sensitive_responses(self):
        s = self.conf
        for marker in (
            'add_header Cache-Control "no-store" always;',
            'add_header X-Frame-Options "DENY" always;',
            'add_header X-Content-Type-Options "nosniff" always;',
            'add_header Strict-Transport-Security "max-age=300" always;',
            "frame-ancestors 'none'",
            "object-src 'none'",
            "connect-src 'self'",
            "access_log off;",
        ):
            self.assertIn(marker, s)
        self.assertNotIn("ssl_certificate -----BEGIN", s)
        self.assertNotRegex(s, r"(?m)^\s*proxy_cache(_valid)?\s")
        self.assertNotRegex(s, r"(?m)^\s*add_header\s+Access-Control-Allow-Origin\b")

    @unittest.skipUnless(shutil.which("nginx") and shutil.which("openssl"),
                         "nginx/openssl недоступны: проверяется статический контракт")
    def test_nginx_syntax_with_ephemeral_synthetic_certificate(self):
        # A syntax check is not a production network, TLS chain or DNS test.
        # Cert/key never leave this synthetic temporary directory.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cert, key = root / "chain.pem", root / "key.pem"
            subprocess.run([
                shutil.which("openssl"), "req", "-x509", "-nodes", "-newkey",
                "rsa:2048", "-days", "1", "-subj",
                "/CN=admin.example.invalid", "-keyout", str(key),
                "-out", str(cert)
            ], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
               check=True, timeout=20)
            conf = self.conf.replace(
                "/etc/d1b-admin/tls/fullchain.pem", str(cert)).replace(
                "/etc/d1b-admin/tls/privkey.pem", str(key))
            snippet = root / "snippet.conf"
            snippet.write_text(conf, encoding="utf-8")
            final = root / "nginx.conf"
            final.write_text(
                "pid " + str(root / "nginx.pid") + ";\n"
                "error_log stderr notice;\n"
                "events { worker_connections 16; }\n"
                "http { include " + str(snippet) + "; }\n",
                encoding="utf-8")
            check = subprocess.run(
                [shutil.which("nginx"), "-t", "-p", str(root) + "/",
                 "-c", str(final)],
                capture_output=True, text=True, timeout=12, check=False)
            # Only synthetic ephemeral temp path and parser diagnostic;
            # never include a certificate, private key or request payload.
            detail = check.stderr.replace(str(root), "<synthetic-root>").strip()
            self.assertEqual(check.returncode, 0,
                             "nginx synthetic syntax validation failed: " + detail)


if __name__ == "__main__":
    unittest.main()
