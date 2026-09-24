from __future__ import annotations

import asyncio
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import time
import unittest

from version_api import VersionAPIError
from version_service import (
    BackupReceipt, OperationStore, Target, UpdateError, UpdateService,
    VersionState, file_hash, safe_error,
)


class FakeClient:
    def __init__(self):
        self.xray = '25.8.1'
        self.panel = '3.8.5'
        self.state = 'running'
        self.available = ['v25.10.31', 'v25.9.15', 'v25.8.1', 'v25.7.26']
        self.xray_posts = 0
        self.panel_posts = 0
        self.install_error = None
        self.change_version = True
        self.run_id = '1735689600123456789'
        self.reported_run_id = self.run_id
        self.update_outcome = 'success'
        self.entered = None
        self.release = None

    async def get_xray_versions(self):
        return self.available

    async def install_xray(self, value):
        self.xray_posts += 1
        if self.entered:
            self.entered.set()
            await self.release.wait()
        if self.change_version:
            self.xray = value
        if self.install_error:
            raise self.install_error
        return {'success': True}

    async def update_panel(self):
        self.panel_posts += 1
        if self.change_version:
            self.panel = 'v3.8.6'
        if self.install_error:
            raise self.install_error
        return {'success': True, 'obj': {'runId': self.run_id}}

    async def get_update_status(self):
        return {'runId': self.reported_run_id, 'state': self.update_outcome}


class WorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = OperationStore(self.root / 'journal')
        self.client = FakeClient()
        self.target = Target('m', 'Master', 'fingerprint', self.client)
        self.roles = {1: 40, 2: 30, 3: 10, 4: 20}
        self.events = []
        self.stable = 'v3.8.6'
        self.backups = 0
        self.bad_backup = False
        self.record_failure = ''
        self.service = self.make_service()
        self.ids = {'actor': 1, 'chat': 10, 'message': 20}

    def make_service(self):
        async def resolve(key):
            return replace(self.target, key=key)
        async def snapshot(target):
            return VersionState(self.client.panel, self.client.xray, self.client.state)
        async def stable(target):
            return self.stable
        async def backup(target, nonce):
            self.backups += 1
            if self.bad_backup:
                raise UpdateError('Backup failed')
            path = self.root / f'{nonce}.db'
            path.write_bytes(b'a test backup, validated by an injected provider')
            return BackupReceipt(str(path), file_hash(path))
        async def authorize(actor, minimum):
            return self.roles.get(actor, 0) >= {'owner': 40, 'admin': 30, 'read_only': 10}[minimum]
        async def record(op, stage):
            if stage == self.record_failure:
                raise RuntimeError('journal unavailable')
            if stage == 'started':
                op.job_id = 17
            self.events.append((op.nonce, stage))
        return UpdateService(
            self.store, resolve=resolve, snapshot=snapshot, stable=stable, backup=backup,
            authorize=authorize, record=record, verify_seconds=0.1, poll_seconds=0.001,
        )

    async def prepare(self, component='xray', value='v25.9.15'):
        return await self.service.prepare('m', component, value, **self.ids)

    async def test_two_phase_xray_success(self):
        op = await self.prepare()
        self.assertEqual(op.state, 'prepared')
        self.assertEqual(self.client.xray_posts, 0)
        result = await self.service.execute(op.nonce, **self.ids)
        self.assertEqual(result.state, 'success')
        self.assertEqual(result.actual, op.desired)
        self.assertEqual(self.client.xray_posts, 1)
        self.assertEqual(result.job_id, 17)
        self.assertEqual(self.store.get('m').job_id, 17)

    async def test_panel_preserves_exact_run_id(self):
        op = await self.prepare('panel')
        result = await self.service.execute(op.nonce, **self.ids)
        self.assertEqual(result.state, 'success')
        self.assertEqual(result.upstream_run_id, '1735689600123456789')
        self.assertEqual(self.client.panel_posts, 1)

    async def test_xray_downgrade(self):
        op = await self.prepare(value='v25.7.26')
        result = await self.service.execute(op.nonce, **self.ids)
        self.assertEqual(result.state, 'success')

    async def test_cancel_keeps_backup_without_install(self):
        op = await self.prepare()
        result = await self.service.cancel(op.nonce, **self.ids)
        self.assertEqual(result.state, 'cancelled')
        self.assertTrue(Path(op.backup).is_file())
        with self.assertRaises(UpdateError):
            await self.service.execute(op.nonce, **self.ids)
        self.assertEqual(self.client.xray_posts, 0)

    async def test_cancel_from_new_panel_same_actor_chat(self):
        op = await self.prepare()
        result = await self.service.cancel(op.nonce, **(self.ids | {'message': 21}))
        self.assertEqual(result.state, 'cancelled')

    async def test_used_confirmation_cannot_replay(self):
        op = await self.prepare()
        await self.service.execute(op.nonce, **self.ids)
        with self.assertRaises(UpdateError):
            await self.service.execute(op.nonce, **self.ids)
        self.assertEqual(self.client.xray_posts, 1)

    async def test_confirmation_bound_to_actor_chat_message(self):
        op = await self.prepare()
        for change in [{'actor': 2}, {'chat': 11}, {'message': 21}]:
            with self.subTest(change=change), self.assertRaises(UpdateError):
                await self.service.execute(op.nonce, **(self.ids | change))
        self.assertEqual(self.client.xray_posts, 0)

    async def test_expired_confirmation(self):
        op = await self.prepare()
        op.expires = time.time() - 1
        self.store.save(op)
        with self.assertRaises(UpdateError):
            await self.service.execute(op.nonce, **self.ids)
        self.assertEqual(self.store.get('m').state, 'expired')
        self.assertEqual(self.client.xray_posts, 0)

    async def test_changed_connection_is_blocked(self):
        op = await self.prepare()
        self.target = replace(self.target, fingerprint='changed')
        result = await self.service.execute(op.nonce, **self.ids)
        self.assertEqual(result.state, 'failed')
        self.assertEqual(self.client.xray_posts, 0)

    async def test_node_goes_offline_after_preflight(self):
        op = await self.prepare()
        self.target = replace(self.target, eligible=False)
        result = await self.service.execute(op.nonce, **self.ids)
        self.assertEqual(result.state, 'failed')
        self.assertEqual(self.client.xray_posts, 0)

    async def test_prepared_fleet_rollout_can_execute_in_intentional_maintenance(self):
        op = await self.prepare()
        self.target = replace(self.target, eligible=False)
        result = await self.service.execute(
            op.nonce,
            allow_prepared_maintenance=True,
            **self.ids,
        )
        self.assertEqual(result.state, 'success')
        self.assertEqual(self.client.xray_posts, 1)

    async def test_offline_target_cannot_prepare(self):
        self.target = replace(self.target, eligible=False)
        with self.assertRaises(UpdateError):
            await self.prepare()
        self.assertEqual(self.backups, 0)

    async def test_changed_backup_is_blocked(self):
        op = await self.prepare()
        Path(op.backup).write_bytes(b'tampered')
        result = await self.service.execute(op.nonce, **self.ids)
        self.assertEqual(result.state, 'failed')
        self.assertEqual(self.client.xray_posts, 0)

    async def test_missing_backup_is_blocked(self):
        op = await self.prepare()
        Path(op.backup).unlink()
        result = await self.service.execute(op.nonce, **self.ids)
        self.assertEqual(result.state, 'failed')
        self.assertEqual(self.client.xray_posts, 0)

    async def test_unavailable_version_cannot_prepare(self):
        with self.assertRaises(UpdateError):
            await self.prepare(value='v99.99.99')
        self.assertEqual(self.backups, 0)

    async def test_removed_version_cannot_install(self):
        op = await self.prepare()
        self.client.available.remove(op.desired)
        result = await self.service.execute(op.nonce, **self.ids)
        self.assertEqual(result.state, 'failed')
        self.assertEqual(self.client.xray_posts, 0)

    async def test_installed_version_changed(self):
        op = await self.prepare()
        self.client.xray = 'v25.10.31'
        result = await self.service.execute(op.nonce, **self.ids)
        self.assertEqual(result.state, 'failed')
        self.assertEqual(self.client.xray_posts, 0)

    async def test_unknown_current_xray_is_blocked(self):
        self.client.xray = 'Unknown'
        with self.assertRaises(UpdateError):
            await self.prepare()

    async def test_already_installed_is_not_reinstalled(self):
        with self.assertRaises(UpdateError):
            await self.prepare(value='v25.8.1')
        self.assertEqual(self.client.xray_posts, 0)

    async def test_read_only_and_support_cannot_prepare(self):
        for actor in [3, 4]:
            with self.subTest(actor=actor), self.assertRaises(UpdateError):
                await self.service.prepare('m', 'xray', 'v25.9.15', **(self.ids | {'actor': actor}))
        self.assertEqual(self.backups, 0)

    async def test_role_revoked_after_prepare(self):
        op = await self.prepare()
        self.roles[1] = 10
        with self.assertRaises(UpdateError):
            await self.service.execute(op.nonce, **self.ids)
        self.assertEqual(self.client.xray_posts, 0)

    async def test_role_rechecked_after_network_preflight(self):
        op = await self.prepare()
        old_check = self.service._check_version
        async def check(*args):
            await old_check(*args)
            self.roles[1] = 10
        self.service._check_version = check
        result = await self.service.execute(op.nonce, **self.ids)
        self.assertEqual(result.state, 'failed')
        self.assertEqual(self.client.xray_posts, 0)

    async def test_overlapping_execution_is_rejected(self):
        op = await self.prepare()
        self.client.entered = asyncio.Event()
        self.client.release = asyncio.Event()
        task = asyncio.create_task(self.service.execute(op.nonce, **self.ids))
        await self.client.entered.wait()
        try:
            with self.assertRaises(UpdateError):
                await self.service.execute(op.nonce, **self.ids)
        finally:
            self.client.release.set()
        self.assertEqual((await task).state, 'success')
        self.assertEqual(self.client.xray_posts, 1)

    async def test_one_pending_confirmation_per_target(self):
        await self.prepare()
        with self.assertRaises(UpdateError):
            await self.prepare()
        self.assertEqual(self.backups, 1)

    async def test_lost_response_verified_without_retry(self):
        op = await self.prepare()
        self.client.install_error = VersionAPIError('lost response', uncertain=True)
        result = await self.service.execute(op.nonce, **self.ids)
        self.assertEqual(result.state, 'success')
        self.assertEqual(self.client.xray_posts, 1)

    async def test_unknown_outcome_survives_restart(self):
        op = await self.prepare()
        self.client.install_error = VersionAPIError('lost response', uncertain=True)
        self.client.change_version = False
        result = await self.service.execute(op.nonce, **self.ids)
        self.assertEqual(result.state, 'unconfirmed')
        self.store = OperationStore(self.root / 'journal')
        self.service = self.make_service()
        with self.assertRaises(UpdateError):
            await self.prepare()
        self.client.xray = op.desired
        checked = await self.service.recheck(op.nonce, actor=3)
        self.assertEqual(checked.state, 'success')
        self.assertEqual(self.client.xray_posts, 1)

    async def test_stale_panel_run_result_does_not_count(self):
        op = await self.prepare('panel')
        self.client.reported_run_id = 'old-run'
        result = await self.service.execute(op.nonce, **self.ids)
        self.assertEqual(result.state, 'unconfirmed')
        self.assertEqual(self.client.panel_posts, 1)

    async def test_explicit_panel_updater_failure(self):
        op = await self.prepare('panel')
        self.client.update_outcome = 'failed'
        result = await self.service.execute(op.nonce, **self.ids)
        self.assertEqual(result.state, 'failed')

    async def test_stopped_xray_is_not_success(self):
        op = await self.prepare()
        self.client.state = 'stopped'
        result = await self.service.execute(op.nonce, **self.ids)
        self.assertEqual(result.state, 'unconfirmed')

    async def test_changed_stable_release_requires_new_confirmation(self):
        op = await self.prepare('panel')
        self.stable = 'v3.8.7'
        result = await self.service.execute(op.nonce, **self.ids)
        self.assertEqual(result.state, 'failed')
        self.assertEqual(self.client.panel_posts, 0)

    async def test_no_implicit_panel_downgrade(self):
        self.client.panel = '3.9.0'
        with self.assertRaises(UpdateError):
            await self.prepare('panel')
        self.assertEqual(self.backups, 0)

    async def test_backup_failure_never_dispatches(self):
        self.bad_backup = True
        with self.assertRaises(UpdateError):
            await self.prepare()
        self.assertEqual(self.store.get('m').state, 'failed')
        self.assertEqual(self.client.xray_posts, 0)

    async def test_audit_start_failure_never_dispatches(self):
        op = await self.prepare()
        self.record_failure = 'started'
        result = await self.service.execute(op.nonce, **self.ids)
        self.assertEqual(result.state, 'failed')
        self.assertEqual(self.client.xray_posts, 0)

    async def test_cancelled_handler_leaves_durable_uncertainty(self):
        op = await self.prepare()
        self.client.entered = asyncio.Event()
        self.client.release = asyncio.Event()
        task = asyncio.create_task(self.service.execute(op.nonce, **self.ids))
        await self.client.entered.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(self.store.get('m').state, 'unconfirmed')
        with self.assertRaises(UpdateError):
            await self.prepare()

    async def test_owner_unlock_is_explicit_and_does_not_retry(self):
        op = await self.prepare()
        self.client.change_version = False
        await self.service.execute(op.nonce, **self.ids)
        with self.assertRaises(UpdateError):
            await self.service.acknowledge(op.nonce, actor=2, phrase=f'UNLOCK {op.nonce}')
        with self.assertRaises(UpdateError):
            await self.service.acknowledge(op.nonce, actor=1, phrase='UNLOCK')
        result = await self.service.acknowledge(op.nonce, actor=1, phrase=f'UNLOCK {op.nonce}')
        self.assertEqual(result.state, 'acknowledged')
        self.assertEqual(result.acknowledged_by, 1)
        self.assertEqual(self.client.xray_posts, 1)
        await self.prepare()
        self.assertEqual(self.client.xray_posts, 1)

    async def test_renderer_replacement_rebinds_confirmation(self):
        op = await self.prepare()
        await self.service.rebind(op.nonce, actor=1, chat=10, old_message=20, new_message=21)
        with self.assertRaises(UpdateError):
            await self.service.execute(op.nonce, **self.ids)
        result = await self.service.execute(op.nonce, **(self.ids | {'message': 21}))
        self.assertEqual(result.state, 'success')

    async def test_corrupt_journal_fails_closed(self):
        await self.prepare()
        (self.store.root / 'target-m.json').write_text('{broken')
        with self.assertRaises(UpdateError):
            await self.prepare()
        self.assertEqual(self.client.xray_posts, 0)

    async def test_private_journal_and_no_credentials(self):
        op = await self.prepare()
        path = self.store.root / 'target-m.json'
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        data = json.loads(path.read_text())
        self.assertNotIn('client', data)
        self.assertNotIn('token', data)
        self.assertEqual(data['nonce'], op.nonce)

    def test_arbitrary_errors_do_not_expose_credentials(self):
        text = safe_error(RuntimeError('token=TOPSECRET https://private/secret'))
        self.assertNotIn('TOPSECRET', text)
        self.assertNotIn('https://', text)

    def test_target_nonce_traversal_rejected(self):
        with self.assertRaises(UpdateError):
            self.store.get('../bad')
        with self.assertRaises(UpdateError):
            self.store.by_nonce('../bad')


if __name__ == '__main__':
    unittest.main()
