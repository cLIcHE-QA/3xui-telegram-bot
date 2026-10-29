"""Изолированный TCP keepalive двух адресных reads, без реальной панели/Telegram."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import datetime
from pathlib import Path
import ssl
import tempfile
import unittest
from unittest.mock import patch

import aiohttp
from aiohttp import web
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from customer_provider_xui import XuiCustomerProvider
from customer_service import CustomerProviderUnavailable
import panel_read_scope as scope
from xui import XUIClient, XUIReadUnavailable


OWNER = "traffic-owner@example.invalid"
TOKEN = "synthetic-traffic-token"


class TrafficConnectionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.calls = []
        self.transports = []
        self.tls_flags = []
        self.sessions = []
        self.connectors = []
        self.allowed_tokens = {TOKEN}
        self.failure_stage = None
        self.malformed = False
        self.server_close = False
        self.change_binding = None
        self.hold_second = False
        self.second_started = asyncio.Event()
        self.release = asyncio.Event()
        app = web.Application()
        app.router.add_route("*", "/{path:.*}", self.reply)
        self.runner = web.AppRunner(app, shutdown_timeout=0.1)
        await self.runner.setup()
        self.addAsyncCleanup(self.runner.cleanup)
        site = web.TCPSite(self.runner, "127.0.0.1", 0)
        await site.start()
        self.port = site._server.sockets[0].getsockname()[1]
        self.client = XUIClient(f"http://localhost:{self.port}", TOKEN)
        original_session = aiohttp.ClientSession

        def session(**options):
            result = original_session(**options)
            self.sessions.append(result)
            self.connectors.append(result.connector)
            return result

        patcher = patch.object(aiohttp, "ClientSession", side_effect=session)
        patcher.start()
        self.addCleanup(patcher.stop)

    async def asyncTearDown(self):
        self.release.set()
        self.assertEqual(scope.read_scope_snapshot(), {"active_scopes": 0})
        self.assertTrue(all(session.closed for session in self.sessions))
        self.assertTrue(all(connector.closed for connector in self.connectors))

    async def reply(self, request):
        self.assertIn(request.remote, {"127.0.0.1", "::1"})
        self.calls.append((request.method, request.path, dict(request.headers)))
        # Retain the transport objects so identity cannot be recycled by GC.
        self.transports.append(request.transport)
        self.tls_flags.append(request.secure)
        self.assertIn(request.headers.get("Authorization"),
                      {"Bearer " + token for token in self.allowed_tokens})
        if self.failure_stage and self.failure_stage in request.path:
            if self.malformed:
                return web.Response(text="synthetic invalid JSON")
            return web.json_response({"success": False, "msg": "synthetic private detail"}, status=500)
        if "/get/" in request.path:
            response = web.json_response({
                "success": True, "obj": {"client": {"email": OWNER, "totalGB": 100}},
            })
            response.set_cookie("traffic_probe", "synthetic-cookie")
            if self.server_close:
                response.force_close()
            if self.change_binding is not None:
                self.client.base_url, self.client.token, self.client.verify_tls = self.change_binding
            return response
        self.assertIn("/traffic/", request.path)
        if self.hold_second:
            self.second_started.set()
            await self.release.wait()
        return web.json_response({"success": True, "obj": {"up": 1, "down": 2}})

    async def read(self):
        result = await XuiCustomerProvider(self.client).traffic(OWNER)
        self.assertEqual((result.up, result.down, result.total), (1, 2, 100))

    def assert_fresh_reads(self, count):
        self.assertEqual(len(self.calls), count)
        self.assertTrue(all(method == "GET" for method, _, _ in self.calls))
        self.assertTrue(all(not headers.get("Cookie") for _, _, headers in self.calls))

    async def test_two_addressed_reads_reuse_one_tcp_connection(self):
        await self.read()
        self.assert_fresh_reads(2)
        self.assertIs(self.transports[0], self.transports[1])

    async def test_new_operation_does_not_reuse_previous_operation_transport(self):
        await self.read()
        await self.read()
        self.assert_fresh_reads(4)
        self.assertIs(self.transports[0], self.transports[1])
        self.assertIs(self.transports[2], self.transports[3])
        self.assertIsNot(self.transports[0], self.transports[2])

    async def test_concurrent_operations_have_distinct_owned_connections(self):
        await asyncio.gather(*(self.read() for _ in range(8)))
        self.assert_fresh_reads(16)
        self.assertEqual(len(set(self.transports)), 8)

    async def test_different_clients_credentials_and_operations_are_isolated(self):
        await self.read()
        other_token = TOKEN + "-other"
        self.allowed_tokens.add(other_token)
        other = XUIClient(self.client.base_url, other_token)
        result = await XuiCustomerProvider(other).traffic(OWNER)
        self.assertEqual(result.total, 100)
        self.assert_fresh_reads(4)
        self.assertIsNot(self.transports[0], self.transports[2])
        self.assertEqual([headers["Authorization"] for _, _, headers in self.calls],
                         ["Bearer " + TOKEN] * 2 + ["Bearer " + other_token] * 2)

    async def test_server_connection_close_is_honored_without_application_retry(self):
        self.server_close = True
        await self.read()
        self.assert_fresh_reads(2)
        self.assertIsNot(self.transports[0], self.transports[1])
        self.assertIs(self.connectors[0], self.connectors[1])

    async def test_http_and_json_failure_at_either_read_close_all_resources(self):
        for route in ("/get/", "/traffic/"):
            for malformed in (False, True):
                self.calls.clear()
                self.failure_stage = route
                self.malformed = malformed
                with self.assertRaises(CustomerProviderUnavailable) as caught:
                    await self.read()
                self.assertEqual(str(caught.exception), "customer provider unavailable")
                self.assertTrue(caught.exception.__suppress_context__)
                self.assertEqual(len(self.calls), 1 if route == "/get/" else 2)
                self.assertEqual(scope.read_scope_snapshot()["active_scopes"], 0)
                self.assertTrue(all(session.closed for session in self.sessions))
                self.assertTrue(all(connector.closed for connector in self.connectors))

    async def test_cancel_during_second_response_closes_owned_connector(self):
        self.hold_second = True
        task = asyncio.create_task(self.read())
        try:
            await asyncio.wait_for(self.second_started.wait(), 2)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            self.release.set()
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(scope.read_scope_snapshot()["active_scopes"], 0)
        self.assertTrue(all(connector.closed for connector in self.connectors))

    async def test_binding_change_before_second_read_is_denied_without_http(self):
        base = self.client.base_url
        for binding in ((base, TOKEN + "-other", True),
                        ("https://foreign.example.invalid", TOKEN, True),
                        (base, TOKEN, False)):
            self.calls.clear()
            self.sessions.clear()
            self.connectors.clear()
            self.client.base_url, self.client.token, self.client.verify_tls = base, TOKEN, True
            self.change_binding = binding
            with self.assertRaises(CustomerProviderUnavailable) as caught:
                await self.read()
            self.assertEqual(str(caught.exception), "customer provider unavailable")
            self.assertEqual(len(self.calls), 1)
            self.assertEqual(len(self.sessions), 1)
            self.assertTrue(self.connectors[0].closed)
            self.assertEqual(scope.read_scope_snapshot()["active_scopes"], 0)

    async def test_admission_denial_happens_before_connector_allocation(self):
        @asynccontextmanager
        async def denied():
            raise XUIReadUnavailable("synthetic admission refusal")
            yield

        with patch.object(self.client, "_panel_read_slot", denied):
            with self.assertRaises(CustomerProviderUnavailable):
                await self.read()
        self.assertFalse(self.sessions)
        self.assertFalse(self.calls)

    async def test_full_scope_capacity_maps_to_existing_customer_unavailable(self):
        ready = asyncio.Event()
        hold = asyncio.Event()
        entered = 0

        async def occupy():
            nonlocal entered
            async with scope.scoped_panel_reads(object()):
                entered += 1
                if entered == 64:
                    ready.set()
                await hold.wait()

        tasks = [asyncio.create_task(occupy()) for _ in range(64)]
        try:
            await asyncio.wait_for(ready.wait(), 2)
            with self.assertRaises(CustomerProviderUnavailable) as caught:
                await self.read()
            self.assertEqual(str(caught.exception), "customer provider unavailable")
            self.assertFalse(self.sessions)
            self.assertFalse(self.calls)
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def start_synthetic_tls(self):
        temp = tempfile.TemporaryDirectory(prefix="traffic-synthetic-tls-")
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        key = ec.generate_private_key(ec.SECP256R1())
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
        now = datetime.datetime.now(datetime.timezone.utc)
        certificate = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
                       .public_key(key.public_key()).serial_number(x509.random_serial_number())
                       .not_valid_before(now - datetime.timedelta(days=1))
                       .not_valid_after(now + datetime.timedelta(days=1))
                       .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
                       .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False)
                       .sign(key, hashes.SHA256()))
        certificate_path, key_path = root / "synthetic.crt", root / "synthetic.key"
        certificate_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
        key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM,
                                             serialization.PrivateFormat.PKCS8,
                                             serialization.NoEncryption()))
        key_path.chmod(0o600)
        server_tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        server_tls.load_cert_chain(certificate_path, key_path)
        site = web.TCPSite(self.runner, "127.0.0.1", 0, ssl_context=server_tls)
        await site.start()
        self.client = XUIClient(f"https://localhost:{site._server.sockets[0].getsockname()[1]}", TOKEN)
        return ssl.create_default_context(cafile=str(certificate_path))

    async def test_tls_requires_trust_and_reuses_only_verified_owned_connection(self):
        trust = await self.start_synthetic_tls()
        with self.assertRaises(CustomerProviderUnavailable):
            await self.read()  # The default trust store rejects this synthetic CA.
        self.assertFalse(self.calls)
        self.assertTrue(all(connector.closed for connector in self.connectors))
        original = aiohttp.TCPConnector

        def trusted_connector(**options):
            return original(**options, ssl=trust)

        # Only this isolated fixture injects its synthetic CA. Runtime TLS
        # validation is unchanged; no CERT_NONE/verify=False fallback is used.
        with patch.object(aiohttp, "TCPConnector", side_effect=trusted_connector), \
                patch.object(aiohttp.client, "TCPConnector", side_effect=trusted_connector):
            await self.read()
        self.assert_fresh_reads(2)
        self.assertTrue(self.client.verify_tls)
        self.assertIs(self.transports[0], self.transports[1])
        self.assertTrue(all(self.tls_flags))

    async def test_explicit_existing_verify_false_setting_is_not_changed(self):
        await self.start_synthetic_tls()
        self.client.verify_tls = False
        await self.read()
        self.assert_fresh_reads(2)
        self.assertIs(self.transports[0], self.transports[1])


if __name__ == "__main__":
    unittest.main()
