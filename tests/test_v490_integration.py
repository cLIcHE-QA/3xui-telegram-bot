"""Real application integration with fake environment values, no live APIs."""
from __future__ import annotations

import inspect
import json
import os
from pathlib import Path
import sqlite3
import tarfile
import tempfile
import unittest
from unittest.mock import AsyncMock, patch


class IntegrationTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.env = patch.dict(os.environ, {
            'BOT_TOKEN': '123456789:offline-test-token-not-used-for-network',
            'PANEL_URL': 'https://panel.example.invalid/base',
            'PANEL_API_TOKEN': 'offline-test-placeholder',
            'SUBSCRIPTION_URL_TEMPLATE': 'https://sub.example.invalid/sub/{sub_id}',
            'ALLOWED_TELEGRAM_IDS': '1', 'ADMIN_TELEGRAM_IDS': '1',
            'NODE_BACKUP_TARGETS': '',
            'DB_PATH': str(Path(cls.tmp.name) / 'bot.sqlite3'),
            'BACKUP_DIR': str(Path(cls.tmp.name) / 'backups'),
        })
        cls.env.start()
        import bot
        import versions_updates
        cls.bot = bot
        cls.updates = versions_updates

    @classmethod
    def tearDownClass(cls):
        cls.env.stop()
        cls.tmp.cleanup()

    def callback_values(self, markup):
        return [button.callback_data for row in markup.inline_keyboard for button in row]

    def test_navigation_shortcuts(self):
        self.assertIn('admin:versions', self.callback_values(self.bot.system_menu()))
        self.assertIn('admin:versions', self.callback_values(self.bot.infrastructure_menu()))
        self.assertIn('admin:ver:panel:m', self.callback_values(self.bot.master_detail_keyboard()))
        self.assertIn('admin:ver:xray:m:0', self.callback_values(self.bot.master_detail_keyboard()))
        self.assertIn('admin:ver:panel:n2', self.callback_values(self.bot.node_detail_keyboard(2)))
        self.assertIn('admin:ver:xray:n2:0', self.callback_values(self.bot.node_detail_keyboard(2)))

    def test_versions_navigation_labels_are_consistent(self):
        home = self.updates.keyboard([[('⬅ System', 'admin:section:system')]])
        self.assertEqual(home.inline_keyboard[0][0].text, '⬅ System')
        self.assertEqual(self.updates.back().inline_keyboard[0][0].text, '⬅ Versions & Updates')
        self.assertEqual(self.updates.back('m').inline_keyboard[0][0].text, '⬅ Сервер')

    def test_real_xui_client_has_version_api(self):
        from version_api import VersionAPIMixin
        self.assertIsInstance(self.bot.xui, VersionAPIMixin)
        self.assertTrue(callable(self.bot.xui.install_xray))
        self.assertTrue(callable(self.bot.xui.get_panel_update_info))

    def test_callback_permissions_are_explicit_and_fail_closed(self):
        from admin_auth import required_role_for_callback
        for data in ['admin:versions', 'admin:ver:target:m', 'admin:ver:panel:n2',
                     'admin:ver:xray:m:0', 'admin:ver:check:0123456789abcdef']:
            self.assertEqual(required_role_for_callback(data), 'read_only', data)
        for data in ['admin:ver:prepare:m:panel', 'admin:ver:pick:n2:v25.9.15',
                     'admin:ver:run:0123456789abcdef', 'admin:ver:cancel:0123456789abcdef',
                     'admin:ver:target:m:unexpected']:
            self.assertEqual(required_role_for_callback(data), 'admin', data)
        self.assertEqual(required_role_for_callback('admin:ver:unlock:0123456789abcdef'), 'owner')

    def test_callback_data_fits_telegram_byte_limit(self):
        key = 'n' + '9' * 19
        tag = 'v12345.12345.12345-beta'
        data = f'admin:ver:pick:{key}:{tag}'
        self.assertLessEqual(len(data.encode('utf-8')), 64)
        markup = self.updates.keyboard([[('version', data)]])
        self.assertEqual(self.callback_values(markup), [data])

    def test_legacy_node_confirmation_has_no_direct_update_call(self):
        from advanced_nodes import node_update_panel_legacy
        source = inspect.getsource(node_update_panel_legacy)
        self.assertIn('show_panel_screen', source)
        self.assertNotIn('node_update_panels(', source)
        self.assertNotIn('service.execute(', source)

    def test_router_registered_and_master_shows_panel_version(self):
        self.assertIn('dp.include_router(versions_router)', inspect.getsource(self.bot.main))
        self.assertIn('get_panel_update_info', inspect.getsource(self.bot.admin_master_detail))
        self.assertIn('3x-ui:', inspect.getsource(self.bot.admin_master_detail))

    def test_single_source_for_runtime_version(self):
        from version import APP_VERSION
        self.assertEqual(APP_VERSION, '4.9.0')
        self.assertIn('APP_VERSION', inspect.getsource(self.bot.start))
        self.assertIn('APP_VERSION', inspect.getsource(self.bot.create_user))
        from system_backup import SystemBackupService
        self.assertIn('version=APP_VERSION', inspect.getsource(SystemBackupService.create_full_backup))

    def test_actual_backup_manifest_version(self):
        from backup_manager import BackupManager
        from version import APP_VERSION
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / 'bot.sqlite3'
            with sqlite3.connect(db_path) as connection:
                connection.execute('CREATE TABLE sample(id INTEGER PRIMARY KEY)')
            manager = BackupManager(str(db_path), str(root / 'backups'))
            manager.sources_root = root / 'sources'
            result = manager.create_full_backup()
            with tarfile.open(result.info.path) as archive:
                manifest = json.load(archive.extractfile('manifest.json'))
            self.assertEqual(manifest['version'], APP_VERSION)

    async def test_audit_and_job_records(self):
        await self.updates.db.init()
        from version_service import Operation
        now = __import__('time').time()
        op = Operation('0123456789abcdef', 'm', 1, 10, 20, 'xray', '25.8.1', 'v25.9.15', 'fingerprint', now, now + 300)
        await self.updates.record_operation(op, 'prepared')
        await self.updates.record_operation(op, 'started')
        op.actual = op.desired
        op.xray_state = 'running'
        await self.updates.record_operation(op, 'success')
        job = await self.updates.db.last_job_run('xray.install')
        self.assertEqual(job.status, 'success')
        actions = [row.action for row in await self.updates.db.list_audit(limit=10)]
        self.assertIn('xray.install.success', actions)

    async def test_missing_direct_token_not_bypassed(self):
        from types import SimpleNamespace
        from version_service import UpdateError
        node = SimpleNamespace(name='Finland', transitive=False, enable=True, status='online')
        with patch.object(self.updates.xui, 'node_get', new=AsyncMock(return_value=node)):
            with self.assertRaises(UpdateError):
                await self.updates.resolve_target('n2')

    async def test_transitive_node_read_only(self):
        from types import SimpleNamespace
        from version_service import UpdateError
        with patch.object(self.updates.xui, 'node_get', new=AsyncMock(return_value=SimpleNamespace(transitive=True))):
            with self.assertRaises(UpdateError):
                await self.updates.resolve_target('n2')

    async def test_partial_master_backup_blocks_update(self):
        from types import SimpleNamespace
        from version_service import UpdateError
        target = self.updates._target('m', 'Master', self.updates.xui)
        with patch.object(self.updates.system_backup, 'create_full_backup', new=AsyncMock(return_value=SimpleNamespace(missing=('x-ui.db',)))):
            with self.assertRaises(UpdateError):
                await self.updates.create_update_backup(target, '0123456789abcdef')


if __name__ == '__main__':
    unittest.main()
