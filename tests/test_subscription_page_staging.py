"""#887 D2d: offline-only staging gates; NEVER call a real Bot API."""
from __future__ import annotations

import asyncio
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from aiohttp.test_utils import TestClient, TestServer

from subscription_page_pilot_wiring import build_isolated_pilot
from subscription_page_staging import (
    StagingConfig, load_staging_config, read_staging_bot_token,
    run_approved_staging, verify_staging_bot,
)

OWNER = 100_001
ORIGIN = "https://staging.example.invalid"


class StagingConfigTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="d2d-synthetic-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.token_path = self.root / "staging-bot.token"
        self.conf_path = self.root / "staging-config.json"
        self.values = {
            "mode": "isolated-staging", "enabled": False, "edge_reviewed": False,
            "https_origin": ORIGIN,
            "bot_token_file": str(self.token_path),
            "expected_bot_id": 900001,
            "expected_bot_username": "StagingExampleBot",
            "pilot_ids": [OWNER],
            "sqlite_path": str(self.root / "standalone-pilot.sqlite3"),
            "loopback_port": 8827,
        }

    def config(self, **changes) -> StagingConfig:
        return StagingConfig.parse(self.values | changes)

    def write_private(self, path: Path, content: str) -> None:
        path.write_text(content, encoding="utf-8")
        path.chmod(0o600)

    def test_default_off_has_no_external_or_runtime_activity(self):
        config = self.config()
        self.assertFalse(config.enabled)
        self.assertFalse(config.edge_reviewed)
        with patch("subscription_page_staging.read_staging_bot_token") as secret:
            with self.assertRaises(ValueError):
                asyncio.run(self._off(config))
            secret.assert_not_called()

    async def _off(self, config):
        await run_approved_staging(config, explicitly_enabled=False)

    async def test_default_off_and_unaudited_edge_never_read_bot_token(self):
        with patch("subscription_page_staging.read_staging_bot_token") as secret:
            with self.assertRaises(ValueError):
                await run_approved_staging(self.config(enabled=False, edge_reviewed=True),
                                           explicitly_enabled=True)
            with self.assertRaises(ValueError):
                await run_approved_staging(self.config(enabled=True, edge_reviewed=False),
                                           explicitly_enabled=True)
            with self.assertRaises(ValueError):
                await run_approved_staging(self.config(enabled=True, edge_reviewed=True),
                                           explicitly_enabled=False)
            with self.assertRaises(ValueError):
                await run_approved_staging(self.config(enabled=True, edge_reviewed=True),
                                           explicitly_enabled=True)
            secret.assert_not_called()

    def test_staging_origin_username_and_exact_fields_are_required(self):
        invalid = [
            {"mode": "production"}, {"enabled": 1}, {"edge_reviewed": "true"},
            {"https_origin": "https://example.invalid"},
            {"https_origin": "http://staging.example.invalid"},
            {"https_origin": "https://staging.example.invalid/"},
            {"https_origin": "https://staging.example.invalid?x=1"},
            {"https_origin": "https://staging.example.invalid:443"},
            {"https_origin": "https://user@staging.example.invalid"},
            {"https_origin": "https://127.0.0.1"},
            {"https_origin": "https://staging.example.invalid."},
            {"https_origin": "https://staging..example.invalid"},
            {"expected_bot_id": True}, {"expected_bot_id": 0},
            {"expected_bot_username": "ProductionBot"},
            {"expected_bot_username": "staging-evilbot"},
            {"pilot_ids": []}, {"pilot_ids": [OWNER, OWNER]},
            {"pilot_ids": [OWNER, "100002"]}, {"pilot_ids": list(range(9))},
            {"loopback_port": 0}, {"loopback_port": True},
            {"bot_token_file": "/tmp/production.token"},
            {"sqlite_path": "/tmp/bot.sqlite3"},
        ]
        for change in invalid:
            with self.subTest(change=change):
                with self.assertRaises(ValueError):
                    self.config(**change)
        for name in ("extra",):
            with self.assertRaises(ValueError):
                StagingConfig.parse(self.values | {name: "unexpected"})

    def test_private_file_permissions_and_symlinks(self):
        self.write_private(self.conf_path, json.dumps(self.values))
        self.assertEqual(load_staging_config(str(self.conf_path)).pilot_ids, frozenset({OWNER}))
        self.conf_path.chmod(0o644)
        with self.assertRaises(ValueError):
            load_staging_config(str(self.conf_path))
        self.conf_path.chmod(0o600)
        self.root.chmod(0o755)
        with self.assertRaises(ValueError):
            load_staging_config(str(self.conf_path))
        self.root.chmod(0o700)
        copied = self.root / "staging-config-symlink.json"
        copied.symlink_to(self.conf_path)
        with self.assertRaises(ValueError):
            load_staging_config(str(copied))
        with self.assertRaises(ValueError):
            load_staging_config(str(self.root / "other.json"))

    def test_bot_token_is_private_and_bound_to_expected_identity(self):
        config = self.config()
        synthetic = "900001:" + "A" * 35
        self.write_private(self.token_path, synthetic + "\n")
        self.assertEqual(read_staging_bot_token(config), synthetic)
        self.write_private(self.token_path, "900002:" + "A" * 35)
        with self.assertRaises(ValueError):
            read_staging_bot_token(config)
        self.write_private(self.token_path, "900001:invalid")
        with self.assertRaises(ValueError):
            read_staging_bot_token(config)
        self.write_private(self.token_path, synthetic)
        self.token_path.chmod(0o644)
        with self.assertRaises(ValueError):
            read_staging_bot_token(config)

    async def test_verified_bot_identity_and_webhook_fail_closed(self):
        config = self.config()
        bot = SimpleNamespace(
            get_me=AsyncMock(return_value=SimpleNamespace(
                id=900001, is_bot=True, username="StagingExampleBot")),
            get_webhook_info=AsyncMock(return_value=SimpleNamespace(url="")),
        )
        await verify_staging_bot(bot, config)
        bot.get_me.return_value.username = "ProductionBot"
        with self.assertRaises(ValueError):
            await verify_staging_bot(bot, config)
        bot.get_me.return_value.username = "StagingExampleBot"
        bot.get_webhook_info.return_value.url = "https://example.invalid/webhook"
        with self.assertRaises(ValueError):
            await verify_staging_bot(bot, config)

    async def test_staging_shows_whole_code_only_after_owner_private_guard(self):
        path = str(self.root / "standalone-pilot.sqlite3")
        service = SimpleNamespace(profile=AsyncMock(return_value=SimpleNamespace(exists=True)))
        flags = SimpleNamespace(snapshot=AsyncMock(
            return_value=SimpleNamespace(portal_enabled=True)))
        bundle = build_isolated_pilot(
            explicitly_enabled=True, display_full_challenge=True,
            https_origin=ORIGIN, sqlite_path=path,
            customer_service=service, feature_flags=flags,
            pilot_ids=frozenset({OWNER}),
            now=lambda: 1_800_000_000,
        )
        self.assertTrue(bundle.approval.display_full_challenge)
        web = TestClient(TestServer(bundle.app))
        await web.start_server()
        try:
            async with web.post(
                "/api/subpage/v1/auth/standalone/start",
                headers={"Origin": ORIGIN, "Host": "staging.example.invalid"}, json={},
            ) as response:
                self.assertEqual(response.status, 200)
                code = (await response.json())["challenge"]
            def message(*, actor=OWNER, forwarded=False):
                return SimpleNamespace(
                    text="/web_login " + code,
                    from_user=SimpleNamespace(id=actor, is_bot=False),
                    chat=SimpleNamespace(id=actor, type="private"),
                    sender_chat=None,
                    forward_origin="forwarded" if forwarded else None,
                    answer=AsyncMock(return_value=SimpleNamespace(message_id=777)),
                )
            forged = message(actor=100_002)
            await bundle.approval.handle_message(forged)
            forged.answer.assert_not_awaited()
            relay = message(forwarded=True)
            await bundle.approval.handle_message(relay)
            relay.answer.assert_not_awaited()
            own = message()
            await bundle.approval.handle_message(own)
            text = own.answer.await_args.args[0]
            self.assertIn(code, text)
            self.assertIn(ORIGIN, text)
            self.assertIn("ВСЕ 16", text)
            self.assertIn("Отмена", text)
        finally:
            await web.close()

    async def test_default_d2c_does_not_show_full_challenge(self):
        service = SimpleNamespace(profile=AsyncMock(return_value=SimpleNamespace(exists=True)))
        flags = SimpleNamespace(snapshot=AsyncMock(
            return_value=SimpleNamespace(portal_enabled=True)))
        bundle = build_isolated_pilot(
            explicitly_enabled=True,
            https_origin=ORIGIN, sqlite_path=str(self.root / "standalone-pilot.sqlite3"),
            customer_service=service, feature_flags=flags, pilot_ids=frozenset({OWNER}),
        )
        self.assertFalse(bundle.approval.display_full_challenge)
        with self.assertRaises(ValueError):
            build_isolated_pilot(
                explicitly_enabled=True, display_full_challenge=1,
                https_origin=ORIGIN, sqlite_path=str(self.root / "standalone-pilot.sqlite3"),
                customer_service=service, feature_flags=flags, pilot_ids=frozenset({OWNER}),
            )
