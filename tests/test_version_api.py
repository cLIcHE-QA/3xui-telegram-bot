from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from aiohttp import web

from version_api import VersionAPIMixin, VersionAPIError, latest_stable_panel, same_version, valid_version


class Client(VersionAPIMixin):
    def __init__(self, url):
        self.base_url = url
        self.token = 'a-test-token-not-a-real-secret'
        self.verify_tls = True


class VersionAPIContractTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.requests = []
        self.http_status = 200
        self.payload = {'success': True, 'obj': {}}
        self.body = None
        async def handler(request):
            self.requests.append((request.method, request.path, dict(await request.post()), dict(request.headers)))
            if self.body is not None:
                return web.Response(text=self.body, status=self.http_status)
            return web.json_response(self.payload, status=self.http_status)
        app = web.Application()
        app.router.add_route('*', '/{tail:.*}', handler)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, '127.0.0.1', 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        self.client = Client(f'http://127.0.0.1:{port}/base')

    async def asyncTearDown(self):
        await self.runner.cleanup()

    async def test_panel_update_is_form_encoded_and_explicitly_stable(self):
        self.payload = {'success': True, 'obj': {'runId': '1735689600123456789'}}
        result = await self.client.update_panel()
        method, path, form, headers = self.requests[0]
        self.assertEqual(method, 'POST')
        self.assertEqual(path, '/base/panel/api/server/updatePanel')
        self.assertEqual(form, {'dev': 'false'})
        self.assertIn('application/x-www-form-urlencoded', headers['Content-Type'])
        self.assertEqual(result['obj']['runId'], '1735689600123456789')

    async def test_version_list_filters_unsafe_tags_and_deduplicates(self):
        self.payload = {'success': True, 'obj': ['v25.9.15', '../bad', 'latest', {}, 'v25.8.1', 'v25.9.15']}
        self.assertEqual(await self.client.get_xray_versions(), ['v25.9.15', 'v25.8.1'])
        self.assertEqual(self.requests[0][0], 'GET')

    async def test_exact_xray_install_path(self):
        await self.client.install_xray('v25.9.15')
        self.assertEqual(self.requests[0][1], '/base/panel/api/server/installXray/v25.9.15')
        self.assertEqual(len(self.requests), 1)

    async def test_unsafe_version_never_reaches_network(self):
        for value in ['latest', '../bad', 'v1.2.3?x=y', 'v1.2.3;id', 'v1.2.3/anything', 'v1.2.3\n']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                await self.client.install_xray(value)
        self.assertEqual(self.requests, [])

    async def test_install_timeout_is_longer_than_read_timeout(self):
        with patch.object(self.client, '_version_request', new_callable=AsyncMock) as request:
            await self.client.install_xray('v25.9.15')
            self.assertEqual(request.call_args.kwargs['timeout'], 180)

    async def test_explicit_api_rejection(self):
        self.payload = {'success': False, 'msg': 'secret token=do-not-echo'}
        with self.assertRaises(VersionAPIError) as caught:
            await self.client.install_xray('v25.9.15')
        self.assertFalse(caught.exception.uncertain)
        self.assertNotIn('do-not-echo', str(caught.exception))
        self.assertEqual(len(self.requests), 1)

    async def test_malformed_mutation_response_is_uncertain(self):
        self.body = '<html>sign in token=do-not-echo</html>'
        with self.assertRaises(VersionAPIError) as caught:
            await self.client.update_panel()
        self.assertTrue(caught.exception.uncertain)
        self.assertNotIn('do-not-echo', str(caught.exception))
        self.assertEqual(len(self.requests), 1)

    async def test_server_error_never_retries_mutation(self):
        self.http_status = 503
        with self.assertRaises(VersionAPIError) as caught:
            await self.client.update_panel()
        self.assertTrue(caught.exception.uncertain)
        self.assertEqual(len(self.requests), 1)

    async def test_read_http_error_has_status(self):
        self.http_status = 404
        with self.assertRaises(VersionAPIError) as caught:
            await self.client.get_update_status()
        self.assertFalse(caught.exception.uncertain)
        self.assertEqual(caught.exception.status, 404)

    async def test_status_and_panel_metadata(self):
        self.payload = {'success': True, 'obj': {'xray': {'version': '25.9.15', 'state': 'running'}}}
        self.assertEqual((await self.client.version_status())['xray']['version'], '25.9.15')
        self.payload = {'success': True, 'obj': {'currentVersion': '3.8.5', 'latestVersion': 'v3.8.6', 'channel': 'stable'}}
        info = await self.client.get_panel_update_info()
        self.assertEqual(await latest_stable_panel(info), 'v3.8.6')

    async def test_empty_version_response_is_not_fabricated(self):
        self.payload = {'success': True, 'obj': []}
        with self.assertRaises(VersionAPIError):
            await self.client.get_xray_versions()

    def test_version_comparison_handles_optional_v_prefix(self):
        self.assertTrue(same_version('v25.9.15', '25.9.15'))
        self.assertFalse(same_version('', ''))
        self.assertFalse(same_version('25.9.15', '25.9.15-beta'))
        self.assertTrue(valid_version('v25.9.15'))
        self.assertFalse(valid_version('v' + '1' * 25))


if __name__ == '__main__':
    unittest.main()
