"""#887 D2e: no real DNS, TLS, Bot API or staging device traffic in CI."""
from __future__ import annotations

import io
import json
import socket
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import subscription_page_staging_preflight as preflight
from subscription_page_staging import StagingConfig


class StagingEdgePreflightTests(unittest.TestCase):
    ORIGIN = "https://staging.example.org"
    TLS_FINGERPRINT = "a" * 64

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="staging-edge-offline-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root.chmod(0o700)
        self.config_file = self.root / "staging-config.json"
        self.template = {
            "mode": "isolated-staging",
            "enabled": False,
            "edge_reviewed": True,
            "https_origin": self.ORIGIN,
            "bot_token_file": str(self.root / "staging-bot.token"),
            "expected_bot_id": 900001,
            "expected_bot_username": "StagingExampleBot",
            "pilot_ids": [100001],
            "sqlite_path": str(self.root / "standalone-pilot.sqlite3"),
            "loopback_port": 8827,
        }
        self.write_config()

    def write_config(self, **overrides):
        self.config_file.write_text(
            json.dumps(self.template | overrides), encoding="utf-8")
        self.config_file.chmod(0o600)

    def config(self, **overrides):
        return StagingConfig.parse(self.template | overrides)

    def reply(self, status=200, **header_overrides):
        headers = {
            "cache-control": "no-store",
            "referrer-policy": "no-referrer",
            "x-content-type-options": "nosniff",
            "x-frame-options": "DENY",
            "strict-transport-security": "max-age=300",
            "content-security-policy":
                "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
        } | header_overrides
        return preflight.EdgeReply(status, headers, "TLSv1.3", self.TLS_FINGERPRINT)

    def fake_network(self):
        calls = []
        def resolver(hostname):
            calls.append(("resolve", hostname))
            return socket.AF_INET, "8.8.8.8"
        def head(family, address, hostname, path, host_header):
            calls.append(("head", family, address, hostname, path, host_header))
            if host_header != hostname:
                return self.reply(status=0)
            if path != "/":
                return self.reply(status=404)
            return self.reply()
        return calls, resolver, head

    def test_default_command_is_offline_without_bot_token(self):
        out = io.StringIO()
        with patch.object(preflight, "_resolve_public_address",
                          side_effect=AssertionError("No DNS permitted")):
            with patch.object(preflight, "_tls_head",
                              side_effect=AssertionError("No requests permitted")):
                with patch.object(preflight, "read_staging_bot_token",
                                  create=True, side_effect=AssertionError("No token")):
                    with redirect_stdout(out):
                        code = preflight.main([str(self.config_file)])
        self.assertEqual(code, 0)
        report = json.loads(out.getvalue())
        self.assertEqual(report["status"], "PENDING")
        self.assertEqual(report["config_schema_and_file_permissions"], "PASS")
        self.assertEqual(report["requests_sent"], 0)
        self.assertEqual(report["overall_acceptance"], "PENDING")

    def test_preflight_incomplete_permissions_fail_without_leaking_paths(self):
        self.config_file.chmod(0o644)
        out = io.StringIO()
        with redirect_stdout(out):
            code = preflight.main([str(self.config_file)])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(out.getvalue())["status"], "BLOCKED")
        self.assertNotIn(str(self.root), out.getvalue())

    def test_unreviewed_edge_or_enabled_bot_never_resolves(self):
        cases = (
            ({"edge_reviewed": False}, {}),
            ({"enabled": True}, {}),
            ({}, {"direct_tcp_confirmed": False}),
            ({}, {"approved_origin": "https://other-staging.example.org"}),
            ({"https_origin": "https://staging.example.invalid"},
             {"approved_origin": "https://staging.example.invalid"}),
        )
        for config_overrides, kwargs in cases:
            with self.subTest(config_overrides=config_overrides, kwargs=kwargs):
                options = {
                    "approved_origin": self.ORIGIN,
                    "direct_tcp_confirmed": True,
                }
                options.update(kwargs)
                with patch.object(preflight, "_resolve_public_address",
                                  side_effect=AssertionError("Unexpected DNS")):
                    with self.assertRaises(ValueError):
                        preflight.probe_approved_public_edge(
                            self.config(**config_overrides), **options,
                        )

    def test_exactly_five_readonly_head_queries_on_pinned_address(self):
        calls, resolver, head = self.fake_network()
        result = preflight.probe_approved_public_edge(
            self.config(), approved_origin=self.ORIGIN,
            direct_tcp_confirmed=True, resolver=resolver, request=head,
        )
        self.assertEqual(result["edge_probe"], "PASS")
        self.assertEqual(result["status"], "PARTIAL")
        self.assertEqual(result["overall_acceptance"], "PENDING")
        self.assertEqual(result["edge_rate_limits"], "PENDING")
        self.assertEqual(result["requests_sent"], 5)
        self.assertEqual(calls[0], ("resolve", "staging.example.org"))
        self.assertEqual(len(calls), 6)
        self.assertEqual(
            [(row[4], row[5]) for row in calls[1:]],
            [("/", "staging.example.org")]
            + [(path, "staging.example.org") for path in preflight._DENIED_PATHS]
            + [("/", "untrusted-host.invalid")],
        )
        self.assertTrue(all(row[2] == "8.8.8.8" for row in calls[1:]))

    def test_positive_validation_never_masks_wrong_host_or_forbidden_paths(self):
        for mode in ("host_ok", "forbidden_ok", "certificate_drift",
                     "redirect", "cookie", "bad_header", "weak_tls"):
            with self.subTest(mode=mode):
                _, resolver, good = self.fake_network()
                def bad(family, address, hostname, path, host_header):
                    if mode == "host_ok" and host_header != hostname:
                        return self.reply(status=200)
                    if mode == "forbidden_ok" and path == "/compat/":
                        return self.reply(status=200)
                    if mode == "certificate_drift" and path == "/admin/":
                        return preflight.EdgeReply(
                            404, {}, "TLSv1.3", "b" * 64)
                    if mode == "redirect" and path == "/":
                        return self.reply(status=302)
                    if mode == "cookie" and path == "/":
                        return self.reply(**{"set-cookie": "bad=1"})
                    if mode == "bad_header" and path == "/":
                        return self.reply(**{"x-frame-options": "ALLOWALL"})
                    if mode == "weak_tls" and path == "/":
                        return preflight.EdgeReply(200, self.reply().headers,
                                                   "TLSv1.0", self.TLS_FINGERPRINT)
                    return good(family, address, hostname, path, host_header)
                with self.assertRaises(ValueError):
                    preflight.probe_approved_public_edge(
                        self.config(), approved_origin=self.ORIGIN,
                        direct_tcp_confirmed=True, resolver=resolver, request=bad,
                    )

    def test_dns_rejects_private_and_mixed_answer_even_if_global_present(self):
        cases = [
            ["127.0.0.1"], ["10.0.0.2"], ["169.254.169.254"],
            ["192.0.2.1"], ["8.8.8.8", "127.0.0.1"], ["::1"],
            ["fe80::1"],
        ]
        for ips in cases:
            with self.subTest(ips=ips):
                result = []
                for value in ips:
                    address = __import__("ipaddress").ip_address(value)
                    family = socket.AF_INET if address.version == 4 else socket.AF_INET6
                    result.append((family, socket.SOCK_STREAM, socket.IPPROTO_TCP,
                                   "", (value, 443)))
                with patch.object(socket, "getaddrinfo", return_value=result):
                    with self.assertRaises(ValueError):
                        preflight._resolve_public_address("staging.example.org")

    def test_public_dns_is_resolved_once_and_prefers_ipv4(self):
        answers = [
            (socket.AF_INET6, socket.SOCK_STREAM, socket.IPPROTO_TCP, "",
             ("2606:4700:4700::1111", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "",
             ("8.8.4.4", 443)),
        ]
        with patch.object(socket, "getaddrinfo", return_value=answers) as resolve:
            self.assertEqual(preflight._resolve_public_address(
                "staging.example.org"), (socket.AF_INET, "8.8.4.4"))
            resolve.assert_called_once()

    def test_cli_explicit_probe_rejects_missing_review_or_enabled_runtime(self):
        args = [str(self.config_file), "--probe-approved-public-edge",
                "--reviewed-origin", self.ORIGIN]
        for flags in ([], ["--direct-tcp-confirmed"]):
            with patch.object(preflight, "_resolve_public_address",
                              side_effect=AssertionError("No DNS")):
                with redirect_stdout(io.StringIO()) as output:
                    code = preflight.main(args + flags)
                if not flags:
                    self.assertEqual(code, 2)
                else:
                    # Review flag is present but real network remains blocked
                    # by patched fake resolver; CLI must redact its details.
                    self.assertEqual(code, 2)
                self.assertEqual(json.loads(output.getvalue())["status"], "BLOCKED")

    def test_cli_rejects_live_flags_without_explicit_probe(self):
        for extra in (["--reviewed-origin", self.ORIGIN], ["--direct-tcp-confirmed"]):
            with self.subTest(flags=extra):
                with redirect_stdout(io.StringIO()) as output:
                    self.assertEqual(
                        preflight.main([str(self.config_file), *extra]), 2)
                self.assertEqual(json.loads(output.getvalue())["status"], "BLOCKED")
