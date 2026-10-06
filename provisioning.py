from __future__ import annotations

import time
from dataclasses import dataclass, field

from config import Settings
from db import Database, PlanRecord, ServerGroupRecord, UserRecord
from xui import InboundOption, NodeInfo, XUIClient, XUIError, XUIMutationError


class ProvisioningError(RuntimeError):
    pass


class ProvisioningUnknown(ProvisioningError):
    """A mutation may have committed, but read-back could not prove the outcome."""


@dataclass
class ProvisioningPolicy:
    plan: PlanRecord | None
    group: ServerGroupRecord | None
    source: str
    member_keys: set[str] = field(default_factory=set)
    inbound_mode: str = "all_managed"
    selected_inbound_ids: set[int] = field(default_factory=set)
    desired_inbound_ids: list[int] = field(default_factory=list)
    actionable_inbound_ids: list[int] = field(default_factory=list)
    managed_inbound_ids: list[int] = field(default_factory=list)
    unavailable_members: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    inbounds: dict[int, InboundOption] = field(default_factory=dict)
    nodes: dict[int, NodeInfo] = field(default_factory=dict)


@dataclass
class ProvisioningResult:
    policy: ProvisioningPolicy
    current_ids: list[int]
    attached_ids: list[int]
    detached_ids: list[int]
    remaining_missing_ids: list[int]
    extra_ids: list[int]
    limits_applied: bool = False


def is_managed_inbound(settings: Settings, inbound: InboundOption) -> bool:
    exact_ids = set(settings.inbound_ids)
    if inbound.protocol in set(settings.ignored_protocols):
        return False
    tag = (inbound.tag or "").lower()
    if tag in set(settings.ignored_tags) or tag.startswith("api"):
        return False
    if exact_ids and inbound.id not in exact_ids:
        return False
    if settings.allowed_ports and inbound.port not in set(settings.allowed_ports):
        return False
    if settings.allowed_protocols and inbound.protocol not in set(settings.allowed_protocols):
        return False
    return True


def inbound_member_key(inbound: InboundOption) -> str:
    return "master" if inbound.node_id is None else f"node_{int(inbound.node_id)}"


def inbound_label(inbound: InboundOption) -> str:
    server = "Master" if inbound.node_id is None else f"Нода #{inbound.node_id}"
    return f"#{inbound.id} · {server} · {inbound.port}/{inbound.protocol} · {inbound.remark}"


class ProvisioningEngine:
    def __init__(self, db: Database, xui: XUIClient, settings: Settings):
        self.db = db
        self.xui = xui
        self.settings = settings

    async def default_plan(self) -> PlanRecord | None:
        raw = await self.db.get_runtime_setting("default_plan_id", "")
        try:
            plan_id = int(raw or 0)
        except (TypeError, ValueError):
            return None
        if not plan_id:
            return None
        plan = await self.db.get_plan(plan_id)
        if not plan or not plan.active:
            return None
        return plan

    async def _node_map(self) -> tuple[dict[int, NodeInfo], str | None]:
        try:
            nodes = await self.xui.nodes_list()
            return {int(n.id): n for n in nodes}, None
        except XUIError as exc:
            return {}, str(exc)

    async def resolve_group(
        self,
        group_id: int | None,
        *,
        plan: PlanRecord | None = None,
        source: str = "user",
    ) -> ProvisioningPolicy:
        all_options = await self.xui.inbound_options()
        managed = [i for i in all_options if i.enable and is_managed_inbound(self.settings, i)]
        by_id = {i.id: i for i in managed}
        node_map, node_error = await self._node_map()

        if not group_id:
            desired = sorted(by_id)
            actionable: list[int] = []
            unavailable: list[str] = []
            for inbound in managed:
                if inbound.node_id is None:
                    actionable.append(inbound.id)
                    continue
                node = node_map.get(int(inbound.node_id))
                if node and node.enable and node.status == "online" and not getattr(node, "transitive", False):
                    actionable.append(inbound.id)
                else:
                    key = f"node_{inbound.node_id}"
                    if key not in unavailable:
                        unavailable.append(key)
            warnings = []
            if node_error:
                warnings.append(f"API нод: {node_error[:180]}")
            if unavailable:
                warnings.append("Недоступные ноды пропущены при безопасном согласовании.")
            return ProvisioningPolicy(
                plan=plan,
                group=None,
                source=source,
                member_keys={"legacy-all-managed"},
                inbound_mode="all_managed",
                desired_inbound_ids=desired,
                actionable_inbound_ids=sorted(actionable),
                managed_inbound_ids=desired,
                unavailable_members=unavailable,
                warnings=warnings,
                inbounds=by_id,
                nodes=node_map,
            )

        group = await self.db.get_server_group(group_id)
        if not group:
            raise ProvisioningError(f"Группа серверов #{group_id} не найдена")
        members = await self.db.list_server_group_members(group_id)
        mode = await self.db.get_server_group_inbound_mode(group_id)
        selected = await self.db.list_server_group_inbounds(group_id)
        member_options = [i for i in managed if inbound_member_key(i) in members]
        if mode == "selected":
            desired_opts = [i for i in member_options if i.id in selected]
        else:
            desired_opts = member_options

        unavailable: list[str] = []
        for key in sorted(members):
            if key == "master":
                continue
            if not key.startswith("node_"):
                unavailable.append(key)
                continue
            try:
                node_id = int(key.split("_", 1)[1])
            except (TypeError, ValueError):
                unavailable.append(key)
                continue
            node = node_map.get(node_id)
            if not node or not node.enable or node.status != "online" or getattr(node, "transitive", False):
                unavailable.append(key)

        actionable = [
            i.id for i in desired_opts
            if i.node_id is None or f"node_{i.node_id}" not in unavailable
        ]
        warnings: list[str] = []
        if not members:
            warnings.append("В группе серверов не выбрано ни одного сервера.")
        if node_error and any(k.startswith("node_") for k in members):
            warnings.append(f"API нод: {node_error[:180]}")
        if mode == "selected" and not selected:
            warnings.append("Режим «выбранные» включён, но Inbounds не выбраны.")
        if members and not desired_opts:
            warnings.append("Для выбранных серверов нет подходящих Inbounds согласования.")
        if unavailable:
            warnings.append("Недоступные ноды будут пропущены до следующего согласования.")

        return ProvisioningPolicy(
            plan=plan,
            group=group,
            source=source,
            member_keys=members,
            inbound_mode=mode,
            selected_inbound_ids=selected,
            desired_inbound_ids=sorted(i.id for i in desired_opts),
            actionable_inbound_ids=sorted(actionable),
            managed_inbound_ids=sorted(by_id),
            unavailable_members=unavailable,
            warnings=warnings,
            inbounds=by_id,
            nodes=node_map,
        )

    async def policy_for_plan(self, plan: PlanRecord) -> ProvisioningPolicy:
        return await self.resolve_group(
            plan.server_group_id,
            plan=plan,
            source=f"plan:{plan.id}",
        )

    async def policy_for_user(self, telegram_id: int) -> ProvisioningPolicy:
        profile = await self.db.get_user_profile(telegram_id)
        plan = await self.db.get_plan(profile.plan_id) if profile and profile.plan_id else None
        group_id = profile.server_group_id if profile and profile.server_group_id else None
        source = "user-profile"
        if group_id is None and plan and plan.server_group_id:
            group_id = plan.server_group_id
            source = f"plan:{plan.id}"
        if group_id is None:
            source = "legacy-all-managed"
        return await self.resolve_group(group_id, plan=plan, source=source)

    async def _mutation_readback(self, email: str, exc: XUIMutationError, *, operation: str) -> dict[str, object]:
        try:
            return await self.xui.get_client(email)
        except XUIError as read_exc:
            raise ProvisioningUnknown(
                f"{operation}: outcome=unknown; mutation_not_retried=true; "
                f"readback=unavailable:{type(read_exc).__name__}"
            ) from exc

    @staticmethod
    def _client_ids(obj: dict[str, object]) -> set[int]:
        return {int(x) for x in (obj.get("inboundIds") or [])}

    @staticmethod
    def _client_payload(obj: dict[str, object]) -> dict[str, object]:
        client = obj.get("client", obj)
        return client if isinstance(client, dict) else {}

    async def sync_user(
        self,
        telegram_id: int,
        *,
        strict: bool = False,
        apply_plan_limits: bool = False,
    ) -> ProvisioningResult:
        rec = await self.db.get(telegram_id)
        if not rec:
            raise ProvisioningError("Пользователь не найден в БД бота")
        profile = await self.db.get_user_profile(telegram_id)
        plan = await self.db.get_plan(profile.plan_id) if profile and profile.plan_id else None
        if apply_plan_limits and plan and plan.server_group_id:
            policy = await self.resolve_group(
                plan.server_group_id, plan=plan, source=f"plan:{plan.id}"
            )
        else:
            policy = await self.policy_for_user(telegram_id)

        obj = await self.xui.get_client(rec.email)
        current = self._client_ids(obj)
        desired = set(policy.desired_inbound_ids)
        actionable = set(policy.actionable_inbound_ids)
        missing = sorted(actionable - current)

        if missing:
            try:
                await self.xui.attach_client(rec.email, missing)
            except XUIMutationError as exc:
                if not exc.uncertain:
                    raise
                readback = await self._mutation_readback(rec.email, exc, operation="attach")
                read_ids = self._client_ids(readback)
                if not set(missing).issubset(read_ids):
                    raise ProvisioningUnknown(
                        "attach: outcome=unknown; mutation_not_retried=true; readback=mismatch"
                    ) from exc
                current = read_ids
            else:
                current.update(missing)

        detached: list[int] = []
        if strict:
            managed_pool = set(policy.managed_inbound_ids)
            detached = sorted((current & managed_pool) - desired)
            if detached:
                after = current - set(detached)
                if not after:
                    raise ProvisioningError("Строгое согласование оставило бы клиента без Inbounds")
                try:
                    await self.xui.detach_client(rec.email, detached)
                except XUIMutationError as exc:
                    if not exc.uncertain:
                        raise
                    readback = await self._mutation_readback(rec.email, exc, operation="detach")
                    read_ids = self._client_ids(readback)
                    if set(detached) & read_ids:
                        raise ProvisioningUnknown(
                            "detach: outcome=unknown; mutation_not_retried=true; readback=mismatch"
                        ) from exc
                    current = read_ids
                else:
                    current.difference_update(detached)

        limits_applied = False
        if apply_plan_limits and policy.plan:
            plan = policy.plan
            expiry = (
                int((time.time() + max(0, plan.duration_days) * 86400) * 1000)
                if plan.duration_days else 0
            )
            expected_limits = {
                "expiryTime": expiry,
                "totalGB": max(0, plan.traffic_gb) * 1024**3,
                "limitIp": max(0, plan.ip_limit),
            }
            try:
                await self.xui.update_client(rec.email, **expected_limits)
            except XUIMutationError as exc:
                if not exc.uncertain:
                    raise
                readback = await self._mutation_readback(rec.email, exc, operation="plan_limits")
                client = self._client_payload(readback)
                if any(int(client.get(key) or 0) != int(value) for key, value in expected_limits.items()):
                    raise ProvisioningUnknown(
                        "plan_limits: outcome=unknown; mutation_not_retried=true; readback=mismatch"
                    ) from exc
            await self.db.update_expiry(telegram_id, expiry)
            if plan.server_group_id:
                await self.db.set_user_server_group(telegram_id, plan.server_group_id)
            limits_applied = True

        if self.settings.vless_flow:
            try:
                await self.xui.bulk_adjust_clients([rec.email], flow=self.settings.vless_flow)
            except XUIMutationError as exc:
                if not exc.uncertain:
                    raise
                readback = await self._mutation_readback(rec.email, exc, operation="flow")
                client = self._client_payload(readback)
                if str(client.get("flow") or "") != self.settings.vless_flow:
                    raise ProvisioningUnknown(
                        "flow: outcome=unknown; mutation_not_retried=true; readback=mismatch"
                    ) from exc

        updated = await self.xui.get_client(rec.email)
        updated_ids = self._client_ids(updated)
        return ProvisioningResult(
            policy=policy,
            current_ids=sorted(updated_ids),
            attached_ids=missing,
            detached_ids=detached,
            remaining_missing_ids=sorted(desired - updated_ids),
            extra_ids=sorted((updated_ids & set(policy.managed_inbound_ids)) - desired),
            limits_applied=limits_applied,
        )

    async def provision_many(self, telegram_ids: list[int], *, strict: bool = False) -> dict[str, object]:
        ok = 0
        failed: dict[int, str] = {}
        unknown: dict[int, str] = {}
        attached = 0
        detached = 0
        for tg_id in telegram_ids:
            try:
                result = await self.sync_user(tg_id, strict=strict, apply_plan_limits=False)
                ok += 1
                attached += len(result.attached_ids)
                detached += len(result.detached_ids)
            except ProvisioningUnknown as exc:
                unknown[int(tg_id)] = str(exc)
            except Exception as exc:  # one broken user must not stop a batch
                failed[int(tg_id)] = f"{type(exc).__name__}: {exc}"
        return {
            "ok": ok,
            "failed": failed,
            "unknown": unknown,
            "attached": attached,
            "detached": detached,
        }

    async def new_user_plan(self) -> tuple[PlanRecord | None, ProvisioningPolicy | None]:
        plan = await self.default_plan()
        if not plan:
            return None, None
        policy = await self.policy_for_plan(plan)
        return plan, policy
