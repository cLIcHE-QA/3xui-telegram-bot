from __future__ import annotations

import os
import sqlite3
import stat
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import aiohttp
from aiogram.enums import ChatType
from aiogram.types import Chat, Message, User

from admin_ui import AdminPrivateChatMiddleware
from backup_manager import BackupManager
from db import Database
from logging_setup import _prepare_private_log_path
from subscription_proxy import SubscriptionProxy
from system_backup import SystemBackupService


ROOT = Path(__file__).resolve().parents[1]


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def _make_sqlite(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE sample(value TEXT NOT NULL)")
        db.execute("INSERT INTO sample(value) VALUES ('ok')")
        db.commit()


def _message(chat_type: ChatType) -> Message:
    kwargs = {"title": "test"} if chat_type != ChatType.PRIVATE else {}
    return Message(
        message_id=1,
        date=datetime.now(timezone.utc),
        chat=Chat(
            id=-100123 if chat_type != ChatType.PRIVATE else 123,
            type=chat_type,
            **kwargs,
        ),
        from_user=User(id=123, is_bot=False, first_name="Admin"),
        text="/admin",
    )


class _FakeResponse:
    def __init__(
        self,
        status: int,
        *,
        url: str,
        headers: dict[str, str] | None = None,
        body: bytes = b"",
    ):
        self.status = status
        self.url = url
        self.headers = headers or {}
        self._body = body

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def read(self) -> bytes:
        return self._body


class _FakeSession:
    def __init__(self, responses: list[_FakeResponse]):
        self.responses = list(responses)
        self.calls: list[dict[str, object]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def get(self, url, **kwargs):
        self.calls.append({"url": str(url), **kwargs})
        if not self.responses:
            raise AssertionError("unexpected extra upstream request")
        return self.responses.pop(0)


class AdminPrivateChatBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_admin_middleware_blocks_group_and_allows_private(self):
        middleware = AdminPrivateChatMiddleware()

        blocked = AsyncMock(return_value="should-not-run")
        result = await middleware(blocked, _message(ChatType.SUPERGROUP), {})
        self.assertIsNone(result)
        blocked.assert_not_awaited()

        allowed = AsyncMock(return_value="ok")
        result = await middleware(allowed, _message(ChatType.PRIVATE), {})
        self.assertEqual(result, "ok")
        allowed.assert_awaited_once()

    def test_all_admin_routers_receive_private_chat_middleware(self):
        runtime = (ROOT / "app_runtime.py").read_text(encoding="utf-8")
        shell = (ROOT / "admin_shell.py").read_text(encoding="utf-8")
        auth = (ROOT / "admin_auth.py").read_text(encoding="utf-8")
        router_block = runtime.split("ADMIN_ROUTERS = (", 1)[1].split(")", 1)[0]

        self.assertIn("router.message.outer_middleware(AdminPrivateChatMiddleware())", runtime)
        self.assertIn("router.callback_query.outer_middleware(AdminPrivateChatMiddleware())", runtime)
        self.assertNotIn("client_access_router", router_block)
        self.assertIn("if not is_private_admin_event(message):", shell)
        self.assertIn("if not is_private_admin_event(call):", auth)


class SubscriptionRedirectSecurityTests(unittest.IsolatedAsyncioTestCase):
    async def _fetch_with(self, responses: list[_FakeResponse]):
        session = _FakeSession(responses)
        proxy = SubscriptionProxy(None, "https://upstream.example.test/sub/{sub_id}")
        with patch("subscription_proxy.aiohttp.ClientSession", return_value=session):
            result = await proxy._fetch(
                "https://upstream.example.test/start",
                headers={
                    "Accept": "text/plain",
                    "User-Agent": "Client/1.0",
                    "X-HWID": "device-id",
                    "X-Device-OS": "Linux",
                    "X-Ver-OS": "test",
                    "X-Device-Model": "test-model",
                },
            )
        return session, result

    async def test_same_origin_redirect_keeps_device_headers(self):
        session, result = await self._fetch_with([
            _FakeResponse(
                302,
                url="https://upstream.example.test/start",
                headers={"Location": "/final"},
            ),
            _FakeResponse(
                200,
                url="https://upstream.example.test/final",
                body=b"ok",
            ),
        ])

        self.assertEqual(result[0], 200)
        self.assertFalse(session.calls[0]["allow_redirects"])
        self.assertEqual(session.calls[1]["headers"]["X-HWID"], "device-id")

    async def test_cross_origin_redirect_strips_device_headers_irreversibly(self):
        session, result = await self._fetch_with([
            _FakeResponse(
                302,
                url="https://upstream.example.test/start",
                headers={"Location": "https://other.example.test/step"},
            ),
            _FakeResponse(
                302,
                url="https://other.example.test/step",
                headers={"Location": "https://upstream.example.test/final"},
            ),
            _FakeResponse(
                200,
                url="https://upstream.example.test/final",
                body=b"ok",
            ),
        ])

        self.assertEqual(result[0], 200)
        for call in session.calls[1:]:
            forwarded = call["headers"]
            self.assertNotIn("X-HWID", forwarded)
            self.assertNotIn("X-Device-OS", forwarded)
            self.assertNotIn("X-Ver-OS", forwarded)
            self.assertNotIn("X-Device-Model", forwarded)
            self.assertEqual(forwarded["User-Agent"], "Client/1.0")

    async def test_https_redirect_cannot_downgrade_tls(self):
        session = _FakeSession([
            _FakeResponse(
                302,
                url="https://upstream.example.test/start",
                headers={"Location": "http://upstream.example.test/final"},
            ),
        ])
        proxy = SubscriptionProxy(None, "https://upstream.example.test/sub/{sub_id}")

        with patch("subscription_proxy.aiohttp.ClientSession", return_value=session):
            with self.assertRaises(aiohttp.ClientError):
                await proxy._fetch(
                    "https://upstream.example.test/start",
                    headers={"X-HWID": "device-id"},
                )

        self.assertEqual(len(session.calls), 1)


class SensitiveArtifactModeTests(unittest.IsolatedAsyncioTestCase):
    async def test_backup_db_and_log_modes_ignore_permissive_umask(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_db = root / "source" / "bot.sqlite3"
            _make_sqlite(source_db)
            backup_dir = root / "backups"
            manager = BackupManager(str(source_db), str(backup_dir), keep=3)
            manager.sources_root = root / "sources"
            manager.sources_root.mkdir(parents=True)
            master_db = manager.sources_root / "x-ui" / "x-ui.db"
            _make_sqlite(master_db)
            (manager.sources_root / "bot.env").write_text(
                "TEST_ONLY=value\n",
                encoding="utf-8",
            )

            old_umask = os.umask(0)
            try:
                snapshot = manager.create_bot_snapshot()
                full = manager.create_full_backup(version="4.26.6-test")
                runtime_db = root / "runtime" / "bot.sqlite3"
                await Database(str(runtime_db)).init()
                log_path = root / "runtime" / "logs" / "bot.log"
                _prepare_private_log_path(log_path)
            finally:
                os.umask(old_umask)

            self.assertEqual(_mode(backup_dir), 0o700)
            self.assertEqual(_mode(snapshot), 0o600)
            self.assertEqual(_mode(full.info.path), 0o600)
            self.assertEqual(_mode(runtime_db.parent), 0o700)
            self.assertEqual(_mode(runtime_db), 0o600)
            self.assertEqual(_mode(log_path.parent), 0o700)
            self.assertEqual(_mode(log_path), 0o600)

    def test_existing_artifacts_are_tightened_and_node_archive_is_private(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_db = root / "source.sqlite3"
            _make_sqlite(source_db)
            manager = BackupManager(str(source_db), str(root / "backups"), keep=3)

            leaky = manager.backup_dir / "old" / "historical.tar.gz"
            leaky.parent.mkdir(parents=True)
            leaky.write_bytes(b"test")
            os.chmod(leaky.parent, 0o755)
            os.chmod(leaky, 0o644)

            manager.list_backups()
            self.assertEqual(_mode(leaky.parent), 0o700)
            self.assertEqual(_mode(leaky), 0o600)

            node_dir = root / "node"
            node_dir.mkdir()
            (node_dir / "x-ui.db").write_bytes(b"test")
            node_archive = root / "node-snapshot.tar.gz"
            old_umask = os.umask(0)
            try:
                SystemBackupService._write_node_archive(
                    node_archive,
                    node_dir,
                    "edge",
                )
            finally:
                os.umask(old_umask)

            self.assertEqual(_mode(node_archive), 0o600)


if __name__ == "__main__":
    unittest.main()
