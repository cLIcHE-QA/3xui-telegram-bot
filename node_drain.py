from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
import re
import secrets
import tempfile
import time
from typing import Any

from provisioning import ProvisioningEngine, is_managed_inbound
from xui import XUIClient, XUIError, XUIMutationError


DRAIN_ID_RE = re.compile(r"^[0-9a-f]{12}$")


class NodeDrainError(RuntimeError):
    pass


class NodeDrainBlocked(NodeDrainError):
    pass


class NodeDrainUnknown(NodeDrainError):
    """A mutation may have happened; callers must not replay it automatically."""


@dataclass(frozen=True)
class DrainUserReview:
    telegram_id: int
    target_inbound_ids: tuple[int, ...]
    alternative_inbound_ids: tuple[int, ...]
    missing_alternative_ids: tuple[int, ...]
    blocker: str = ""


@dataclass(frozen=True)
class DrainReview:
    node_id: int
    node_name: str
    target_inbound_ids: tuple[int, ...]
    users: tuple[DrainUserReview, ...]
    blockers: int

    @property
    def affected_users(self) -> int:
        return sum(1 for item in self.users if item.target_inbound_ids)

    @property
    def movable_users(self) -> int:
        return sum(1 for item in self.users if item.target_inbound_ids and not item.blocker)


class DrainPlanStore:
    """Private persistent journal for Node Drain orchestration.

    The journal intentionally stores stable Telegram/user and inbound identifiers,
    never emails, subscription URLs, sub_id values or credentials.
    """

    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        os.chmod(self.root, 0o700)

    def _path(self, plan_id: str) -> Path:
        if not DRAIN_ID_RE.fullmatch(plan_id or ""):
            raise NodeDrainError("Некорректный ID Node Drain.")
        return self.root / f"drain-{plan_id}.json"

    def save(self, plan: dict[str, Any]) -> None:
        path = self._path(str(plan["id"]))
        fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", dir=str(self.root))
        tmp = Path(tmp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(plan, handle, ensure_ascii=False, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(tmp, 0o600)
            os.replace(tmp, path)
        finally:
            tmp.unlink(missing_ok=True)

    def create(self, review: DrainReview, *, actor_id: int) -> dict[str, Any]:
        now = int(time.time())
        plan = {
            "id": secrets.token_hex(6),
            "node_id": int(review.node_id),
            "node_name": review.node_name,
            "actor": int(actor_id),
            "state": "review",
            "created_at": now,
            "updated_at": now,
            "target_inbound_ids": list(review.target_inbound_ids),
            "users": [asdict(item) for item in review.users],
            "blockers": int(review.blockers),
            "results": {},
            "job_id": 0,
        }
        self.save(plan)
        return plan

    def get(self, plan_id: str) -> dict[str, Any]:
        path = self._path(plan_id)
        if not path.is_file():
            raise NodeDrainError("Node Drain не найден.")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise NodeDrainError("Журнал Node Drain недоступен для чтения.") from exc
        if not isinstance(data, dict) or data.get("id") != plan_id:
            raise NodeDrainError("Журнал Node Drain не прошёл проверку идентичности.")
        return data

    def list(self) -> list[dict[str, Any]]:
        plans: list[dict[str, Any]] = []
        for path in sorted(self.root.glob("drain-*.json"), reverse=True):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(data, dict) and DRAIN_ID_RE.fullmatch(str(data.get("id") or "")):
                plans.append(data)
        return plans

    def latest_for_node(self, node_id: int) -> dict[str, Any] | None:
        matches = [p for p in self.list() if int(p.get("node_id") or 0) == int(node_id)]
        if not matches:
            return None
        return max(matches, key=lambda p: int(p.get("updated_at") or 0))


class NodeDrainService:
    def __init__(self, db, xui: XUIClient, settings):
        self.db = db
        self.xui = xui
        self.settings = settings
        self.provisioner = ProvisioningEngine(db, xui, settings)

    async def _direct_node(self, node_id: int):
        if int(node_id) <= 0:
            raise NodeDrainError("Node Drain доступен только для direct node со stable node_id.")
        node = await self.xui.node_get(int(node_id))
        if getattr(node, "transitive", False):
            raise NodeDrainError("Node Drain транзитной ноды запрещён.")
        if int(getattr(node, "id", 0) or 0) != int(node_id):
            raise NodeDrainError("3x-ui вернул неоднозначную identity ноды.")
        return node

    async def _target_inbound_ids(self, node_id: int) -> set[int]:
        options = await self.xui.inbound_options()
        return {
            int(item.id)
            for item in options
            if item.enable
            and item.node_id is not None
            and int(item.node_id) == int(node_id)
            and is_managed_inbound(self.settings, item)
        }

    @staticmethod
    def _current_ids(obj: dict[str, Any]) -> set[int]:
        return {int(value) for value in (obj.get("inboundIds") or [])}

    async def _policy_alternatives(self, telegram_id: int, node_id: int) -> set[int]:
        policy = await self.provisioner.policy_for_user(int(telegram_id))
        alternatives: set[int] = set()
        for inbound_id in policy.actionable_inbound_ids:
            item = policy.inbounds.get(int(inbound_id))
            if item is None:
                continue
            if item.node_id is not None and int(item.node_id) == int(node_id):
                continue
            alternatives.add(int(inbound_id))
        return alternatives

    async def review(self, node_id: int) -> DrainReview:
        node = await self._direct_node(node_id)
        target_ids = await self._target_inbound_ids(node_id)
        users: list[DrainUserReview] = []
        blockers = 0

        for rec in await self.db.list_users():
            telegram_id = int(rec.telegram_id)
            try:
                current = self._current_ids(await self.xui.get_client(rec.email))
            except XUIError:
                blockers += 1
                users.append(DrainUserReview(
                    telegram_id=telegram_id,
                    target_inbound_ids=(),
                    alternative_inbound_ids=(),
                    missing_alternative_ids=(),
                    blocker="client_read_failed",
                ))
                continue

            affected = tuple(sorted(current & target_ids))
            if not affected:
                continue
            try:
                alternatives = await self._policy_alternatives(telegram_id, node_id)
            except Exception:
                alternatives = set()

            blocker = ""
            if not alternatives:
                blocker = "no_policy_alternative"
                blockers += 1
            users.append(DrainUserReview(
                telegram_id=telegram_id,
                target_inbound_ids=affected,
                alternative_inbound_ids=tuple(sorted(alternatives)),
                missing_alternative_ids=tuple(sorted(alternatives - current)),
                blocker=blocker,
            ))

        return DrainReview(
            node_id=int(node_id),
            node_name=str(getattr(node, "name", f"Node {node_id}")),
            target_inbound_ids=tuple(sorted(target_ids)),
            users=tuple(users),
            blockers=blockers,
        )

    async def _read_current(self, telegram_id: int) -> tuple[Any, set[int]]:
        rec = await self.db.get(int(telegram_id))
        if rec is None:
            raise NodeDrainBlocked("Пользователь отсутствует в локальной БД.")
        try:
            current = self._current_ids(await self.xui.get_client(rec.email))
        except XUIError as exc:
            raise NodeDrainUnknown("Не удалось доказать текущее назначение пользователя.") from exc
        return rec, current

    async def evacuate_user(self, node_id: int, telegram_id: int) -> dict[str, Any]:
        await self._direct_node(node_id)
        target_ids = await self._target_inbound_ids(node_id)
        rec, current = await self._read_current(telegram_id)
        affected = current & target_ids
        if not affected:
            return {"status": "skipped", "attached": [], "detached": []}

        alternatives = await self._policy_alternatives(telegram_id, node_id)
        if not alternatives:
            raise NodeDrainBlocked("Для пользователя нет подтверждённой policy alternative.")

        missing = sorted(alternatives - current)
        attached: list[int] = []
        if missing:
            try:
                await self.xui.attach_client(rec.email, missing)
            except XUIMutationError as exc:
                if not exc.uncertain:
                    raise NodeDrainError("3x-ui отклонил подключение альтернативных Inbounds.") from exc
                _, readback = await self._read_current(telegram_id)
                if not set(missing).issubset(readback):
                    raise NodeDrainUnknown(
                        "Результат attach альтернативных Inbounds неизвестен; mutation не повторялась."
                    ) from exc
            attached = missing

        _, after_attach = await self._read_current(telegram_id)
        confirmed_alternatives = after_attach & alternatives
        if not confirmed_alternatives:
            raise NodeDrainBlocked("Альтернативный Inbound не подтверждён; detach запрещён.")

        detach_ids = sorted(after_attach & target_ids)
        if not detach_ids:
            return {"status": "success", "attached": attached, "detached": []}

        # Attach-before-detach safety: this is the final guard immediately before mutation.
        if not (after_attach - set(detach_ids)):
            raise NodeDrainBlocked("Detach оставил бы пользователя без единого Inbound.")

        try:
            await self.xui.detach_client(rec.email, detach_ids)
        except XUIMutationError as exc:
            if not exc.uncertain:
                raise NodeDrainError("3x-ui отклонил detach Inbounds выводимой ноды.") from exc
            _, readback = await self._read_current(telegram_id)
            if set(detach_ids) & readback:
                raise NodeDrainUnknown(
                    "Результат detach Inbounds неизвестен; mutation не повторялась."
                ) from exc

        _, final_ids = await self._read_current(telegram_id)
        if set(detach_ids) & final_ids:
            raise NodeDrainUnknown("Post-condition detach не подтверждён.")
        if not (final_ids & alternatives):
            raise NodeDrainUnknown("Post-condition альтернативного Inbound не подтверждён.")
        if not final_ids:
            raise NodeDrainUnknown("Post-condition оставил пользователя без Inbounds.")

        return {
            "status": "success",
            "attached": attached,
            "detached": detach_ids,
        }
