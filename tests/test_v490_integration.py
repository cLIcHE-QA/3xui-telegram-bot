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
from types import SimpleNamespace
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
        import app_runtime
        import admin_navigation
        import admin_shell
        import client_access
        import advanced_users
        import node_ui
        import system_admin
        import storage_admin
        import versions_updates
        cls.bot = bot
        cls.runtime = app_runtime
        cls.nav = admin_navigation
        cls.shell = admin_shell
        cls.client = client_access
        cls.users = advanced_users
        cls.node_ui = node_ui
        cls.system = system_admin
        cls.storage = storage_admin
        cls.updates = versions_updates

    @classmethod
    def tearDownClass(cls):
        cls.env.stop()
        cls.tmp.cleanup()

    def callback_values(self, markup):
        return [button.callback_data for row in markup.inline_keyboard for button in row]

    def test_bot_is_thin_runtime_entrypoint(self):
        source = inspect.getsource(self.bot)
        self.assertIn('from app_runtime import main', source)
        self.assertNotIn('Dispatcher(', source)
        self.assertNotIn('include_router(', source)
        self.assertNotIn('automatic_backup_loop', source)
        self.assertIn('asyncio.run(main())', source)

    def test_v424_diagnostics_router_is_registered(self):
        source = inspect.getsource(self.runtime)
        self.assertIn(
            'from website_diagnostics_admin import website_diagnostics_router',
            source,
        )
        self.assertIn('dp.include_router(website_diagnostics_router)', source)

    def test_navigation_shortcuts(self):
        self.assertIn('admin:versions', self.callback_values(self.nav.system_menu()))
        self.assertIn('admin:botupd', self.callback_values(self.nav.system_menu()))
        self.assertNotIn('admin:versions', self.callback_values(self.nav.infrastructure_menu()))
        self.assertIn('admin:hostctl:m', self.callback_values(self.node_ui.master_detail_keyboard()))
        self.assertIn('admin:ver:panel:m', self.callback_values(self.node_ui.master_detail_keyboard()))
        self.assertIn('admin:ver:xray:m:0', self.callback_values(self.node_ui.master_detail_keyboard()))
        self.assertIn('admin:cheburcheck:master', self.callback_values(self.node_ui.master_detail_keyboard()))
        self.assertIn('admin:hostctl:n2', self.callback_values(self.node_ui.node_detail_keyboard(2)))
        self.assertIn('admin:ver:panel:n2', self.callback_values(self.node_ui.node_detail_keyboard(2)))
        self.assertIn('admin:ver:xray:n2:0', self.callback_values(self.node_ui.node_detail_keyboard(2)))
        self.assertIn('admin:cheburcheck:node:2', self.callback_values(self.node_ui.node_detail_keyboard(2)))
        self.assertIn('admin:webmon', self.callback_values(self.nav.monitoring_menu()))

    def test_versions_navigation_labels_are_consistent(self):
        home = self.updates.keyboard([[('⬅ Система', 'admin:section:system')]])
        self.assertEqual(home.inline_keyboard[0][0].text, '⬅ Система')
        self.assertEqual(self.updates.back().inline_keyboard[0][0].text, '⬅ Версии и обновления')
        self.assertEqual(self.updates.back('m').inline_keyboard[0][0].text, '⬅ Сервер')

    def test_static_inline_buttons_start_with_visual_marker(self):
        import ast
        import unicodedata

        root = Path(__file__).resolve().parents[1]
        files = [
            'bot.py', 'admin_shell.py', 'client_access.py', 'node_admin.py', 'system_admin.py', 'storage_admin.py', 'advanced_nodes.py', 'advanced_users.py', 'user_groups_admin.py', 'inbound_admin.py',
            'catalog_admin.py', 'business_admin.py', 'admin_observability.py',
            'disaster_recovery.py', 'logs_alerts.py', 'host_control_ui.py',
            'fleet_operations.py', 'cheburcheck_admin.py',
            'website_monitoring_admin.py', 'website_diagnostics_admin.py',
        ]

        def marked(label: str) -> bool:
            value = label.strip()
            if not value:
                return False
            return unicodedata.category(value[0]) in {'So', 'Sm'}

        missing = []
        for name in files:
            tree = ast.parse((root / name).read_text(encoding='utf-8'), filename=name)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                if not (isinstance(func, ast.Name) and func.id == 'InlineKeyboardButton'):
                    continue
                text_kw = next((kw.value for kw in node.keywords if kw.arg == 'text'), None)
                if isinstance(text_kw, ast.Constant) and isinstance(text_kw.value, str):
                    if not marked(text_kw.value):
                        missing.append(f'{name}:{node.lineno}:{text_kw.value}')
        self.assertEqual(missing, [])

    def test_versions_static_tuple_buttons_start_with_visual_marker(self):
        import ast
        import unicodedata

        source = inspect.getsource(self.updates)
        tree = ast.parse(source)

        def marked(label: str) -> bool:
            value = label.strip()
            if not value:
                return False
            return unicodedata.category(value[0]) in {'So', 'Sm'}

        missing = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Tuple) or len(node.elts) != 2:
                continue
            label, callback = node.elts
            if (isinstance(label, ast.Constant) and isinstance(label.value, str)
                    and isinstance(callback, (ast.Constant, ast.JoinedStr))):
                cb_value = callback.value if isinstance(callback, ast.Constant) else None
                if (cb_value is None or (isinstance(cb_value, str) and cb_value.startswith('admin:'))):
                    if not marked(label.value):
                        missing.append(f'line {node.lineno}: {label.value}')
        self.assertEqual(missing, [])

    def test_system_admin_helpers_are_stable(self):
        self.assertEqual(
            self.system.public_health_url('https://sub.example.invalid/sub/{sub_id}'),
            'https://sub.example.invalid/healthz',
        )
        self.assertIsNone(self.system.public_health_url(''))
        self.assertEqual(
            self.system.usage_line('RAM', 50, 100),
            'RAM: 50 B / 100 B (50%)',
        )

    def test_health_summary_uses_symmetric_master_node_grammar(self):
        node = SimpleNamespace(
            id=1,
            name="Finland",
            enable=True,
            status="online",
            xray_state="running",
            xray_version="26.9.9",
            cpu_pct=8.0,
            mem_pct=27.0,
            uptime_secs=5 * 86400 + 21 * 3600 + 9 * 60,
            inbound_count=3,
            client_count=24,
            online_count=7,
            latency_ms=42,
        )
        self.assertEqual(
            self.system._node_health_lines(node),
            [
                "🇫🇮 Finland · 🟢 В сети",
                "🟢 Панель: в сети",
                "🟢 Xray: работает 26.9.9",
                "🧮 CPU: 8.0%",
                "🧠 RAM: 27.0%",
                "⏱ Время работы: 5д 21ч 9м",
                "🌐 Inbounds: 3",
                "👥 Клиентов: 24 · 📡 В сети: 7",
                "📶 Задержка API: 42 ms",
            ],
        )

        node.enable = False
        node.status = "offline"
        maintenance = self.system._node_health_lines(node)
        self.assertEqual(maintenance[0], "🇫🇮 Finland · 🛠 Обслуживание")
        self.assertEqual(maintenance[1], "🛠 Панель: обслуживание")

    def test_admin_shell_routes_have_single_owner(self):
        shell_source = inspect.getsource(self.shell)
        bot_source = inspect.getsource(self.bot)
        self.assertIn('@admin_shell_router.message(Command("admin"))', shell_source)
        self.assertNotIn('@router.message(Command("admin"))', bot_source)
        for callback in (
            'admin:dashboard',
            'admin:subscriptions',
            'admin:section:infrastructure',
            'admin:section:monitoring',
            'admin:section:system',
            'admin:infra:inbounds',
            'admin:home',
        ):
            self.assertIn(f'F.data == "{callback}"', shell_source)
            self.assertNotIn(f'F.data == "{callback}"', bot_source)

    def test_client_access_routes_have_single_owner(self):
        client_source = inspect.getsource(self.client)
        bot_source = inspect.getsource(self.bot)
        for marker in (
            '@client_access_router.message(CommandStart())',
            '@client_access_router.message(Command("subscription"))',
            '@client_access_router.callback_query(F.data == "client:home")',
            '@client_access_router.callback_query(F.data == "client:profile")',
            '@client_access_router.callback_query(F.data == "client:subscription")',
            '@client_access_router.callback_query(F.data == "client:buy")',
            '@client_access_router.callback_query(F.data == "client:traffic")',
            '@client_access_router.callback_query(F.data == "client:devices")',
            '@client_access_router.callback_query(F.data == "client:help")',
            '@client_access_router.callback_query(F.data.in_({"create", "inbounds", "subscription"}))',
            '@client_access_router.message(Command("create", "inbounds"))',
        ):
            self.assertIn(marker, client_source)
        self.assertNotIn('CommandStart()', bot_source)
        self.assertNotIn('@router.message(Command("inbounds"))', bot_source)
        self.assertNotIn('@router.message(Command("create"))', bot_source)
        self.assertNotIn('@router.message(Command("subscription"))', bot_source)
        self.assertEqual(
            self.callback_values(self.client.portal_menu()),
            [
                'client:profile',
                'client:subscription',
                'client:buy',
                'client:traffic',
                'client:devices',
                'client:help',
            ],
        )

    def test_legacy_user_callbacks_are_owned_by_advanced_users(self):
        user_source = inspect.getsource(self.users)
        bot_source = inspect.getsource(self.bot)
        for callback in (
            'adminuser:',
            'adminsub:',
            'adminsync:',
            'adminextend:',
            'admindisable:',
            'adminenable:',
            'admindelask:',
            'admindel:',
        ):
            self.assertIn(callback, user_source)
            self.assertNotIn(
                f'F.data.startswith("{callback}")',
                bot_source,
            )
        for callback in (
            'admin:users',
            'admin:provision:all:ask',
            'admin:provision:all:run',
            'admin:syncall:ask',
            'admin:syncall:run',
            'admin:stats',
        ):
            self.assertIn(f'F.data == "{callback}"', user_source)
            self.assertNotIn(f'F.data == "{callback}"', bot_source)
        self.assertIn('inbound_is_managed(settings, i)', inspect.getsource(self.users.is_managed_inbound))

    def test_storage_admin_uses_shared_backup_lock(self):
        self.assertIs(self.storage.backup_lock, self.runtime.backup_lock)
        source = inspect.getsource(self.storage.admin_backup_create)
        self.assertIn('replicate_with_job', source)
        self.assertIn('system_backup.create_full_backup', source)
        self.assertEqual(self.storage.human_bytes(1024), '1.0 KB')
        with patch.object(
            self.storage.backup_manager, 'list_backups', return_value=[]
        ), patch.object(
            self.storage.system_backup, 'configured_node_names', return_value=[]
        ):
            text = self.storage.backup_status_text()
        self.assertIn('🕘 Последняя: ещё не создана', text)
        self.assertIn('🌍 Резервные копии нод: не настроены', text)

    def test_real_xui_client_has_version_api(self):
        from version_api import VersionAPIMixin
        self.assertIsInstance(self.shell.xui, VersionAPIMixin)
        self.assertTrue(callable(self.shell.xui.install_xray))
        self.assertTrue(callable(self.shell.xui.get_panel_update_info))

    def test_callback_permissions_are_explicit_and_fail_closed(self):
        from admin_auth import required_role_for_callback
        for data in ['admin:versions', 'admin:ver:target:m', 'admin:ver:panel:n2',
                     'admin:ver:xray:m:0', 'admin:ver:check:0123456789abcdef']:
            self.assertEqual(required_role_for_callback(data), 'read_only', data)
        for data in ['admin:ver:prepare:m:panel', 'admin:ver:pick:n2:v25.9.15',
                     'admin:ver:run:0123456789abcdef', 'admin:ver:cancel:0123456789abcdef']:
            self.assertEqual(required_role_for_callback(data), 'admin', data)
        self.assertIsNone(required_role_for_callback('admin:ver:target:m:unexpected'))
        self.assertEqual(required_role_for_callback('admin:ver:op:0123456789abcdef'), 'read_only')
        self.assertEqual(required_role_for_callback('admin:ver:unlock:0123456789abcdef'), 'owner')
        self.assertEqual(required_role_for_callback('admin:hostctl:m'), 'read_only')
        self.assertEqual(required_role_for_callback('admin:hostctl:n2'), 'read_only')
        for data in [
            'admin:hostctl:m:ss:ask', 'admin:hostctl:m:ss:run',
            'admin:hostctl:n2:sr:ask', 'admin:hostctl:n2:pr:run',
            'admin:hostctl:n2:xr:run',
        ]:
            self.assertEqual(required_role_for_callback(data), 'admin', data)
        self.assertEqual(required_role_for_callback('admin:hostctl:n2:xs:ask'), 'owner')
        self.assertEqual(required_role_for_callback('admin:hostctl:n2:xs:run'), 'owner')
        self.assertEqual(required_role_for_callback('admin:hostctl:m:sp:ask'), 'owner')
        self.assertEqual(required_role_for_callback('admin:hostctl:n2:stopcancel'), 'owner')
        for data in ['admin:fleet', 'admin:fleet:health', 'admin:fleet:jobs']:
            self.assertEqual(required_role_for_callback(data), 'read_only', data)
        for data in [
            'admin:fleet:mt:e', 'admin:fleet:mt:e:n2',
            'admin:fleet:rollout', 'admin:fleet:ro:p',
            'admin:fleet:run:012345abcdef:canary',
        ]:
            self.assertEqual(required_role_for_callback(data), 'admin', data)

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

    def test_legacy_restart_xray_callback_cannot_mutate_directly(self):
        from advanced_nodes import node_restart_xray_legacy
        source = inspect.getsource(node_restart_xray_legacy)
        self.assertIn('admin:hostctl:n', source)
        self.assertNotIn('restart_xray(', source)
        self.assertNotIn('direct_client_for(', source)

    def test_router_registered_and_master_shows_panel_version(self):
        self.assertIn('dp.include_router(admin_shell_router)', inspect.getsource(self.runtime.main))
        self.assertIn('dp.include_router(client_access_router)', inspect.getsource(self.runtime.main))
        self.assertIn('dp.include_router(versions_router)', inspect.getsource(self.runtime.main))
        self.assertIn('dp.include_router(node_admin_router)', inspect.getsource(self.runtime.main))
        self.assertIn('dp.include_router(system_admin_router)', inspect.getsource(self.runtime.main))
        self.assertIn('dp.include_router(storage_admin_router)', inspect.getsource(self.runtime.main))
        self.assertIn('dp.include_router(host_control_router)', inspect.getsource(self.runtime.main))
        self.assertIn('dp.include_router(fleet_router)', inspect.getsource(self.runtime.main))
        self.assertIn('dp.include_router(cheburcheck_router)', inspect.getsource(self.runtime.main))
        self.assertIn('get_panel_update_info', inspect.getsource(self.system.admin_master_detail))
        self.assertIn('3x-ui:', inspect.getsource(self.system.admin_master_detail))

    def test_single_source_for_runtime_version(self):
        from version import APP_VERSION
        self.assertEqual(APP_VERSION, '5.0.0-rc.3')
        self.assertIn('APP_VERSION', inspect.getsource(self.client.portal_text))
        self.assertNotIn('async def create_user', inspect.getsource(self.client))
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