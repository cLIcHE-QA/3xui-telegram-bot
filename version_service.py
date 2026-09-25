"""Guarded, two-phase update workflow. This module has no Telegram/DB dependency.

The durable journal contains metadata only. It prevents replay after restart;
flock prevents overlapping operations, including from another local process.
Unconfirmed remote outcomes remain blocked until a read-only verification or an
explicit Owner acknowledgement. Locks cover this workflow, not external admins.
"""
from __future__ import annotations

import asyncio
from contextlib import contextmanager
from dataclasses import asdict, dataclass
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import time
from typing import Any, Awaitable, Callable

from version_api import VersionAPIError, same_version, valid_version, version_order

_TARGET = re.compile(r"(?:m|n[1-9][0-9]{0,18})\Z")
_NONCE = re.compile(r"[0-9a-f]{16}\Z")
UNCERTAIN_STATES = {"dispatching", "verifying", "unconfirmed"}


class UpdateError(RuntimeError):
    pass


@dataclass(frozen=True)
class Target:
    key: str
    name: str
    fingerprint: str
    client: Any
    eligible: bool = True


@dataclass(frozen=True)
class VersionState:
    panel: str = ""
    xray: str = ""
    xray_state: str = "unknown"

    @property
    def healthy(self) -> bool:
        return self.xray_state.lower() in {"running", "started", "online"}


@dataclass(frozen=True)
class BackupReceipt:
    path: str
    sha256: str


@dataclass
class Operation:
    nonce: str
    target: str
    actor: int
    chat: int
    message: int
    component: str
    previous: str
    desired: str
    fingerprint: str
    created: float
    expires: float
    state: str = "preparing"
    backup: str = ""
    backup_sha256: str = ""
    upstream_run_id: str = ""
    actual: str = ""
    xray_state: str = "unknown"
    error: str = ""
    job_id: int = 0
    started: float = 0
    acknowledged_by: int = 0


def file_hash(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_error(exc: BaseException) -> str:
    # Arbitrary API/OS/DB exceptions can contain credentials or secret URLs.
    if isinstance(exc, (UpdateError, VersionAPIError)):
        return str(exc)[:280]
    return f"{type(exc).__name__}; inspect local logs without sharing credentials."


class OperationStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    def _path(self, key: str) -> Path:
        if not _TARGET.fullmatch(key):
            raise UpdateError("Некорректная цель обновления.")
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        return self.root / f"target-{key}.json"

    @contextmanager
    def lock(self, key: str):
        path = self._path(key).with_suffix(".lock")
        fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise UpdateError("Для этой цели уже выполняется операция.") from exc
            yield
        finally:
            os.close(fd)

    def get(self, key: str) -> Operation | None:
        path = self._path(key)
        if not path.exists():
            return None
        try:
            op = Operation(**json.loads(path.read_text(encoding="utf-8")))
            if op.target != key or not _NONCE.fullmatch(op.nonce):
                raise ValueError("invalid operation identity")
            return op
        except (ValueError, TypeError) as exc:
            raise UpdateError("Журнал обновления повреждён; требуется ручная проверка.") from exc

    def by_nonce(self, nonce: str) -> Operation:
        if not _NONCE.fullmatch(nonce):
            raise UpdateError("Некорректное подтверждение.")
        for path in self.root.glob("target-*.json"):
            op = self.get(path.stem.removeprefix("target-"))
            if op and op.nonce == nonce:
                return op
        raise UpdateError("Подтверждение истекло или было заменено. Начни заново.")

    def save(self, op: Operation) -> None:
        path = self._path(op.target)
        temp = path.with_suffix(f".{secrets.token_hex(4)}.tmp")
        try:
            fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(asdict(op), stream, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp, path)
            directory = os.open(self.root, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            temp.unlink(missing_ok=True)


class UpdateService:
    def __init__(
        self, store: OperationStore, *,
        resolve: Callable[[str], Awaitable[Target]],
        snapshot: Callable[[Target], Awaitable[VersionState]],
        stable: Callable[[Target], Awaitable[str]],
        backup: Callable[[Target, str], Awaitable[BackupReceipt]],
        authorize: Callable[[int, str], Awaitable[bool]],
        record: Callable[[Operation, str], Awaitable[None]],
        verify_seconds: float = 120, poll_seconds: float = 3,
        confirmation_seconds: float = 300,
    ):
        self.store = store
        self.resolve = resolve
        self.snapshot = snapshot
        self.stable = stable
        self.backup = backup
        self.authorize = authorize
        self.record = record
        self.verify_seconds = verify_seconds
        self.poll_seconds = poll_seconds
        self.confirmation_seconds = confirmation_seconds

    async def _authorize(self, actor: int, minimum: str = "admin") -> None:
        if not await self.authorize(actor, minimum):
            raise UpdateError(f"Недостаточно прав; требуется роль {minimum}.")

    async def _check_version(
        self,
        target: Target,
        component: str,
        desired: str,
        current: str,
        *,
        allow_prepared_maintenance: bool = False,
    ) -> None:
        if not target.eligible and not allow_prepared_maintenance:
            raise UpdateError("Перед обновлением нода должна быть включена и находиться в сети.")
        if component == "xray":
            if not valid_version(current):
                raise UpdateError("Текущая версия Xray неизвестна; обновление заблокировано.")
            if not valid_version(desired) or desired not in await target.client.get_xray_versions():
                raise UpdateError("Выбранная версия Xray больше недоступна.")
        elif component == "panel":
            if not same_version(desired, await self.stable(target)):
                raise UpdateError("Последний стабильный релиз изменился. Проверь новое подтверждение.")
            if version_order(current) and version_order(desired) < version_order(current):
                raise UpdateError("Этот сценарий не поддерживает откат панели.")
        else:
            raise UpdateError("Неподдерживаемый компонент обновления.")
        if not current:
            raise UpdateError("Текущая версия неизвестна; обновление заблокировано.")
        if same_version(current, desired):
            raise UpdateError("Выбранная версия уже установлена.")

    async def prepare(
        self, key: str, component: str, desired: str, *, actor: int, chat: int, message: int,
    ) -> Operation:
        await self._authorize(actor)
        with self.store.lock(key):
            previous_op = self.store.get(key)
            if previous_op and (
                previous_op.state in UNCERTAIN_STATES
                or (previous_op.state in {"prepared", "preparing", "checking"} and previous_op.expires > time.time())
            ):
                raise UpdateError("Есть незавершённая операция. Сначала проверь или отмени её.")
            target = await self.resolve(key)
            state = await self.snapshot(target)
            if component == "panel":
                desired = await self.stable(target)
            current = state.panel if component == "panel" else state.xray
            await self._check_version(target, component, desired, current)
            now = time.time()
            op = Operation(
                secrets.token_hex(8), key, actor, chat, message, component,
                current, desired, target.fingerprint, now, now + self.confirmation_seconds,
            )
            self.store.save(op)
            try:
                receipt = await self.backup(target, op.nonce)
                if (not Path(receipt.path).is_file()
                        or await asyncio.to_thread(file_hash, receipt.path) != receipt.sha256):
                    raise UpdateError("Не удалось проверить свежую резервную копию.")
                op.backup, op.backup_sha256 = receipt.path, receipt.sha256
                op.expires = time.time() + self.confirmation_seconds
                op.state = "prepared"
                self.store.save(op)
                await self.record(op, "prepared")
                return op
            except BaseException as exc:
                op.state, op.error = "failed", safe_error(exc)
                self.store.save(op)
                if not isinstance(exc, asyncio.CancelledError):
                    await self.record(op, "failed")
                raise

    def _bound(self, op: Operation, actor: int, chat: int, message: int) -> None:
        if (op.actor, op.chat, op.message) != (actor, chat, message):
            raise UpdateError("Это подтверждение относится к другой сессии администратора.")

    async def rebind(self, nonce: str, *, actor: int, chat: int, old_message: int, new_message: int) -> None:
        op = self.store.by_nonce(nonce)
        with self.store.lock(op.target):
            op = self.store.by_nonce(nonce)
            self._bound(op, actor, chat, old_message)
            if op.state != "prepared":
                raise UpdateError("Подтверждение больше не активно.")
            op.message = new_message
            self.store.save(op)

    async def cancel(self, nonce: str, *, actor: int, chat: int, message: int) -> Operation:
        await self._authorize(actor)
        op = self.store.by_nonce(nonce)
        with self.store.lock(op.target):
            op = self.store.by_nonce(nonce)
            if (op.actor, op.chat) != (actor, chat):
                raise UpdateError("Эта незавершённая операция относится к другой сессии администратора.")
            if op.state != "prepared":
                raise UpdateError("Уже отправленное обновление нельзя отменить.")
            op.state = "cancelled"
            self.store.save(op)
            await self.record(op, "cancelled")
            return op

    async def _observe(self, op: Operation, target: Target) -> bool:
        if op.component == "panel" and op.upstream_run_id:
            status = await target.client.get_update_status()
            if str(status.get("runId") or "") != op.upstream_run_id:
                return False  # Never accept an older run's result.
            if status.get("state") == "failed":
                op.state, op.error = "failed", "Средство обновления панели сообщило об ошибке этой операции."
                self.store.save(op)
                return True
            if status.get("state") != "success":
                return False
        state = await self.snapshot(target)
        op.actual = state.panel if op.component == "panel" else state.xray
        op.xray_state = state.xray_state
        if same_version(op.actual, op.desired) and state.healthy:
            op.state, op.error = "success", ""
            self.store.save(op)
            return True
        self.store.save(op)
        return False

    async def _verify(self, op: Operation, target: Target) -> None:
        try:
            async with asyncio.timeout(self.verify_seconds):
                while True:
                    try:
                        if await self._observe(op, target):
                            return
                    except (VersionAPIError, OSError, TimeoutError):
                        pass  # Read-only polling is safe while the panel restarts.
                    await asyncio.sleep(self.poll_seconds)
        except TimeoutError:
            pass
        op.state = "unconfirmed"
        op.error = "Результат не подтверждён. Повторный запрос не отправлялся. Проверь статус перед новым обновлением."
        self.store.save(op)

    async def execute(
        self,
        nonce: str,
        *,
        actor: int,
        chat: int,
        message: int,
        allow_prepared_maintenance: bool = False,
    ) -> Operation:
        await self._authorize(actor)
        op = self.store.by_nonce(nonce)
        with self.store.lock(op.target):
            op = self.store.by_nonce(nonce)
            self._bound(op, actor, chat, message)
            if op.state != "prepared":
                raise UpdateError("Подтверждение уже использовано. Второй запрос не отправлялся.")
            if time.time() >= op.expires:
                op.state = "expired"
                self.store.save(op)
                raise UpdateError("Резервная копия или подтверждение устарели. Создай свежую резервную копию.")
            op.state = "checking"
            self.store.save(op)
            dispatched = False
            try:
                target = await self.resolve(op.target)
                if target.fingerprint != op.fingerprint:
                    raise UpdateError("Подключение к цели изменилось. Начни заново.")
                state = await self.snapshot(target)
                current = state.panel if op.component == "panel" else state.xray
                if not same_version(current, op.previous):
                    raise UpdateError("Установленная версия изменилась после предварительной проверки. Начни заново.")
                await self._check_version(
                    target,
                    op.component,
                    op.desired,
                    current,
                    allow_prepared_maintenance=allow_prepared_maintenance,
                )
                if await asyncio.to_thread(file_hash, op.backup) != op.backup_sha256:
                    raise UpdateError("Контрольная сумма резервной копии изменилась. Обновление заблокировано.")
                await self._authorize(actor)  # Role may have been revoked during preflight.
                op.started = time.time()
                await self.record(op, "started")  # Abort if audit/job recording is unavailable.
                op.state = "dispatching"
                self.store.save(op)
                dispatched = True
                try:
                    response = (await target.client.update_panel() if op.component == "panel"
                                else await target.client.install_xray(op.desired))
                    obj = response.get("obj")
                    if op.component == "panel" and isinstance(obj, dict):
                        op.upstream_run_id = str(obj.get("runId") or "")
                except VersionAPIError as exc:
                    if not exc.uncertain:
                        raise
                    # Request may have succeeded; do not retry the POST.
                op.state = "verifying"
                self.store.save(op)
                await self._verify(op, target)
            except asyncio.CancelledError:
                op.state = "unconfirmed" if dispatched else "failed"
                op.error = "Локальный процесс остановился; перед повторной попыткой проверь удалённую цель."
                self.store.save(op)
                raise
            except Exception as exc:
                explicit_rejection = isinstance(exc, VersionAPIError) and not exc.uncertain
                op.state = "unconfirmed" if dispatched and not explicit_rejection else "failed"
                op.error = safe_error(exc)
                self.store.save(op)
            # A failure to record the result must not undo or repeat the remote operation.
            await self.record(op, op.state)
            return op

    async def recheck(self, nonce: str, *, actor: int) -> Operation:
        await self._authorize(actor, "read_only")
        op = self.store.by_nonce(nonce)
        with self.store.lock(op.target):
            op = self.store.by_nonce(nonce)
            if op.state not in UNCERTAIN_STATES:
                return op
            target = await self.resolve(op.target)
            if target.fingerprint != op.fingerprint:
                raise UpdateError("Подключение к цели изменилось; требуется ручная проверка.")
            try:
                await self._observe(op, target)
            except (VersionAPIError, OSError, TimeoutError):
                pass
            if op.state in UNCERTAIN_STATES:
                op.state = "unconfirmed"
                self.store.save(op)
            await self.record(op, op.state)
            return op

    async def acknowledge(self, nonce: str, *, actor: int, phrase: str) -> Operation:
        await self._authorize(actor, "owner")
        if phrase != f"UNLOCK {nonce}":
            raise UpdateError("Требуется точная фраза подтверждения Owner.")
        op = self.store.by_nonce(nonce)
        with self.store.lock(op.target):
            op = self.store.by_nonce(nonce)
            if op.state not in UNCERTAIN_STATES:
                raise UpdateError("Этой операции не требуется ручное подтверждение результата.")
            op.state = "acknowledged"
            op.acknowledged_by = actor
            op.error = f"Owner {actor} подтвердил непроверенный результат после ручной проверки."
            self.store.save(op)
            await self.record(op, "acknowledged")
            return op
