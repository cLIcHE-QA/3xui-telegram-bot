import os
import time
from dataclasses import dataclass
from pathlib import Path

import aiosqlite

from db_migrations import run_migrations


def _prepare_private_database(path: str) -> None:
    if path == ":memory:":
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if str(target.parent) not in {"", "."}:
        os.chmod(target.parent, 0o700)
    fd = os.open(target, os.O_WRONLY | os.O_CREAT, 0o600)
    os.close(fd)
    os.chmod(target, 0o600)


@dataclass
class UserRecord:
    telegram_id: int
    email: str
    sub_id: str
    expiry_time: int
    created_at: int


@dataclass
class PlanRecord:
    id: int
    name: str
    duration_days: int
    traffic_gb: int
    ip_limit: int
    price_minor: int
    currency: str
    server_group_id: int | None
    active: int
    created_at: int
    stars_price: int


@dataclass
class ServerGroupRecord:
    id: int
    name: str
    description: str
    created_at: int


@dataclass
class UserGroupRecord:
    id: int
    name: str
    description: str
    created_at: int
    updated_at: int


@dataclass
class HostRecord:
    id: int
    label: str
    hostname: str
    role: str
    enabled: int
    created_at: int


@dataclass
class AuditRecord:
    id: int
    actor_id: int
    actor_username: str
    action: str
    target_type: str
    target_id: str
    details: str
    success: int
    created_at: int


@dataclass(frozen=True)
class BotUpdateAcknowledgment:
    job_run_id: int
    actor_id: int
    actor_username: str
    reason_code: str
    evidence_code: str
    operation_id: str
    target_release: str
    agent_state: str
    target_sha: str
    current_release: str
    current_sha: str
    postcondition: str
    acknowledged_at: int


@dataclass
class JobRunRecord:
    id: int
    name: str
    trigger: str
    actor_id: int
    status: str
    started_at: int
    finished_at: int
    duration_ms: int
    details: str


@dataclass
class PaymentRecord:
    id: int
    telegram_id: int
    plan_id: int | None
    amount_minor: int
    currency: str
    status: str
    provider: str
    external_id: str
    note: str
    created_by: int
    created_at: int
    updated_at: int
    paid_at: int


@dataclass
class CommerceOrderRecord:
    id: int
    telegram_id: int
    plan_id: int
    promo_code_id: int | None
    amount_minor: int
    currency: str
    status: str
    created_at: int
    updated_at: int
    paid_at: int


@dataclass
class CommercePaymentRecord:
    id: int
    order_id: int
    provider: str
    provider_payment_id: str
    amount_minor: int
    currency: str
    status: str
    created_at: int
    updated_at: int
    confirmed_at: int
    checkout_url: str
    idempotency_key: str


@dataclass
class PaymentWebhookEventRecord:
    id: int
    provider: str
    provider_event_id: str
    event_type: str
    signature_valid: int
    payload_sha256: str
    metadata_json: str
    processing_status: str
    order_id: int | None
    payment_id: int | None
    received_at: int
    applied_at: int
    result_code: str
    provider_payment_id: str


@dataclass
class EntitlementRecord:
    id: int
    telegram_id: int
    order_id: int
    plan_id: int
    status: str
    starts_at: int
    expires_at: int
    created_at: int
    updated_at: int
    quota_reset_status: str


@dataclass
class StarsRefundOperationRecord:
    id: int
    operation_id: str
    payment_id: int
    telegram_id: int
    provider_payment_id: str
    status: str
    requested_by: int
    created_at: int
    updated_at: int
    error: str


@dataclass
class PromoCodeRecord:
    id: int
    code: str
    discount_type: str
    value: int
    currency: str
    plan_id: int | None
    max_uses: int
    uses_count: int
    expires_at: int
    active: int
    created_at: int


@dataclass
class AdministratorRecord:
    telegram_id: int
    role: str
    enabled: int
    added_by: int
    created_at: int
    updated_at: int


@dataclass
class RuntimeSettingRecord:
    key: str
    value: str
    updated_by: int
    updated_at: int


@dataclass
class UserProfileRecord:
    telegram_id: int
    plan_id: int | None
    server_group_id: int | None
    note: str
    updated_at: int
    display_name: str


@dataclass
class InboundTemplateRecord:
    id: int
    name: str
    source_inbound_id: int
    protocol: str
    payload_json: str
    created_at: int
    updated_at: int


@dataclass
class AlertRuleRecord:
    code: str
    enabled: int
    threshold: int
    cooldown_sec: int
    updated_at: int


@dataclass
class AlertStateRecord:
    code: str
    target: str
    active: int
    last_value: str
    first_seen: int
    last_seen: int
    last_notified: int


class Database:
    def __init__(self, path: str, migration_backup_dir: str | None = None):
        self.path = path
        if migration_backup_dir is not None:
            self.migration_backup_dir = migration_backup_dir
        elif path == ":memory:":
            self.migration_backup_dir = None
        else:
            self.migration_backup_dir = str(Path(path).parent / "migration-backups")

    async def init(self):
        _prepare_private_database(self.path)
        await run_migrations(
            self.path,
            backup_dir=self.migration_backup_dir,
        )
        if self.path != ":memory:":
            os.chmod(self.path, 0o600)
    async def get(self, telegram_id: int) -> UserRecord | None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
            row = await cur.fetchone()
            return UserRecord(**dict(row)) if row else None

    async def get_by_email(self, email: str) -> UserRecord | None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM users WHERE email = ?", (email,))
            row = await cur.fetchone()
            return UserRecord(**dict(row)) if row else None

    async def get_by_sub_id(self, sub_id: str) -> UserRecord | None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM users WHERE sub_id = ?", (sub_id,))
            row = await cur.fetchone()
            return UserRecord(**dict(row)) if row else None

    async def list_users(self) -> list[UserRecord]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM users ORDER BY created_at DESC")
            rows = await cur.fetchall()
            return [UserRecord(**dict(r)) for r in rows]

    async def search_users(self, query: str, *, limit: int = 20) -> list[UserRecord]:
        text = str(query or "").strip()
        if not text:
            return []
        limit = max(1, min(50, int(limit)))
        escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT u.*
                FROM users AS u
                LEFT JOIN user_profiles AS p ON p.telegram_id = u.telegram_id
                WHERE CAST(u.telegram_id AS TEXT) = ?
                   OR u.email LIKE ? ESCAPE '\\' COLLATE NOCASE
                   OR COALESCE(p.display_name, '') LIKE ? ESCAPE '\\' COLLATE NOCASE
                ORDER BY
                    CASE WHEN CAST(u.telegram_id AS TEXT) = ? THEN 0 ELSE 1 END,
                    COALESCE(NULLIF(p.display_name, ''), u.email) COLLATE NOCASE,
                    u.telegram_id
                LIMIT ?
                """,
                (text, pattern, pattern, text, limit),
            )
            rows = await cur.fetchall()
            return [UserRecord(**dict(r)) for r in rows]

    async def put(self, rec: UserRecord):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("""
                INSERT INTO users(telegram_id, email, sub_id, expiry_time, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(telegram_id) DO UPDATE SET
                    email=excluded.email,
                    sub_id=excluded.sub_id,
                    expiry_time=excluded.expiry_time,
                    created_at=excluded.created_at
            """, (rec.telegram_id, rec.email, rec.sub_id, rec.expiry_time, rec.created_at))
            await db.commit()

    async def update_expiry(self, telegram_id: int, expiry_time: int):
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "UPDATE users SET expiry_time = ? WHERE telegram_id = ?",
                (expiry_time, telegram_id)
            )
            await db.commit()

    async def update_sub_id(self, telegram_id: int, sub_id: str):
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "UPDATE users SET sub_id = ? WHERE telegram_id = ?",
                (str(sub_id), int(telegram_id)),
            )
            await db.commit()

    async def get_user_profile(self, telegram_id: int) -> UserProfileRecord | None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM user_profiles WHERE telegram_id = ?",
                (int(telegram_id),),
            )
            row = await cur.fetchone()
            return UserProfileRecord(**dict(row)) if row else None

    async def upsert_user_profile(
        self,
        telegram_id: int,
        *,
        plan_id: int | None = None,
        server_group_id: int | None = None,
        note: str | None = None,
        display_name: str | None = None,
        preserve_unspecified: bool = True,
    ) -> None:
        current = await self.get_user_profile(int(telegram_id)) if preserve_unspecified else None
        plan_value = current.plan_id if current and plan_id is None else plan_id
        group_value = current.server_group_id if current and server_group_id is None else server_group_id
        note_value = current.note if current and note is None else (note or "")
        display_name_value = (
            getattr(current, "display_name", "") if current and display_name is None else (display_name or "")
        )
        now = int(time.time())
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                INSERT INTO user_profiles(
                    telegram_id, plan_id, server_group_id, note, updated_at, display_name
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(telegram_id) DO UPDATE SET
                    plan_id=excluded.plan_id,
                    server_group_id=excluded.server_group_id,
                    note=excluded.note,
                    updated_at=excluded.updated_at,
                    display_name=excluded.display_name
                """,
                (
                    int(telegram_id), plan_value, group_value, note_value[:1000], now,
                    display_name_value[:64],
                ),
            )
            await db.commit()

    async def set_user_plan(self, telegram_id: int, plan_id: int | None) -> None:
        current = await self.get_user_profile(int(telegram_id))
        await self.upsert_user_profile(
            int(telegram_id),
            plan_id=plan_id,
            server_group_id=current.server_group_id if current else None,
            note=current.note if current else "",
            display_name=getattr(current, "display_name", "") if current else "",
            preserve_unspecified=False,
        )

    async def set_user_server_group(self, telegram_id: int, group_id: int | None) -> None:
        current = await self.get_user_profile(int(telegram_id))
        await self.upsert_user_profile(
            int(telegram_id),
            plan_id=current.plan_id if current else None,
            server_group_id=group_id,
            note=current.note if current else "",
            display_name=getattr(current, "display_name", "") if current else "",
            preserve_unspecified=False,
        )

    async def set_user_note(self, telegram_id: int, note: str) -> None:
        current = await self.get_user_profile(int(telegram_id))
        await self.upsert_user_profile(
            int(telegram_id),
            plan_id=current.plan_id if current else None,
            server_group_id=current.server_group_id if current else None,
            note=note,
            display_name=getattr(current, "display_name", "") if current else "",
            preserve_unspecified=False,
        )

    async def set_user_display_name(self, telegram_id: int, display_name: str) -> None:
        current = await self.get_user_profile(int(telegram_id))
        await self.upsert_user_profile(
            int(telegram_id),
            plan_id=current.plan_id if current else None,
            server_group_id=current.server_group_id if current else None,
            note=current.note if current else "",
            display_name=display_name,
            preserve_unspecified=False,
        )

    async def delete(self, telegram_id: int):
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "DELETE FROM user_group_members WHERE telegram_id = ?",
                (int(telegram_id),),
            )
            await db.execute("DELETE FROM user_profiles WHERE telegram_id = ?", (telegram_id,))
            await db.execute("DELETE FROM users WHERE telegram_id = ?", (telegram_id,))
            await db.commit()

    # --- Plans ---------------------------------------------------------

    async def list_plans(self) -> list[PlanRecord]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM plans ORDER BY active DESC, name COLLATE NOCASE")
            rows = await cur.fetchall()
            return [PlanRecord(**dict(r)) for r in rows]

    async def get_plan(self, plan_id: int) -> PlanRecord | None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM plans WHERE id = ?", (int(plan_id),))
            row = await cur.fetchone()
            return PlanRecord(**dict(row)) if row else None

    async def create_plan(
        self,
        *,
        name: str,
        duration_days: int,
        traffic_gb: int,
        ip_limit: int,
        price_minor: int,
        currency: str,
        server_group_id: int | None = None,
        stars_price: int = 0,
    ) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                """
                INSERT INTO plans(
                    name, duration_days, traffic_gb, ip_limit,
                    price_minor, currency, server_group_id, active, created_at,
                    stars_price
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    name.strip(), int(duration_days), int(traffic_gb), int(ip_limit),
                    int(price_minor), currency.strip().upper(), server_group_id,
                    int(time.time()), max(0, int(stars_price)),
                ),
            )
            await db.commit()
            return int(cur.lastrowid)

    async def set_plan_stars_price(self, plan_id: int, stars_price: int) -> None:
        value = max(0, int(stars_price))
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "UPDATE plans SET stars_price = ? WHERE id = ?",
                (value, int(plan_id)),
            )
            await db.commit()

    async def set_plan_active(self, plan_id: int, active: bool):
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "UPDATE plans SET active = ? WHERE id = ?",
                (1 if active else 0, int(plan_id)),
            )
            await db.commit()

    async def set_plan_group(self, plan_id: int, group_id: int | None):
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "UPDATE plans SET server_group_id = ? WHERE id = ?",
                (group_id, int(plan_id)),
            )
            await db.commit()

    async def delete_plan(self, plan_id: int):
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "UPDATE user_profiles SET plan_id = NULL, updated_at = ? WHERE plan_id = ?",
                (int(time.time()), int(plan_id)),
            )
            await db.execute("DELETE FROM plans WHERE id = ?", (int(plan_id),))
            await db.commit()

    # --- Server groups -------------------------------------------------

    async def list_server_groups(self) -> list[ServerGroupRecord]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM server_groups ORDER BY name COLLATE NOCASE")
            rows = await cur.fetchall()
            return [ServerGroupRecord(**dict(r)) for r in rows]

    async def get_server_group(self, group_id: int) -> ServerGroupRecord | None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM server_groups WHERE id = ?", (int(group_id),))
            row = await cur.fetchone()
            return ServerGroupRecord(**dict(row)) if row else None

    async def create_server_group(self, *, name: str, description: str = "") -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "INSERT INTO server_groups(name, description, created_at) VALUES (?, ?, ?)",
                (name.strip(), description.strip(), int(time.time())),
            )
            await db.commit()
            return int(cur.lastrowid)

    async def delete_server_group(self, group_id: int):
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "UPDATE plans SET server_group_id = NULL WHERE server_group_id = ?",
                (int(group_id),),
            )
            await db.execute(
                "UPDATE user_profiles SET server_group_id = NULL, updated_at = ? WHERE server_group_id = ?",
                (int(time.time()), int(group_id)),
            )
            await db.execute(
                "DELETE FROM server_group_members WHERE group_id = ?",
                (int(group_id),),
            )
            await db.execute(
                "DELETE FROM server_group_inbounds WHERE group_id = ?",
                (int(group_id),),
            )
            await db.execute(
                "DELETE FROM server_group_provisioning WHERE group_id = ?",
                (int(group_id),),
            )
            await db.execute("DELETE FROM server_groups WHERE id = ?", (int(group_id),))
            await db.commit()

    async def list_server_group_members(self, group_id: int) -> set[str]:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "SELECT member_key FROM server_group_members WHERE group_id = ?",
                (int(group_id),),
            )
            rows = await cur.fetchall()
            return {str(r[0]) for r in rows}

    async def set_server_group_member(self, group_id: int, member_key: str, enabled: bool):
        async with aiosqlite.connect(self.path) as db:
            if enabled:
                await db.execute(
                    "INSERT OR IGNORE INTO server_group_members(group_id, member_key) VALUES (?, ?)",
                    (int(group_id), member_key),
                )
            else:
                await db.execute(
                    "DELETE FROM server_group_members WHERE group_id = ? AND member_key = ?",
                    (int(group_id), member_key),
                )
            await db.commit()

    async def get_server_group_inbound_mode(self, group_id: int) -> str:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "SELECT inbound_mode FROM server_group_provisioning WHERE group_id = ?",
                (int(group_id),),
            )
            row = await cur.fetchone()
            mode = str(row[0]) if row else "all_managed"
            return mode if mode in {"all_managed", "selected"} else "all_managed"

    async def set_server_group_inbound_mode(self, group_id: int, mode: str) -> None:
        if mode not in {"all_managed", "selected"}:
            raise ValueError("invalid inbound mode")
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                INSERT INTO server_group_provisioning(group_id, inbound_mode, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(group_id) DO UPDATE SET
                    inbound_mode=excluded.inbound_mode,
                    updated_at=excluded.updated_at
                """,
                (int(group_id), mode, int(time.time())),
            )
            await db.commit()

    async def list_server_group_inbounds(self, group_id: int) -> set[int]:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "SELECT inbound_id FROM server_group_inbounds WHERE group_id = ?",
                (int(group_id),),
            )
            rows = await cur.fetchall()
            return {int(r[0]) for r in rows}

    async def set_server_group_inbound(self, group_id: int, inbound_id: int, enabled: bool) -> None:
        async with aiosqlite.connect(self.path) as db:
            if enabled:
                await db.execute(
                    "INSERT OR IGNORE INTO server_group_inbounds(group_id, inbound_id) VALUES (?, ?)",
                    (int(group_id), int(inbound_id)),
                )
            else:
                await db.execute(
                    "DELETE FROM server_group_inbounds WHERE group_id = ? AND inbound_id = ?",
                    (int(group_id), int(inbound_id)),
                )
            await db.commit()

    async def replace_server_group_inbounds(self, group_id: int, inbound_ids: set[int] | list[int]) -> None:
        ids = sorted({int(x) for x in inbound_ids})
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "DELETE FROM server_group_inbounds WHERE group_id = ?",
                (int(group_id),),
            )
            if ids:
                await db.executemany(
                    "INSERT INTO server_group_inbounds(group_id, inbound_id) VALUES (?, ?)",
                    [(int(group_id), inbound_id) for inbound_id in ids],
                )
            await db.commit()

    # --- User / audience groups ----------------------------------------

    async def list_user_groups(self) -> list[UserGroupRecord]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM user_groups ORDER BY name COLLATE NOCASE, id"
            )
            rows = await cur.fetchall()
            return [UserGroupRecord(**dict(r)) for r in rows]

    async def get_user_group(self, group_id: int) -> UserGroupRecord | None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM user_groups WHERE id = ?",
                (int(group_id),),
            )
            row = await cur.fetchone()
            return UserGroupRecord(**dict(row)) if row else None

    async def create_user_group(self, *, name: str, description: str = "") -> int:
        now = int(time.time())
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                """
                INSERT INTO user_groups(name, description, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (name.strip(), description.strip(), now, now),
            )
            await db.commit()
            return int(cur.lastrowid)

    async def update_user_group(
        self,
        group_id: int,
        *,
        name: str,
        description: str,
    ) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                UPDATE user_groups
                SET name = ?, description = ?, updated_at = ?
                WHERE id = ?
                """,
                (name.strip(), description.strip(), int(time.time()), int(group_id)),
            )
            await db.commit()

    async def delete_user_group(self, group_id: int) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "DELETE FROM user_group_members WHERE group_id = ?",
                (int(group_id),),
            )
            await db.execute(
                "DELETE FROM user_groups WHERE id = ?",
                (int(group_id),),
            )
            await db.commit()

    async def count_user_group_members(self, group_id: int) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "SELECT COUNT(*) FROM user_group_members WHERE group_id = ?",
                (int(group_id),),
            )
            row = await cur.fetchone()
            return int(row[0] if row else 0)

    async def list_user_group_member_ids(self, group_id: int) -> set[int]:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "SELECT telegram_id FROM user_group_members WHERE group_id = ?",
                (int(group_id),),
            )
            rows = await cur.fetchall()
            return {int(row[0]) for row in rows}

    async def list_user_group_members(
        self,
        group_id: int,
        *,
        limit: int = 30,
        offset: int = 0,
    ) -> list[UserRecord]:
        limit = max(1, min(100, int(limit)))
        offset = max(0, int(offset))
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT u.*
                FROM user_group_members AS m
                JOIN users AS u ON u.telegram_id = m.telegram_id
                LEFT JOIN user_profiles AS p ON p.telegram_id = u.telegram_id
                WHERE m.group_id = ?
                ORDER BY COALESCE(NULLIF(p.display_name, ''), u.email) COLLATE NOCASE,
                         u.telegram_id
                LIMIT ? OFFSET ?
                """,
                (int(group_id), limit, offset),
            )
            rows = await cur.fetchall()
            return [UserRecord(**dict(r)) for r in rows]

    async def list_user_groups_for_user(self, telegram_id: int) -> list[UserGroupRecord]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT g.*
                FROM user_group_members AS m
                JOIN user_groups AS g ON g.id = m.group_id
                WHERE m.telegram_id = ?
                ORDER BY g.name COLLATE NOCASE, g.id
                """,
                (int(telegram_id),),
            )
            rows = await cur.fetchall()
            return [UserGroupRecord(**dict(r)) for r in rows]

    async def list_user_group_ids_for_user(self, telegram_id: int) -> set[int]:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "SELECT group_id FROM user_group_members WHERE telegram_id = ?",
                (int(telegram_id),),
            )
            rows = await cur.fetchall()
            return {int(row[0]) for row in rows}

    async def set_user_group_member(
        self,
        group_id: int,
        telegram_id: int,
        enabled: bool,
    ) -> bool:
        group_id = int(group_id)
        telegram_id = int(telegram_id)
        async with aiosqlite.connect(self.path) as db:
            group = await (
                await db.execute("SELECT 1 FROM user_groups WHERE id = ?", (group_id,))
            ).fetchone()
            user = await (
                await db.execute("SELECT 1 FROM users WHERE telegram_id = ?", (telegram_id,))
            ).fetchone()
            if not group:
                raise ValueError("user group not found")
            if not user:
                raise ValueError("user not found")
            if enabled:
                cur = await db.execute(
                    """
                    INSERT OR IGNORE INTO user_group_members(group_id, telegram_id, created_at)
                    VALUES (?, ?, ?)
                    """,
                    (group_id, telegram_id, int(time.time())),
                )
            else:
                cur = await db.execute(
                    """
                    DELETE FROM user_group_members
                    WHERE group_id = ? AND telegram_id = ?
                    """,
                    (group_id, telegram_id),
                )
            await db.commit()
            return bool(cur.rowcount)

    # --- Hosts ---------------------------------------------------------

    async def list_hosts(self) -> list[HostRecord]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM hosts ORDER BY enabled DESC, role COLLATE NOCASE, hostname COLLATE NOCASE"
            )
            rows = await cur.fetchall()
            return [HostRecord(**dict(r)) for r in rows]

    async def get_host(self, host_id: int) -> HostRecord | None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM hosts WHERE id = ?", (int(host_id),))
            row = await cur.fetchone()
            return HostRecord(**dict(row)) if row else None

    async def create_host(self, *, label: str, hostname: str, role: str) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                """
                INSERT INTO hosts(label, hostname, role, enabled, created_at)
                VALUES (?, ?, ?, 1, ?)
                """,
                (label.strip(), hostname.strip().lower(), role.strip().lower(), int(time.time())),
            )
            await db.commit()
            return int(cur.lastrowid)

    async def upsert_host(self, *, label: str, hostname: str, role: str) -> int:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                INSERT INTO hosts(label, hostname, role, enabled, created_at)
                VALUES (?, ?, ?, 1, ?)
                ON CONFLICT(hostname, role) DO UPDATE SET
                    enabled=1
                """,
                (label.strip(), hostname.strip().lower(), role.strip().lower(), int(time.time())),
            )
            cur = await db.execute(
                "SELECT id FROM hosts WHERE hostname = ? AND role = ?",
                (hostname.strip().lower(), role.strip().lower()),
            )
            row = await cur.fetchone()
            await db.commit()
            return int(row[0])

    async def set_host_enabled(self, host_id: int, enabled: bool):
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "UPDATE hosts SET enabled = ? WHERE id = ?",
                (1 if enabled else 0, int(host_id)),
            )
            await db.commit()

    async def delete_host(self, host_id: int):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("DELETE FROM hosts WHERE id = ?", (int(host_id),))
            await db.commit()

    # --- Payments ------------------------------------------------------

    async def list_payments(self, *, limit: int = 50, offset: int = 0) -> list[PaymentRecord]:
        limit = max(1, min(200, int(limit)))
        offset = max(0, int(offset))
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM payments ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
            rows = await cur.fetchall()
            return [PaymentRecord(**dict(r)) for r in rows]

    async def count_payments(self) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT COUNT(*) FROM payments")
            row = await cur.fetchone()
            return int(row[0] if row else 0)

    async def list_user_payments(
        self, telegram_id: int, *, limit: int = 20, offset: int = 0
    ) -> list[PaymentRecord]:
        limit = max(1, min(100, int(limit)))
        offset = max(0, int(offset))
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT * FROM payments
                WHERE telegram_id = ?
                ORDER BY id DESC
                LIMIT ? OFFSET ?
                """,
                (int(telegram_id), limit, offset),
            )
            rows = await cur.fetchall()
            return [PaymentRecord(**dict(r)) for r in rows]

    async def count_user_payments(self, telegram_id: int) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "SELECT COUNT(*) FROM payments WHERE telegram_id = ?",
                (int(telegram_id),),
            )
            row = await cur.fetchone()
            return int(row[0] if row else 0)

    async def count_user_payments_by_status(self, telegram_id: int, status: str) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "SELECT COUNT(*) FROM payments WHERE telegram_id = ? AND status = ?",
                (int(telegram_id), str(status)),
            )
            row = await cur.fetchone()
            return int(row[0] if row else 0)

    async def get_user_payment(self, telegram_id: int, payment_id: int) -> PaymentRecord | None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM payments WHERE id = ? AND telegram_id = ?",
                (int(payment_id), int(telegram_id)),
            )
            row = await cur.fetchone()
            return PaymentRecord(**dict(row)) if row else None

    async def paid_user_totals_by_currency(self, telegram_id: int) -> dict[str, int]:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                """
                SELECT currency, COALESCE(SUM(amount_minor), 0)
                FROM payments
                WHERE telegram_id = ? AND status = 'paid'
                GROUP BY currency
                """,
                (int(telegram_id),),
            )
            return {str(currency): int(total) for currency, total in await cur.fetchall()}

    async def get_payment(self, payment_id: int) -> PaymentRecord | None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM payments WHERE id = ?", (int(payment_id),))
            row = await cur.fetchone()
            return PaymentRecord(**dict(row)) if row else None

    async def create_payment(
        self, *, telegram_id: int, plan_id: int | None, amount_minor: int,
        currency: str, status: str, provider: str = "manual", external_id: str = "",
        note: str = "", created_by: int = 0,
    ) -> int:
        now = int(time.time())
        paid_at = now if status == "paid" else 0
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                """
                INSERT INTO payments(
                    telegram_id, plan_id, amount_minor, currency, status, provider,
                    external_id, note, created_by, created_at, updated_at, paid_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(telegram_id), plan_id, int(amount_minor), currency.upper(), status,
                    provider[:32], external_id[:160], note[:1000], int(created_by), now, now, paid_at,
                ),
            )
            await db.commit()
            return int(cur.lastrowid)

    async def set_payment_status(self, payment_id: int, status: str) -> None:
        now = int(time.time())
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                UPDATE payments
                SET status = ?, updated_at = ?,
                    paid_at = CASE WHEN ? = 'paid' AND paid_at = 0 THEN ? ELSE paid_at END
                WHERE id = ?
                """,
                (status, now, status, now, int(payment_id)),
            )
            await db.commit()

    async def payment_summary(self) -> dict[str, int]:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "SELECT status, COUNT(*) FROM payments GROUP BY status"
            )
            counts = {str(k): int(v) for k, v in await cur.fetchall()}
            cur = await db.execute(
                "SELECT COUNT(*) FROM payments WHERE status = 'paid'"
            )
            row = await cur.fetchone()
            counts['paid_total'] = int(row[0] if row else 0)
            return counts

    async def paid_totals_by_currency(self) -> dict[str, int]:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "SELECT currency, COALESCE(SUM(amount_minor), 0) FROM payments WHERE status = 'paid' GROUP BY currency"
            )
            return {str(currency): int(total) for currency, total in await cur.fetchall()}

    async def stars_payment_summary(self) -> dict[str, int]:
        """Read-only Stars counts and amounts; never mix XTR with fiat."""
        async with aiosqlite.connect(self.path) as conn:
            cur = await conn.execute(
                """
                SELECT status, COUNT(*), COALESCE(SUM(amount_minor), 0)
                FROM commerce_payments
                WHERE provider = 'telegram_stars' AND currency = 'XTR'
                GROUP BY status
                """
            )
            summary = {"total": 0, "confirmed_amount": 0, "refunded_amount": 0}
            for status, count, amount in await cur.fetchall():
                summary["total"] += int(count)
                summary[str(status)] = int(count)
                if status in {"confirmed", "refunded"}:
                    summary[f"{status}_amount"] = int(amount)
            return summary

    # --- Client Portal commerce ---------------------------------------

    async def create_commerce_order(
        self, *, telegram_id: int, plan_id: int, amount_minor: int,
        currency: str, promo_code_id: int | None = None,
    ) -> int:
        now = int(time.time())
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                """
                INSERT INTO commerce_orders(
                    telegram_id, plan_id, promo_code_id, amount_minor, currency,
                    status, created_at, updated_at, paid_at
                ) VALUES (?, ?, ?, ?, ?, 'created', ?, ?, 0)
                """,
                (
                    int(telegram_id), int(plan_id), promo_code_id,
                    max(0, int(amount_minor)), str(currency).upper(), now, now,
                ),
            )
            await db.commit()
            return int(cur.lastrowid)

    async def find_open_commerce_order(
        self, *, telegram_id: int, plan_id: int,
    ) -> CommerceOrderRecord | None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT * FROM commerce_orders
                WHERE telegram_id = ? AND plan_id = ?
                  AND status IN ('created', 'awaiting_payment')
                ORDER BY id DESC
                LIMIT 1
                """,
                (int(telegram_id), int(plan_id)),
            )
            row = await cur.fetchone()
            return CommerceOrderRecord(**dict(row)) if row else None

    async def create_or_get_open_commerce_order(
        self, *, telegram_id: int, plan_id: int, amount_minor: int,
        currency: str, promo_code_id: int | None = None,
    ) -> tuple[CommerceOrderRecord, bool]:
        now = int(time.time())
        amount_value = max(0, int(amount_minor))
        currency_value = str(currency).upper()
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            await db.execute("BEGIN IMMEDIATE")
            try:
                cur = await db.execute(
                    """
                    SELECT * FROM commerce_orders
                    WHERE telegram_id = ? AND plan_id = ?
                      AND amount_minor = ? AND currency = ?
                      AND promo_code_id IS ?
                      AND status IN ('created', 'awaiting_payment')
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (
                        int(telegram_id), int(plan_id), amount_value,
                        currency_value, promo_code_id,
                    ),
                )
                row = await cur.fetchone()
                if row is not None:
                    await db.commit()
                    return CommerceOrderRecord(**dict(row)), False

                cur = await db.execute(
                    """
                    INSERT INTO commerce_orders(
                        telegram_id, plan_id, promo_code_id, amount_minor, currency,
                        status, created_at, updated_at, paid_at
                    ) VALUES (?, ?, ?, ?, ?, 'created', ?, ?, 0)
                    """,
                    (
                        int(telegram_id), int(plan_id), promo_code_id,
                        amount_value, currency_value, now, now,
                    ),
                )
                order_id = int(cur.lastrowid)
                cur = await db.execute(
                    "SELECT * FROM commerce_orders WHERE id = ?",
                    (order_id,),
                )
                row = await cur.fetchone()
                await db.commit()
                return CommerceOrderRecord(**dict(row)), True
            except Exception:
                await db.rollback()
                raise

    async def mark_commerce_order_awaiting_payment(
        self, order_id: int,
    ) -> CommerceOrderRecord:
        now = int(time.time())
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            await db.execute("BEGIN IMMEDIATE")
            try:
                cur = await db.execute(
                    "SELECT * FROM commerce_orders WHERE id = ?",
                    (int(order_id),),
                )
                row = await cur.fetchone()
                if row is None:
                    raise RuntimeError("Order does not exist.")
                status = str(row["status"])
                if status == "created":
                    await db.execute(
                        """
                        UPDATE commerce_orders
                        SET status = 'awaiting_payment', updated_at = ?
                        WHERE id = ?
                        """,
                        (now, int(order_id)),
                    )
                elif status != "awaiting_payment":
                    raise RuntimeError(
                        f"Order status {status!r} cannot enter awaiting_payment."
                    )
                cur = await db.execute(
                    "SELECT * FROM commerce_orders WHERE id = ?",
                    (int(order_id),),
                )
                row = await cur.fetchone()
                await db.commit()
                return CommerceOrderRecord(**dict(row))
            except Exception:
                await db.rollback()
                raise

    async def get_commerce_order(self, order_id: int) -> CommerceOrderRecord | None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM commerce_orders WHERE id = ?",
                (int(order_id),),
            )
            row = await cur.fetchone()
            return CommerceOrderRecord(**dict(row)) if row else None

    async def create_commerce_payment(
        self, *, order_id: int, provider: str, provider_payment_id: str,
        amount_minor: int, currency: str, checkout_url: str = "",
        idempotency_key: str = "",
    ) -> int:
        now = int(time.time())
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            await db.execute("BEGIN IMMEDIATE")
            try:
                cur = await db.execute(
                    "SELECT * FROM commerce_orders WHERE id = ?",
                    (int(order_id),),
                )
                order = await cur.fetchone()
                if order is None:
                    raise RuntimeError("Order does not exist.")
                if str(order["status"]) not in {"created", "awaiting_payment"}:
                    raise RuntimeError(
                        f"Order status {order['status']!r} cannot accept a new payment."
                    )
                cur = await db.execute(
                    """
                    INSERT INTO commerce_payments(
                        order_id, provider, provider_payment_id, amount_minor, currency,
                        status, created_at, updated_at, confirmed_at, checkout_url,
                        idempotency_key
                    ) VALUES (?, ?, ?, ?, ?, 'created', ?, ?, 0, ?, ?)
                    """,
                    (
                        int(order_id), str(provider)[:32], str(provider_payment_id)[:160],
                        max(0, int(amount_minor)), str(currency).upper(), now, now,
                        str(checkout_url)[:2000], str(idempotency_key)[:160],
                    ),
                )
                if str(order["status"]) == "created":
                    await db.execute(
                        """
                        UPDATE commerce_orders
                        SET status = 'awaiting_payment', updated_at = ?
                        WHERE id = ?
                        """,
                        (now, int(order_id)),
                    )
                await db.commit()
                return int(cur.lastrowid)
            except Exception:
                await db.rollback()
                raise

    async def get_commerce_payment_by_idempotency(
        self, *, provider: str, idempotency_key: str,
    ) -> CommercePaymentRecord | None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT * FROM commerce_payments
                WHERE provider = ? AND idempotency_key = ?
                """,
                (str(provider)[:32], str(idempotency_key)[:160]),
            )
            row = await cur.fetchone()
            return CommercePaymentRecord(**dict(row)) if row else None

    async def create_or_get_checkout_payment(
        self, *, order_id: int, provider: str, provider_payment_id: str,
        amount_minor: int, currency: str, checkout_url: str,
        idempotency_key: str,
    ) -> tuple[CommercePaymentRecord, bool]:
        provider = str(provider)[:32]
        provider_payment_id = str(provider_payment_id)[:160]
        idempotency_key = str(idempotency_key)[:160]
        checkout_url = str(checkout_url)[:2000]
        currency = str(currency).upper()
        if not idempotency_key:
            raise ValueError("checkout idempotency_key must not be empty")
        now = int(time.time())
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            await db.execute("BEGIN IMMEDIATE")
            try:
                cur = await db.execute(
                    """
                    SELECT * FROM commerce_payments
                    WHERE provider = ? AND idempotency_key = ?
                    """,
                    (provider, idempotency_key),
                )
                existing = await cur.fetchone()
                if existing is not None:
                    if (
                        int(existing["order_id"]) != int(order_id)
                        or int(existing["amount_minor"]) != max(0, int(amount_minor))
                        or str(existing["currency"]).upper() != currency
                    ):
                        raise RuntimeError(
                            "Checkout idempotency key is already bound to different payment data."
                        )
                    await db.commit()
                    return CommercePaymentRecord(**dict(existing)), False

                cur = await db.execute(
                    "SELECT * FROM commerce_orders WHERE id = ?",
                    (int(order_id),),
                )
                order = await cur.fetchone()
                if order is None:
                    raise RuntimeError("Order does not exist.")
                if str(order["status"]) not in {"created", "awaiting_payment"}:
                    raise RuntimeError(
                        f"Order status {order['status']!r} cannot accept a checkout payment."
                    )
                cur = await db.execute(
                    """
                    INSERT INTO commerce_payments(
                        order_id, provider, provider_payment_id, amount_minor, currency,
                        status, created_at, updated_at, confirmed_at, checkout_url,
                        idempotency_key
                    ) VALUES (?, ?, ?, ?, ?, 'created', ?, ?, 0, ?, ?)
                    """,
                    (
                        int(order_id), provider, provider_payment_id,
                        max(0, int(amount_minor)), currency, now, now,
                        checkout_url, idempotency_key,
                    ),
                )
                payment_id = int(cur.lastrowid)
                if str(order["status"]) == "created":
                    await db.execute(
                        """
                        UPDATE commerce_orders
                        SET status = 'awaiting_payment', updated_at = ?
                        WHERE id = ?
                        """,
                        (now, int(order_id)),
                    )
                cur = await db.execute(
                    "SELECT * FROM commerce_payments WHERE id = ?",
                    (payment_id,),
                )
                row = await cur.fetchone()
                await db.commit()
                return CommercePaymentRecord(**dict(row)), True
            except Exception:
                await db.rollback()
                raise

    async def get_commerce_payment(
        self, payment_id: int,
    ) -> CommercePaymentRecord | None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM commerce_payments WHERE id = ?",
                (int(payment_id),),
            )
            row = await cur.fetchone()
            return CommercePaymentRecord(**dict(row)) if row else None

    async def confirm_telegram_stars_payment(
        self, *, order_id: int, telegram_id: int, charge_id: str,
        amount: int, payload_sha256: str,
    ) -> tuple[CommercePaymentRecord, CommerceOrderRecord, EntitlementRecord, bool]:
        now = int(time.time())
        provider = "telegram_stars"
        charge = str(charge_id)[:160]
        digest = str(payload_sha256)[:64]
        if not charge:
            raise RuntimeError("Telegram Stars charge id must not be empty.")

        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            await db.execute("BEGIN IMMEDIATE")
            try:
                cur = await db.execute(
                    "SELECT * FROM commerce_orders WHERE id = ?",
                    (int(order_id),),
                )
                order = await cur.fetchone()
                if order is None:
                    raise RuntimeError("Stars order does not exist.")
                if int(order["telegram_id"]) != int(telegram_id):
                    raise RuntimeError("Stars order ownership mismatch.")
                if str(order["currency"]) != "XTR" or int(order["amount_minor"]) != int(amount):
                    raise RuntimeError("Stars payment amount/currency does not match order.")
                if str(order["status"]) not in {"created", "awaiting_payment", "paid"}:
                    raise RuntimeError(
                        f"Order status {order['status']!r} cannot accept Stars payment."
                    )

                cur = await db.execute(
                    """
                    SELECT * FROM commerce_payments
                    WHERE provider = ? AND provider_payment_id = ?
                    """,
                    (provider, charge),
                )
                payment = await cur.fetchone()
                created = payment is None
                if payment is None:
                    cur = await db.execute(
                        """
                        INSERT INTO commerce_payments(
                            order_id, provider, provider_payment_id, amount_minor, currency,
                            status, created_at, updated_at, confirmed_at, checkout_url,
                            idempotency_key
                        ) VALUES (?, ?, ?, ?, 'XTR', 'confirmed', ?, ?, ?, '', ?)
                        """,
                        (
                            int(order_id), provider, charge, int(amount),
                            now, now, now, f"stars:{charge}"[:160],
                        ),
                    )
                    payment_id = int(cur.lastrowid)
                else:
                    if (
                        int(payment["order_id"]) != int(order_id)
                        or int(payment["amount_minor"]) != int(amount)
                        or str(payment["currency"]) != "XTR"
                    ):
                        raise RuntimeError(
                            "Telegram Stars charge id is already bound to different payment data."
                        )
                    payment_id = int(payment["id"])
                    # A refunded charge is terminal: delayed duplicate confirmation
                    # must not resurrect its payment or refund accounting.
                    if str(payment["status"]) not in {"confirmed", "refunded"}:
                        await db.execute(
                            """
                            UPDATE commerce_payments
                            SET status = 'confirmed', updated_at = ?,
                                confirmed_at = CASE WHEN confirmed_at = 0 THEN ? ELSE confirmed_at END
                            WHERE id = ?
                            """,
                            (now, now, payment_id),
                        )

                await db.execute(
                    """
                    INSERT OR IGNORE INTO payment_webhook_events(
                        provider, provider_event_id, event_type, signature_valid,
                        payload_sha256, metadata_json, processing_status,
                        order_id, payment_id, received_at, applied_at, result_code,
                        provider_payment_id
                    ) VALUES (
                        ?, ?, 'payment.confirmed', 1, ?, '{}', 'applied',
                        ?, ?, ?, ?, 'confirmed', ?
                    )
                    """,
                    (
                        provider, charge, digest, int(order_id), payment_id,
                        now, now, charge,
                    ),
                )

                if str(order["status"]) != "paid":
                    await db.execute(
                        """
                        UPDATE commerce_orders
                        SET status = 'paid', updated_at = ?,
                            paid_at = CASE WHEN paid_at = 0 THEN ? ELSE paid_at END
                        WHERE id = ?
                        """,
                        (now, now, int(order_id)),
                    )

                await db.execute(
                    """
                    INSERT OR IGNORE INTO entitlements(
                        telegram_id, order_id, plan_id, status, starts_at,
                        expires_at, created_at, updated_at
                    ) VALUES (?, ?, ?, 'pending', 0, 0, ?, ?)
                    """,
                    (
                        int(telegram_id), int(order_id), int(order["plan_id"]),
                        now, now,
                    ),
                )

                cur = await db.execute(
                    "SELECT * FROM commerce_payments WHERE id = ?",
                    (payment_id,),
                )
                payment = await cur.fetchone()
                cur = await db.execute(
                    "SELECT * FROM commerce_orders WHERE id = ?",
                    (int(order_id),),
                )
                order = await cur.fetchone()
                cur = await db.execute(
                    "SELECT * FROM entitlements WHERE order_id = ?",
                    (int(order_id),),
                )
                entitlement = await cur.fetchone()
                if payment is None or order is None or entitlement is None:
                    raise RuntimeError("Stars confirmation postcondition failed.")
                await db.commit()
                return (
                    CommercePaymentRecord(**dict(payment)),
                    CommerceOrderRecord(**dict(order)),
                    EntitlementRecord(**dict(entitlement)),
                    created,
                )
            except Exception:
                await db.rollback()
                raise

    async def record_payment_webhook_event(
        self, *, provider: str, provider_event_id: str, event_type: str,
        signature_valid: bool, payload_sha256: str, metadata_json: str = "{}",
    ) -> tuple[int, bool]:
        now = int(time.time())
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                INSERT OR IGNORE INTO payment_webhook_events(
                    provider, provider_event_id, event_type, signature_valid,
                    payload_sha256, metadata_json, processing_status,
                    order_id, payment_id, received_at, applied_at, result_code
                ) VALUES (?, ?, ?, ?, ?, ?, 'received', NULL, NULL, ?, 0, '')
                """,
                (
                    str(provider)[:32], str(provider_event_id)[:160],
                    str(event_type)[:64], 1 if signature_valid else 0,
                    str(payload_sha256)[:64], str(metadata_json)[:2000], now,
                ),
            )
            created = cur.rowcount == 1
            cur = await db.execute(
                """
                SELECT * FROM payment_webhook_events
                WHERE provider = ? AND provider_event_id = ?
                """,
                (str(provider)[:32], str(provider_event_id)[:160]),
            )
            row = await cur.fetchone()
            if row is None:
                await db.rollback()
                raise RuntimeError("Webhook event disappeared after insert.")

            existing_signature_valid = int(row["signature_valid"]) == 1
            incoming_signature_valid = bool(signature_valid)
            incoming_type = str(event_type)[:64]
            incoming_digest = str(payload_sha256)[:64]
            if not existing_signature_valid and incoming_signature_valid:
                await db.execute(
                    """
                    UPDATE payment_webhook_events
                    SET event_type = ?, signature_valid = 1, payload_sha256 = ?,
                        metadata_json = ?, processing_status = 'received',
                        order_id = NULL, payment_id = NULL, received_at = ?,
                        applied_at = 0, result_code = ''
                    WHERE id = ?
                    """,
                    (
                        incoming_type, incoming_digest, str(metadata_json)[:2000],
                        now, int(row["id"]),
                    ),
                )
                created = True
            elif existing_signature_valid and incoming_signature_valid:
                if (
                    str(row["event_type"]) != incoming_type
                    or str(row["payload_sha256"]) != incoming_digest
                ):
                    await db.rollback()
                    raise RuntimeError(
                        "Webhook event identity was reused with different content."
                    )
            await db.commit()
            return int(row["id"]), created

    async def finalize_payment_webhook_event(
        self, event_id: int, *, processing_status: str, result_code: str,
    ) -> PaymentWebhookEventRecord:
        now = int(time.time())
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            await db.execute(
                """
                UPDATE payment_webhook_events
                SET processing_status = ?, result_code = ?, applied_at = ?
                WHERE id = ?
                """,
                (
                    str(processing_status)[:32], str(result_code)[:64],
                    now, int(event_id),
                ),
            )
            cur = await db.execute(
                "SELECT * FROM payment_webhook_events WHERE id = ?",
                (int(event_id),),
            )
            row = await cur.fetchone()
            if row is None:
                await db.rollback()
                raise RuntimeError("Webhook event does not exist.")
            await db.commit()
            return PaymentWebhookEventRecord(**dict(row))

    async def apply_confirmed_payment_event(
        self, *, provider: str, provider_event_id: str, event_type: str,
        signature_valid: bool, payload_sha256: str, metadata_json: str,
        provider_payment_id: str,
        fail_after_payment_update: bool = False,
    ) -> tuple[PaymentWebhookEventRecord, CommercePaymentRecord | None, CommerceOrderRecord | None, EntitlementRecord | None, bool]:
        now = int(time.time())
        provider_value = str(provider)[:32]
        event_value = str(provider_event_id)[:160]
        payment_ref = str(provider_payment_id)[:160]
        digest = str(payload_sha256)[:64]
        event_type_value = str(event_type)[:64]
        metadata_value = str(metadata_json)[:2000]

        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            await db.execute("BEGIN IMMEDIATE")
            try:
                cur = await db.execute(
                    """
                    INSERT OR IGNORE INTO payment_webhook_events(
                        provider, provider_event_id, event_type, signature_valid,
                        payload_sha256, metadata_json, processing_status,
                        order_id, payment_id, received_at, applied_at, result_code,
                        provider_payment_id
                    ) VALUES (?, ?, ?, ?, ?, ?, 'received', NULL, NULL, ?, 0, '', ?)
                    """,
                    (
                        provider_value, event_value, event_type_value,
                        1 if signature_valid else 0, digest, metadata_value, now,
                        payment_ref,
                    ),
                )
                created = cur.rowcount == 1
                cur = await db.execute(
                    """
                    SELECT * FROM payment_webhook_events
                    WHERE provider = ? AND provider_event_id = ?
                    """,
                    (provider_value, event_value),
                )
                event_row = await cur.fetchone()
                if event_row is None:
                    raise RuntimeError("Webhook event disappeared inside transaction.")

                existing_signature_valid = int(event_row["signature_valid"]) == 1
                if not existing_signature_valid and signature_valid:
                    # An unauthenticated request must never poison the provider's
                    # canonical event identity. A later authenticated delivery may
                    # replace the untrusted envelope and continue normally.
                    await db.execute(
                        """
                        UPDATE payment_webhook_events
                        SET event_type = ?, signature_valid = 1, payload_sha256 = ?,
                            metadata_json = ?, processing_status = 'received',
                            order_id = NULL, payment_id = NULL, received_at = ?,
                            applied_at = 0, result_code = '', provider_payment_id = ?
                        WHERE id = ?
                        """,
                        (
                            event_type_value, digest, metadata_value, now,
                            payment_ref, int(event_row["id"]),
                        ),
                    )
                    cur = await db.execute(
                        "SELECT * FROM payment_webhook_events WHERE id = ?",
                        (int(event_row["id"]),),
                    )
                    event_row = await cur.fetchone()
                    created = True
                    existing_signature_valid = True
                elif existing_signature_valid and not signature_valid:
                    # Do not let an invalid replay alter or re-drive a previously
                    # authenticated provider event.
                    await db.commit()
                    return (
                        PaymentWebhookEventRecord(**dict(event_row)),
                        None, None, None, False,
                    )
                elif not existing_signature_valid and not signature_valid:
                    await db.execute(
                        """
                        UPDATE payment_webhook_events
                        SET processing_status = 'ignored', applied_at = ?,
                            result_code = 'invalid_signature'
                        WHERE id = ?
                        """,
                        (now, int(event_row["id"])),
                    )
                    cur = await db.execute(
                        "SELECT * FROM payment_webhook_events WHERE id = ?",
                        (int(event_row["id"]),),
                    )
                    event_row = await cur.fetchone()
                    await db.commit()
                    return (
                        PaymentWebhookEventRecord(**dict(event_row)),
                        None, None, None, created,
                    )

                if (
                    str(event_row["event_type"]) != event_type_value
                    or str(event_row["payload_sha256"]) != digest
                ):
                    raise RuntimeError("Webhook event identity was reused with different content.")

                stored_payment_ref = str(event_row["provider_payment_id"] or "")
                if stored_payment_ref and stored_payment_ref != payment_ref:
                    raise RuntimeError(
                        "Webhook event identity was reused for a different payment reference."
                    )
                if not stored_payment_ref:
                    await db.execute(
                        """
                        UPDATE payment_webhook_events
                        SET provider_payment_id = ?
                        WHERE id = ?
                        """,
                        (payment_ref, int(event_row["id"])),
                    )
                    cur = await db.execute(
                        "SELECT * FROM payment_webhook_events WHERE id = ?",
                        (int(event_row["id"]),),
                    )
                    event_row = await cur.fetchone()

                if str(event_row["processing_status"]) == "applied":
                    payment = None
                    order = None
                    entitlement = None
                    if event_row["payment_id"] is not None:
                        cur = await db.execute(
                            "SELECT * FROM commerce_payments WHERE id = ?",
                            (int(event_row["payment_id"]),),
                        )
                        row = await cur.fetchone()
                        payment = CommercePaymentRecord(**dict(row)) if row else None
                    if event_row["order_id"] is not None:
                        cur = await db.execute(
                            "SELECT * FROM commerce_orders WHERE id = ?",
                            (int(event_row["order_id"]),),
                        )
                        row = await cur.fetchone()
                        order = CommerceOrderRecord(**dict(row)) if row else None
                        cur = await db.execute(
                            "SELECT * FROM entitlements WHERE order_id = ?",
                            (int(event_row["order_id"]),),
                        )
                        row = await cur.fetchone()
                        entitlement = EntitlementRecord(**dict(row)) if row else None
                    await db.commit()
                    return (
                        PaymentWebhookEventRecord(**dict(event_row)),
                        payment, order, entitlement, created,
                    )

                if not signature_valid:
                    await db.execute(
                        """
                        UPDATE payment_webhook_events
                        SET processing_status = 'ignored', applied_at = ?, result_code = 'invalid_signature'
                        WHERE id = ?
                        """,
                        (now, int(event_row["id"])),
                    )
                    cur = await db.execute(
                        "SELECT * FROM payment_webhook_events WHERE id = ?",
                        (int(event_row["id"]),),
                    )
                    event_row = await cur.fetchone()
                    await db.commit()
                    return (
                        PaymentWebhookEventRecord(**dict(event_row)),
                        None, None, None, created,
                    )

                cur = await db.execute(
                    """
                    SELECT * FROM commerce_payments
                    WHERE provider = ? AND provider_payment_id = ?
                    """,
                    (provider_value, payment_ref),
                )
                payment_row = await cur.fetchone()
                if payment_row is None:
                    await db.execute(
                        """
                        UPDATE payment_webhook_events
                        SET processing_status = 'failed', applied_at = ?, result_code = 'payment_not_found'
                        WHERE id = ?
                        """,
                        (now, int(event_row["id"])),
                    )
                    cur = await db.execute(
                        "SELECT * FROM payment_webhook_events WHERE id = ?",
                        (int(event_row["id"]),),
                    )
                    event_row = await cur.fetchone()
                    await db.commit()
                    return (
                        PaymentWebhookEventRecord(**dict(event_row)),
                        None, None, None, created,
                    )

                cur = await db.execute(
                    "SELECT * FROM commerce_orders WHERE id = ?",
                    (int(payment_row["order_id"]),),
                )
                order_row = await cur.fetchone()
                if order_row is None:
                    raise RuntimeError("Payment references a missing order.")
                if (
                    int(payment_row["amount_minor"]) != int(order_row["amount_minor"])
                    or str(payment_row["currency"]) != str(order_row["currency"])
                ):
                    raise RuntimeError("Payment amount/currency does not match order.")
                if str(payment_row["status"]) not in {"created", "pending", "unknown", "confirmed"}:
                    raise RuntimeError(
                        f"Payment status {payment_row['status']!r} cannot be confirmed."
                    )
                if str(order_row["status"]) not in {"created", "awaiting_payment", "paid"}:
                    raise RuntimeError(
                        f"Order status {order_row['status']!r} cannot be paid."
                    )

                if str(payment_row["status"]) != "confirmed":
                    await db.execute(
                        """
                        UPDATE commerce_payments
                        SET status = 'confirmed', updated_at = ?,
                            confirmed_at = CASE WHEN confirmed_at = 0 THEN ? ELSE confirmed_at END
                        WHERE id = ?
                        """,
                        (now, now, int(payment_row["id"])),
                    )

                if fail_after_payment_update:
                    raise RuntimeError("synthetic failure after payment update")

                if str(order_row["status"]) != "paid":
                    await db.execute(
                        """
                        UPDATE commerce_orders
                        SET status = 'paid', updated_at = ?,
                            paid_at = CASE WHEN paid_at = 0 THEN ? ELSE paid_at END
                        WHERE id = ?
                        """,
                        (now, now, int(order_row["id"])),
                    )

                await db.execute(
                    """
                    INSERT OR IGNORE INTO entitlements(
                        telegram_id, order_id, plan_id, status, starts_at,
                        expires_at, created_at, updated_at
                    ) VALUES (?, ?, ?, 'pending', 0, 0, ?, ?)
                    """,
                    (
                        int(order_row["telegram_id"]), int(order_row["id"]),
                        int(order_row["plan_id"]), now, now,
                    ),
                )
                cur = await db.execute(
                    "SELECT * FROM entitlements WHERE order_id = ?",
                    (int(order_row["id"]),),
                )
                entitlement_row = await cur.fetchone()
                if entitlement_row is None:
                    raise RuntimeError("Entitlement was not created.")

                await db.execute(
                    """
                    UPDATE payment_webhook_events
                    SET processing_status = 'applied', order_id = ?, payment_id = ?,
                        applied_at = ?, result_code = 'confirmed'
                    WHERE id = ?
                    """,
                    (
                        int(order_row["id"]), int(payment_row["id"]), now,
                        int(event_row["id"]),
                    ),
                )

                cur = await db.execute(
                    "SELECT * FROM payment_webhook_events WHERE id = ?",
                    (int(event_row["id"]),),
                )
                event_row = await cur.fetchone()
                cur = await db.execute(
                    "SELECT * FROM commerce_payments WHERE id = ?",
                    (int(payment_row["id"]),),
                )
                payment_row = await cur.fetchone()
                cur = await db.execute(
                    "SELECT * FROM commerce_orders WHERE id = ?",
                    (int(order_row["id"]),),
                )
                order_row = await cur.fetchone()
                await db.commit()
                return (
                    PaymentWebhookEventRecord(**dict(event_row)),
                    CommercePaymentRecord(**dict(payment_row)),
                    CommerceOrderRecord(**dict(order_row)),
                    EntitlementRecord(**dict(entitlement_row)),
                    created,
                )
            except Exception:
                await db.rollback()
                raise

    async def list_recoverable_payment_webhook_events(
        self, *, limit: int = 100,
    ) -> list[PaymentWebhookEventRecord]:
        safe_limit = max(1, min(500, int(limit)))
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT * FROM payment_webhook_events
                WHERE signature_valid = 1
                  AND event_type = 'payment.confirmed'
                  AND processing_status = 'failed'
                  AND result_code = 'payment_not_found'
                  AND provider_payment_id != ''
                ORDER BY received_at ASC, id ASC
                LIMIT ?
                """,
                (safe_limit,),
            )
            rows = await cur.fetchall()
            return [PaymentWebhookEventRecord(**dict(row)) for row in rows]

    async def get_payment_webhook_event(
        self, event_id: int,
    ) -> PaymentWebhookEventRecord | None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM payment_webhook_events WHERE id = ?",
                (int(event_id),),
            )
            row = await cur.fetchone()
            return PaymentWebhookEventRecord(**dict(row)) if row else None

    async def ensure_entitlement_for_order(
        self, *, telegram_id: int, order_id: int, plan_id: int,
    ) -> tuple[EntitlementRecord, bool]:
        now = int(time.time())
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            await db.execute("BEGIN IMMEDIATE")
            cur = await db.execute(
                "SELECT * FROM entitlements WHERE order_id = ?",
                (int(order_id),),
            )
            row = await cur.fetchone()
            if row:
                await db.commit()
                return EntitlementRecord(**dict(row)), False
            cur = await db.execute(
                """
                INSERT INTO entitlements(
                    telegram_id, order_id, plan_id, status, starts_at,
                    expires_at, created_at, updated_at
                ) VALUES (?, ?, ?, 'pending', 0, 0, ?, ?)
                """,
                (int(telegram_id), int(order_id), int(plan_id), now, now),
            )
            entitlement_id = int(cur.lastrowid)
            cur = await db.execute(
                "SELECT * FROM entitlements WHERE id = ?",
                (entitlement_id,),
            )
            row = await cur.fetchone()
            await db.commit()
            return EntitlementRecord(**dict(row)), True

    async def list_pending_entitlements(
        self, *, limit: int = 100,
    ) -> list[EntitlementRecord]:
        safe_limit = max(1, min(500, int(limit)))
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT * FROM entitlements
                WHERE status = 'pending'
                ORDER BY created_at ASC, id ASC
                LIMIT ?
                """,
                (safe_limit,),
            )
            rows = await cur.fetchall()
            return [EntitlementRecord(**dict(row)) for row in rows]

    async def list_expired_active_entitlements(
        self, *, now: int | None = None, limit: int = 100,
    ) -> list[EntitlementRecord]:
        safe_limit = max(1, min(500, int(limit)))
        cutoff = int(time.time()) if now is None else int(now)
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT * FROM entitlements
                WHERE status IN ('active', 'suspended')
                  AND expires_at > 0
                  AND expires_at <= ?
                ORDER BY expires_at ASC, id ASC
                LIMIT ?
                """,
                (cutoff, safe_limit),
            )
            rows = await cur.fetchall()
            return [EntitlementRecord(**dict(row)) for row in rows]

    async def get_latest_entitlement_for_user(
        self, telegram_id: int,
    ) -> EntitlementRecord | None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT * FROM entitlements
                WHERE telegram_id = ?
                ORDER BY updated_at DESC, id DESC
                LIMIT 1
                """,
                (int(telegram_id),),
            )
            row = await cur.fetchone()
            return EntitlementRecord(**dict(row)) if row else None

    async def get_entitlement(self, entitlement_id: int) -> EntitlementRecord | None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM entitlements WHERE id = ?",
                (int(entitlement_id),),
            )
            row = await cur.fetchone()
            return EntitlementRecord(**dict(row)) if row else None

    async def transition_entitlement(
        self, entitlement_id: int, *, expected_statuses: set[str],
        target_status: str, starts_at: int | None = None,
        expires_at: int | None = None,
    ) -> EntitlementRecord:
        now = int(time.time())
        expected = {str(value) for value in expected_statuses}
        if not expected:
            raise RuntimeError("At least one expected entitlement status is required.")
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            await db.execute("BEGIN IMMEDIATE")
            try:
                cur = await db.execute(
                    "SELECT * FROM entitlements WHERE id = ?",
                    (int(entitlement_id),),
                )
                row = await cur.fetchone()
                if row is None:
                    raise RuntimeError("Entitlement does not exist.")
                current = str(row["status"])
                if current == str(target_status):
                    await db.commit()
                    return EntitlementRecord(**dict(row))
                if current not in expected:
                    raise RuntimeError(
                        f"Entitlement status {current!r} cannot transition to {target_status!r}."
                    )
                next_starts = int(row["starts_at"]) if starts_at is None else int(starts_at)
                next_expires = int(row["expires_at"]) if expires_at is None else int(expires_at)
                await db.execute(
                    """
                    UPDATE entitlements
                    SET status = ?, starts_at = ?, expires_at = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        str(target_status), max(0, next_starts), max(0, next_expires),
                        now, int(entitlement_id),
                    ),
                )
                cur = await db.execute(
                    "SELECT * FROM entitlements WHERE id = ?",
                    (int(entitlement_id),),
                )
                updated = await cur.fetchone()
                await db.commit()
                return EntitlementRecord(**dict(updated))
            except Exception:
                await db.rollback()
                raise

    async def transition_entitlement_quota_reset(
        self,
        entitlement_id: int,
        *,
        expected_statuses: set[str],
        target_status: str,
    ) -> EntitlementRecord:
        allowed = {
            "pending",
            "legacy",
            "not_required",
            "in_flight",
            "success",
            "failed",
            "unknown",
        }
        target = str(target_status)
        if target not in allowed:
            raise RuntimeError(f"Unsupported quota reset status: {target!r}.")
        expected = {str(value) for value in expected_statuses}
        if not expected:
            raise RuntimeError("At least one expected quota reset status is required.")
        now = int(time.time())
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            await db.execute("BEGIN IMMEDIATE")
            try:
                cur = await db.execute(
                    "SELECT * FROM entitlements WHERE id = ?",
                    (int(entitlement_id),),
                )
                row = await cur.fetchone()
                if row is None:
                    raise RuntimeError("Entitlement does not exist.")
                current = str(row["quota_reset_status"])
                if current == target:
                    await db.commit()
                    return EntitlementRecord(**dict(row))
                if current not in expected:
                    raise RuntimeError(
                        f"Quota reset status {current!r} cannot transition to {target!r}."
                    )
                await db.execute(
                    """
                    UPDATE entitlements
                    SET quota_reset_status = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (target, now, int(entitlement_id)),
                )
                cur = await db.execute(
                    "SELECT * FROM entitlements WHERE id = ?",
                    (int(entitlement_id),),
                )
                updated = await cur.fetchone()
                await db.commit()
                return EntitlementRecord(**dict(updated))
            except Exception:
                await db.rollback()
                raise

    async def accept_customer_terms(
        self, *, telegram_id: int, terms_version: str,
    ) -> None:
        version = str(terms_version).strip()
        if not version or len(version) > 64:
            raise ValueError("Invalid terms version.")
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                INSERT OR IGNORE INTO customer_terms_acceptance(
                    telegram_id, terms_version, accepted_at
                ) VALUES (?, ?, ?)
                """,
                (int(telegram_id), version, int(time.time())),
            )
            await db.commit()

    async def has_customer_accepted_terms(
        self, *, telegram_id: int, terms_version: str,
    ) -> bool:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                """
                SELECT 1 FROM customer_terms_acceptance
                WHERE telegram_id = ? AND terms_version = ?
                """,
                (int(telegram_id), str(terms_version).strip()),
            )
            return await cur.fetchone() is not None

    async def get_commerce_payment(self, payment_id: int) -> CommercePaymentRecord | None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM commerce_payments WHERE id = ?",
                (int(payment_id),),
            )
            row = await cur.fetchone()
            return CommercePaymentRecord(**dict(row)) if row else None

    async def get_commerce_order(self, order_id: int) -> CommerceOrderRecord | None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM commerce_orders WHERE id = ?",
                (int(order_id),),
            )
            row = await cur.fetchone()
            return CommerceOrderRecord(**dict(row)) if row else None

    async def begin_stars_refund(
        self, *, payment_id: int, requested_by: int, operation_id: str,
    ) -> StarsRefundOperationRecord:
        now = int(time.time())
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            await db.execute("BEGIN IMMEDIATE")
            try:
                cur = await db.execute(
                    "SELECT * FROM commerce_payments WHERE id = ?",
                    (int(payment_id),),
                )
                payment = await cur.fetchone()
                if payment is None:
                    raise RuntimeError("Commerce payment does not exist.")
                if str(payment["provider"]) != "telegram_stars":
                    raise RuntimeError("Only Telegram Stars payments can be refunded here.")
                if str(payment["status"]) != "confirmed":
                    raise RuntimeError("Only confirmed Telegram Stars payments can be refunded.")
                cur = await db.execute(
                    "SELECT * FROM commerce_orders WHERE id = ?",
                    (int(payment["order_id"]),),
                )
                order = await cur.fetchone()
                if order is None:
                    raise RuntimeError("Commerce order does not exist.")
                cur = await db.execute(
                    "SELECT * FROM stars_refund_operations WHERE payment_id = ?",
                    (int(payment_id),),
                )
                existing = await cur.fetchone()
                if existing is not None:
                    await db.commit()
                    return StarsRefundOperationRecord(**dict(existing))
                cur = await db.execute(
                    """
                    INSERT INTO stars_refund_operations(
                        operation_id, payment_id, telegram_id, provider_payment_id,
                        status, requested_by, created_at, updated_at, error
                    ) VALUES (?, ?, ?, ?, 'in_flight', ?, ?, ?, '')
                    """,
                    (
                        str(operation_id), int(payment_id), int(order["telegram_id"]),
                        str(payment["provider_payment_id"]), int(requested_by), now, now,
                    ),
                )
                op_id = int(cur.lastrowid)
                cur = await db.execute(
                    "SELECT * FROM stars_refund_operations WHERE id = ?",
                    (op_id,),
                )
                row = await cur.fetchone()
                await db.commit()
                return StarsRefundOperationRecord(**dict(row))
            except Exception:
                await db.rollback()
                raise

    async def finish_stars_refund(
        self, operation_id: str, *, status: str, error: str = "",
    ) -> StarsRefundOperationRecord:
        if status not in {"success", "failed", "unknown"}:
            raise ValueError("Invalid Stars refund status.")
        now = int(time.time())
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            await db.execute("BEGIN IMMEDIATE")
            try:
                cur = await db.execute(
                    "SELECT * FROM stars_refund_operations WHERE operation_id = ?",
                    (str(operation_id),),
                )
                row = await cur.fetchone()
                if row is None:
                    raise RuntimeError("Stars refund operation does not exist.")
                if str(row["status"]) != "in_flight":
                    await db.commit()
                    return StarsRefundOperationRecord(**dict(row))
                await db.execute(
                    """
                    UPDATE stars_refund_operations
                    SET status = ?, updated_at = ?, error = ?
                    WHERE operation_id = ?
                    """,
                    (status, now, str(error)[:500], str(operation_id)),
                )
                if status == "success":
                    await db.execute(
                        """
                        UPDATE commerce_payments
                        SET status = 'refunded', updated_at = ?
                        WHERE id = ? AND status = 'confirmed'
                        """,
                        (now, int(row["payment_id"])),
                    )
                cur = await db.execute(
                    "SELECT * FROM stars_refund_operations WHERE operation_id = ?",
                    (str(operation_id),),
                )
                updated = await cur.fetchone()
                await db.commit()
                return StarsRefundOperationRecord(**dict(updated))
            except Exception:
                await db.rollback()
                raise

    async def get_stars_refund_for_payment(
        self, payment_id: int,
    ) -> StarsRefundOperationRecord | None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM stars_refund_operations WHERE payment_id = ?",
                (int(payment_id),),
            )
            row = await cur.fetchone()
            return StarsRefundOperationRecord(**dict(row)) if row else None

    # --- Promo codes ---------------------------------------------------

    async def list_promo_codes(self) -> list[PromoCodeRecord]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM promo_codes ORDER BY active DESC, id DESC"
            )
            rows = await cur.fetchall()
            return [PromoCodeRecord(**dict(r)) for r in rows]

    async def get_promo_code(self, promo_id: int) -> PromoCodeRecord | None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM promo_codes WHERE id = ?", (int(promo_id),))
            row = await cur.fetchone()
            return PromoCodeRecord(**dict(row)) if row else None

    async def create_promo_code(
        self, *, code: str, discount_type: str, value: int, currency: str = "RUB",
        plan_id: int | None = None, max_uses: int = 0, expires_at: int = 0,
    ) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                """
                INSERT INTO promo_codes(
                    code, discount_type, value, currency, plan_id, max_uses,
                    uses_count, expires_at, active, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 0, ?, 1, ?)
                """,
                (
                    code.strip().upper(), discount_type, int(value), currency.upper(), plan_id,
                    max(0, int(max_uses)), max(0, int(expires_at)), int(time.time()),
                ),
            )
            await db.commit()
            return int(cur.lastrowid)

    async def set_promo_active(self, promo_id: int, active: bool) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "UPDATE promo_codes SET active = ? WHERE id = ?",
                (1 if active else 0, int(promo_id)),
            )
            await db.commit()

    async def delete_promo_code(self, promo_id: int) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute("DELETE FROM promo_codes WHERE id = ?", (int(promo_id),))
            await db.commit()

    # --- Administrators -----------------------------------------------

    async def list_administrators(self) -> list[AdministratorRecord]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM administrators ORDER BY enabled DESC, role, telegram_id"
            )
            rows = await cur.fetchall()
            return [AdministratorRecord(**dict(r)) for r in rows]

    async def get_administrator(self, telegram_id: int) -> AdministratorRecord | None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM administrators WHERE telegram_id = ?", (int(telegram_id),)
            )
            row = await cur.fetchone()
            return AdministratorRecord(**dict(row)) if row else None

    async def upsert_administrator(
        self, *, telegram_id: int, role: str, enabled: bool = True, added_by: int = 0,
    ) -> None:
        now = int(time.time())
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                INSERT INTO administrators(telegram_id, role, enabled, added_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(telegram_id) DO UPDATE SET
                    role=excluded.role, enabled=excluded.enabled, updated_at=excluded.updated_at
                """,
                (int(telegram_id), role, 1 if enabled else 0, int(added_by), now, now),
            )
            await db.commit()

    async def set_administrator_enabled(self, telegram_id: int, enabled: bool) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "UPDATE administrators SET enabled = ?, updated_at = ? WHERE telegram_id = ?",
                (1 if enabled else 0, int(time.time()), int(telegram_id)),
            )
            await db.commit()

    async def delete_administrator(self, telegram_id: int) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute("DELETE FROM administrators WHERE telegram_id = ?", (int(telegram_id),))
            await db.commit()

    # --- Runtime settings ---------------------------------------------

    async def list_runtime_settings(self) -> list[RuntimeSettingRecord]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM runtime_settings ORDER BY key")
            rows = await cur.fetchall()
            return [RuntimeSettingRecord(**dict(r)) for r in rows]

    async def get_runtime_setting(self, key: str, default: str | None = None) -> str | None:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT value FROM runtime_settings WHERE key = ?", (key,))
            row = await cur.fetchone()
            return str(row[0]) if row else default

    async def set_runtime_setting(self, key: str, value: str, *, updated_by: int = 0) -> None:
        now = int(time.time())
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                INSERT INTO runtime_settings(key, value, updated_by, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value=excluded.value, updated_by=excluded.updated_by, updated_at=excluded.updated_at
                """,
                (key, str(value), int(updated_by), now),
            )
            await db.commit()

    async def delete_runtime_setting(self, key: str) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute("DELETE FROM runtime_settings WHERE key = ?", (key,))
            await db.commit()

    async def get_feature_flag_records(self) -> dict[str, str]:
        """Single-snapshot, fail-closed read of both flags and revision keys."""
        keys = (
            "client_portal_enabled", "client_payment_acceptance_enabled",
            "client_portal_enabled:revision", "client_payment_acceptance_enabled:revision",
        )
        async with aiosqlite.connect(self.path) as connection:
            cur = await connection.execute(
                "SELECT key, value FROM runtime_settings WHERE key IN (?, ?, ?, ?)", keys
            )
            return {str(key): str(value) for key, value in await cur.fetchall()}

    async def compare_and_set_feature_flag(
        self, *, key: str, expected_revision: int, enabled: bool,
        actor_id: int, actor_username: str = "",
    ) -> bool:
        """CAS and audit are one SQLite write transaction, never a blind toggle."""
        from client_flags import FEATURE_KEYS, MAX_REVISION, parse_override, parse_revision
        if key not in FEATURE_KEYS.values() or type(enabled) is not bool:
            raise ValueError("Invalid feature update")
        if actor_id <= 0 or not 0 <= expected_revision < MAX_REVISION:
            raise ValueError("Invalid feature revision/actor")
        now = int(time.time())
        async with aiosqlite.connect(self.path) as connection:
            await connection.execute("BEGIN IMMEDIATE")
            cur = await connection.execute(
                "SELECT key, value FROM runtime_settings WHERE key IN (?, ?)",
                (key, key + ":revision"),
            )
            values = {str(k): str(v) for k, v in await cur.fetchall()}
            current = parse_override(values.get(key))
            revision = parse_revision(values.get(key + ":revision"))
            if revision != expected_revision or current is enabled:
                await connection.rollback()
                return False
            for setting_key, setting_value in (
                (key, "true" if enabled else "false"),
                (key + ":revision", str(revision + 1)),
            ):
                await connection.execute(
                    "INSERT INTO runtime_settings(key, value, updated_by, updated_at) "
                    "VALUES (?, ?, ?, ?) ON CONFLICT(key) DO UPDATE SET "
                    "value=excluded.value, updated_by=excluded.updated_by, updated_at=excluded.updated_at",
                    (setting_key, setting_value, actor_id, now),
                )
            await connection.execute(
                "INSERT INTO audit_log(actor_id, actor_username, action, target_type, "
                "target_id, details, success, created_at) VALUES (?, ?, ?, ?, ?, ?, 1, ?)",
                (actor_id, actor_username[:64], "client.feature.toggle", "setting",
                 key, f"old={current}; new={enabled}; revision={revision + 1}", now),
            )
            await connection.commit()
            return True

    # --- Inbound templates ---------------------------------------------

    async def list_inbound_templates(self) -> list[InboundTemplateRecord]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM inbound_templates ORDER BY name COLLATE NOCASE, id"
            )
            rows = await cur.fetchall()
            return [InboundTemplateRecord(**dict(r)) for r in rows]

    async def get_inbound_template(self, template_id: int) -> InboundTemplateRecord | None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM inbound_templates WHERE id = ?", (int(template_id),)
            )
            row = await cur.fetchone()
            return InboundTemplateRecord(**dict(row)) if row else None

    async def create_inbound_template(
        self, *, name: str, source_inbound_id: int, protocol: str, payload_json: str
    ) -> int:
        now = int(time.time())
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                """
                INSERT INTO inbound_templates(
                    name, source_inbound_id, protocol, payload_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    name.strip(), int(source_inbound_id), protocol.strip().lower(),
                    payload_json, now, now,
                ),
            )
            await db.commit()
            return int(cur.lastrowid)

    async def update_inbound_template_payload(
        self, template_id: int, *, source_inbound_id: int, protocol: str, payload_json: str
    ) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                UPDATE inbound_templates
                SET source_inbound_id = ?, protocol = ?, payload_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    int(source_inbound_id), protocol.strip().lower(), payload_json,
                    int(time.time()), int(template_id),
                ),
            )
            await db.commit()

    async def delete_inbound_template(self, template_id: int) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute("DELETE FROM inbound_templates WHERE id = ?", (int(template_id),))
            await db.commit()

    # --- Audit log -----------------------------------------------------

    async def add_audit(
        self,
        *,
        actor_id: int,
        actor_username: str = "",
        action: str,
        target_type: str = "",
        target_id: str = "",
        details: str = "",
        success: bool = True,
    ) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                """
                INSERT INTO audit_log(
                    actor_id, actor_username, action, target_type, target_id,
                    details, success, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(actor_id),
                    (actor_username or "")[:64],
                    (action or "")[:96],
                    (target_type or "")[:64],
                    (target_id or "")[:160],
                    (details or "")[:1500],
                    1 if success else 0,
                    int(time.time()),
                ),
            )
            await db.commit()
            return int(cur.lastrowid)

    async def list_audit(self, *, limit: int = 20, offset: int = 0) -> list[AuditRecord]:
        limit = max(1, min(100, int(limit)))
        offset = max(0, int(offset))
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM audit_log ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
            rows = await cur.fetchall()
            return [AuditRecord(**dict(r)) for r in rows]

    async def get_audit(self, audit_id: int) -> AuditRecord | None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM audit_log WHERE id = ?",
                (int(audit_id),),
            )
            row = await cur.fetchone()
            return AuditRecord(**dict(row)) if row else None

    async def list_user_audit(
        self,
        telegram_id: int,
        email: str,
        *,
        limit: int = 30,
        offset: int = 0,
    ) -> list[AuditRecord]:
        limit = max(1, min(100, int(limit)))
        offset = max(0, int(offset))
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT * FROM audit_log
                WHERE target_type = 'user' AND target_id IN (?, ?)
                ORDER BY id DESC
                LIMIT ? OFFSET ?
                """,
                (str(email), str(int(telegram_id)), limit, offset),
            )
            rows = await cur.fetchall()
            return [AuditRecord(**dict(r)) for r in rows]

    async def count_user_audit(self, telegram_id: int, email: str) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                """
                SELECT COUNT(*) FROM audit_log
                WHERE target_type = 'user' AND target_id IN (?, ?)
                """,
                (str(email), str(int(telegram_id))),
            )
            row = await cur.fetchone()
            return int(row[0] if row else 0)

    async def count_audit(self) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT COUNT(*) FROM audit_log")
            row = await cur.fetchone()
            return int(row[0] if row else 0)

    # --- Job runs ------------------------------------------------------

    async def start_job_run(
        self,
        *,
        name: str,
        trigger: str,
        actor_id: int = 0,
        details: str = "",
    ) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                """
                INSERT INTO job_runs(name, trigger, actor_id, status, started_at, details)
                VALUES (?, ?, ?, 'running', ?, ?)
                """,
                (
                    (name or "")[:96],
                    (trigger or "")[:32],
                    int(actor_id),
                    int(time.time()),
                    (details or "")[:1500],
                ),
            )
            await db.commit()
            return int(cur.lastrowid)

    async def finish_job_run(
        self,
        run_id: int,
        *,
        status: str,
        duration_ms: int,
        details: str = "",
    ) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                UPDATE job_runs
                SET status = ?, finished_at = ?, duration_ms = ?, details = ?
                WHERE id = ?
                """,
                (
                    (status or "unknown")[:24],
                    int(time.time()),
                    max(0, int(duration_ms)),
                    (details or "")[:1500],
                    int(run_id),
                ),
            )
            await db.commit()


    async def get_job_run(self, run_id: int) -> JobRunRecord | None:
        async with aiosqlite.connect(self.path) as conn:
            conn.row_factory = aiosqlite.Row
            row = await (await conn.execute(
                "SELECT * FROM job_runs WHERE id = ?", (int(run_id),)
            )).fetchone()
            return JobRunRecord(**dict(row)) if row is not None else None

    async def get_bot_update_acknowledgment(
        self, run_id: int
    ) -> BotUpdateAcknowledgment | None:
        async with aiosqlite.connect(self.path) as conn:
            conn.row_factory = aiosqlite.Row
            row = await (await conn.execute(
                "SELECT * FROM bot_update_acknowledgments WHERE job_run_id = ?",
                (int(run_id),),
            )).fetchone()
            return BotUpdateAcknowledgment(**dict(row)) if row is not None else None

    async def list_bot_update_acknowledged_run_ids(
        self, run_ids: list[int]
    ) -> set[int]:
        ids = list(dict.fromkeys(int(value) for value in run_ids if int(value) > 0))
        if not ids:
            return set()
        placeholders = ", ".join("?" for _ in ids)
        async with aiosqlite.connect(self.path) as conn:
            rows = await (await conn.execute(
                f"SELECT job_run_id FROM bot_update_acknowledgments WHERE job_run_id IN ({placeholders})",
                ids,
            )).fetchall()
            return {int(row[0]) for row in rows}

    async def acknowledge_bot_update_unknown(
        self, run_id: int, *, actor_id: int, actor_username: str,
        reason_code: str, evidence,
    ) -> bool:
        """Atomic append-only finding + audit; duplicates are no-ops."""
        if reason_code not in {"reviewed", "recovered", "insufficient"}:
            raise ValueError("Unrecognized historical incident reason")
        if actor_id <= 0 or run_id <= 0:
            raise ValueError("Invalid actor or run identity")
        async with aiosqlite.connect(self.path, timeout=15) as conn:
            try:
                await conn.execute("BEGIN IMMEDIATE")
                run = await (await conn.execute(
                    "SELECT name, status FROM job_runs WHERE id = ?", (int(run_id),)
                )).fetchone()
                if run is None or run[0] != "bot.update" or run[1] != "unknown":
                    raise ValueError("Historical bot.update unknown no longer exists")
                existing = await (await conn.execute(
                    "SELECT 1 FROM bot_update_acknowledgments WHERE job_run_id = ?",
                    (int(run_id),),
                )).fetchone()
                if existing is not None:
                    await conn.rollback()
                    return False
                now = int(time.time())
                await conn.execute(
                    """
                    INSERT INTO bot_update_acknowledgments(
                        job_run_id, actor_id, actor_username, reason_code,
                        evidence_code, operation_id, target_release, agent_state,
                        target_sha, current_release, current_sha, postcondition,
                        acknowledged_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        int(run_id), int(actor_id), str(actor_username or "")[:64],
                        reason_code, str(evidence.code)[:64],
                        str(evidence.operation_id)[:32],
                        str(evidence.requested_release)[:64],
                        str(evidence.agent_state)[:24], str(evidence.target_sha)[:40],
                        str(evidence.current_release)[:64],
                        str(evidence.current_sha)[:40],
                        str(evidence.postcondition)[:32], now,
                    ),
                )
                await conn.execute(
                    """
                    INSERT INTO audit_log(
                        actor_id, actor_username, action, target_type, target_id,
                        details, success, created_at
                    ) VALUES (?, ?, 'bot.update.unknown.acknowledged', 'job_run',
                              ?, ?, 1, ?)
                    """,
                    (
                        int(actor_id), str(actor_username or "")[:64], str(int(run_id)),
                        f"reason={reason_code}; evidence={str(evidence.code)[:64]}; "
                        f"operation_id={str(evidence.operation_id)[:32]}; "
                        f"postcondition={str(evidence.postcondition)[:32]}", now,
                    ),
                )
                await conn.commit()
                return True
            except Exception:
                await conn.rollback()
                raise

    async def list_job_runs(self, *, name: str | None = None, limit: int = 20) -> list[JobRunRecord]:
        limit = max(1, min(100, int(limit)))
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            if name:
                cur = await db.execute(
                    "SELECT * FROM job_runs WHERE name = ? ORDER BY id DESC LIMIT ?",
                    (name, limit),
                )
            else:
                cur = await db.execute(
                    "SELECT * FROM job_runs ORDER BY id DESC LIMIT ?",
                    (limit,),
                )
            rows = await cur.fetchall()
            return [JobRunRecord(**dict(r)) for r in rows]

    async def last_job_run(self, name: str) -> JobRunRecord | None:
        rows = await self.list_job_runs(name=name, limit=1)
        return rows[0] if rows else None

    async def list_running_job_runs(self, *, limit: int = 100) -> list[JobRunRecord]:
        limit = max(1, min(500, int(limit)))
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM job_runs WHERE status = 'running' ORDER BY id ASC LIMIT ?",
                (limit,),
            )
            rows = await cur.fetchall()
            return [JobRunRecord(**dict(r)) for r in rows]

    async def fail_stale_job_runs(self, *, older_than_seconds: int = 21600) -> int:
        cutoff = int(time.time()) - max(60, int(older_than_seconds))
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                """
                UPDATE job_runs
                SET status = 'failed', finished_at = ?, details =
                    CASE WHEN details = '' THEN 'process stopped before job completion' ELSE details END
                WHERE status = 'running' AND started_at < ?
                """,
                (int(time.time()), cutoff),
            )
            await db.commit()
            return int(cur.rowcount or 0)
    # --- Alerts --------------------------------------------------------

    async def list_alert_rules(self) -> list[AlertRuleRecord]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM alert_rules ORDER BY code")
            rows = await cur.fetchall()
            return [AlertRuleRecord(**dict(r)) for r in rows]

    async def get_alert_rule(self, code: str) -> AlertRuleRecord | None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM alert_rules WHERE code = ?", (code,))
            row = await cur.fetchone()
            return AlertRuleRecord(**dict(row)) if row else None

    async def set_alert_rule_enabled(self, code: str, enabled: bool) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "UPDATE alert_rules SET enabled = ?, updated_at = ? WHERE code = ?",
                (1 if enabled else 0, int(time.time()), code),
            )
            await db.commit()

    async def set_alert_rule_threshold(self, code: str, threshold: int) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "UPDATE alert_rules SET threshold = ?, updated_at = ? WHERE code = ?",
                (max(0, int(threshold)), int(time.time()), code),
            )
            await db.commit()

    async def list_alert_states(self, *, active_only: bool = False) -> list[AlertStateRecord]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            if active_only:
                cur = await db.execute(
                    "SELECT * FROM alert_state WHERE active = 1 ORDER BY last_seen DESC"
                )
            else:
                cur = await db.execute("SELECT * FROM alert_state ORDER BY last_seen DESC")
            rows = await cur.fetchall()
            return [AlertStateRecord(**dict(r)) for r in rows]

    async def get_alert_state(self, code: str, target: str) -> AlertStateRecord | None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM alert_state WHERE code = ? AND target = ?",
                (code, target),
            )
            row = await cur.fetchone()
            return AlertStateRecord(**dict(row)) if row else None

    async def update_alert_state(
        self, *, code: str, target: str, active: bool, value: str = "",
        notified_at: int | None = None,
        reset_first_seen: bool = False,
    ) -> AlertStateRecord:
        now = int(time.time())
        existing = await self.get_alert_state(code, target)
        # A newer failed job run is a distinct incident, even when the
        # previous run is still active. The historical job run remains intact.
        first_seen = now if active and (
            reset_first_seen or not existing or not existing.active
        ) else (existing.first_seen if existing else 0)
        last_notified = existing.last_notified if existing else 0
        if notified_at is not None:
            last_notified = int(notified_at)
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                INSERT INTO alert_state(code, target, active, last_value, first_seen, last_seen, last_notified)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(code, target) DO UPDATE SET
                    active=excluded.active, last_value=excluded.last_value,
                    first_seen=excluded.first_seen, last_seen=excluded.last_seen,
                    last_notified=excluded.last_notified
                """,
                (code, target, 1 if active else 0, (value or "")[:500], first_seen, now, last_notified),
            )
            await db.commit()
        return AlertStateRecord(
            code=code, target=target, active=1 if active else 0, last_value=(value or "")[:500],
            first_seen=first_seen, last_seen=now, last_notified=last_notified,
        )

