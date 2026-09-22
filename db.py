import time
from dataclasses import dataclass

import aiosqlite


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


@dataclass
class ServerGroupRecord:
    id: int
    name: str
    description: str
    created_at: int


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


@dataclass
class InboundTemplateRecord:
    id: int
    name: str
    source_inbound_id: int
    protocol: str
    payload_json: str
    created_at: int
    updated_at: int


class Database:
    def __init__(self, path: str):
        self.path = path

    async def init(self):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id INTEGER PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    sub_id TEXT NOT NULL UNIQUE,
                    expiry_time INTEGER NOT NULL,
                    created_at INTEGER NOT NULL
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS server_groups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT COLLATE NOCASE NOT NULL UNIQUE,
                    description TEXT NOT NULL DEFAULT '',
                    created_at INTEGER NOT NULL
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS server_group_members (
                    group_id INTEGER NOT NULL,
                    member_key TEXT NOT NULL,
                    PRIMARY KEY(group_id, member_key)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS server_group_provisioning (
                    group_id INTEGER PRIMARY KEY,
                    inbound_mode TEXT NOT NULL DEFAULT 'all_managed',
                    updated_at INTEGER NOT NULL
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS server_group_inbounds (
                    group_id INTEGER NOT NULL,
                    inbound_id INTEGER NOT NULL,
                    PRIMARY KEY(group_id, inbound_id)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS plans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT COLLATE NOCASE NOT NULL UNIQUE,
                    duration_days INTEGER NOT NULL,
                    traffic_gb INTEGER NOT NULL,
                    ip_limit INTEGER NOT NULL,
                    price_minor INTEGER NOT NULL DEFAULT 0,
                    currency TEXT NOT NULL DEFAULT 'RUB',
                    server_group_id INTEGER,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at INTEGER NOT NULL
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS hosts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    label TEXT NOT NULL,
                    hostname TEXT NOT NULL,
                    role TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    created_at INTEGER NOT NULL,
                    UNIQUE(hostname, role)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    actor_id INTEGER NOT NULL,
                    actor_username TEXT NOT NULL DEFAULT '',
                    action TEXT NOT NULL,
                    target_type TEXT NOT NULL DEFAULT '',
                    target_id TEXT NOT NULL DEFAULT '',
                    details TEXT NOT NULL DEFAULT '',
                    success INTEGER NOT NULL DEFAULT 1,
                    created_at INTEGER NOT NULL
                )
            """)
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON audit_log(created_at DESC)"
            )
            await db.execute("""
                CREATE TABLE IF NOT EXISTS job_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    trigger TEXT NOT NULL,
                    actor_id INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'running',
                    started_at INTEGER NOT NULL,
                    finished_at INTEGER NOT NULL DEFAULT 0,
                    duration_ms INTEGER NOT NULL DEFAULT 0,
                    details TEXT NOT NULL DEFAULT ''
                )
            """)
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_job_runs_name_started ON job_runs(name, started_at DESC)"
            )
            await db.execute("""
                CREATE TABLE IF NOT EXISTS payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER NOT NULL,
                    plan_id INTEGER,
                    amount_minor INTEGER NOT NULL,
                    currency TEXT NOT NULL DEFAULT 'RUB',
                    status TEXT NOT NULL DEFAULT 'pending',
                    provider TEXT NOT NULL DEFAULT 'manual',
                    external_id TEXT NOT NULL DEFAULT '',
                    note TEXT NOT NULL DEFAULT '',
                    created_by INTEGER NOT NULL DEFAULT 0,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    paid_at INTEGER NOT NULL DEFAULT 0
                )
            """)
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_payments_user_created ON payments(telegram_id, created_at DESC)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_payments_status_created ON payments(status, created_at DESC)"
            )
            await db.execute("""
                CREATE TABLE IF NOT EXISTS promo_codes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT COLLATE NOCASE NOT NULL UNIQUE,
                    discount_type TEXT NOT NULL,
                    value INTEGER NOT NULL,
                    currency TEXT NOT NULL DEFAULT 'RUB',
                    plan_id INTEGER,
                    max_uses INTEGER NOT NULL DEFAULT 0,
                    uses_count INTEGER NOT NULL DEFAULT 0,
                    expires_at INTEGER NOT NULL DEFAULT 0,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at INTEGER NOT NULL
                )
            """)
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_promo_active_code ON promo_codes(active, code COLLATE NOCASE)"
            )
            await db.execute("""
                CREATE TABLE IF NOT EXISTS administrators (
                    telegram_id INTEGER PRIMARY KEY,
                    role TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    added_by INTEGER NOT NULL DEFAULT 0,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS runtime_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_by INTEGER NOT NULL DEFAULT 0,
                    updated_at INTEGER NOT NULL
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_profiles (
                    telegram_id INTEGER PRIMARY KEY,
                    plan_id INTEGER,
                    server_group_id INTEGER,
                    note TEXT NOT NULL DEFAULT '',
                    updated_at INTEGER NOT NULL
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS inbound_templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT COLLATE NOCASE NOT NULL UNIQUE,
                    source_inbound_id INTEGER NOT NULL DEFAULT 0,
                    protocol TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                )
            """)
            await db.commit()

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
        preserve_unspecified: bool = True,
    ) -> None:
        current = await self.get_user_profile(int(telegram_id)) if preserve_unspecified else None
        plan_value = current.plan_id if current and plan_id is None else plan_id
        group_value = current.server_group_id if current and server_group_id is None else server_group_id
        note_value = current.note if current and note is None else (note or "")
        now = int(time.time())
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                INSERT INTO user_profiles(telegram_id, plan_id, server_group_id, note, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(telegram_id) DO UPDATE SET
                    plan_id=excluded.plan_id,
                    server_group_id=excluded.server_group_id,
                    note=excluded.note,
                    updated_at=excluded.updated_at
                """,
                (int(telegram_id), plan_value, group_value, note_value[:1000], now),
            )
            await db.commit()

    async def set_user_plan(self, telegram_id: int, plan_id: int | None) -> None:
        current = await self.get_user_profile(int(telegram_id))
        await self.upsert_user_profile(
            int(telegram_id),
            plan_id=plan_id,
            server_group_id=current.server_group_id if current else None,
            note=current.note if current else "",
            preserve_unspecified=False,
        )

    async def set_user_server_group(self, telegram_id: int, group_id: int | None) -> None:
        current = await self.get_user_profile(int(telegram_id))
        await self.upsert_user_profile(
            int(telegram_id),
            plan_id=current.plan_id if current else None,
            server_group_id=group_id,
            note=current.note if current else "",
            preserve_unspecified=False,
        )

    async def set_user_note(self, telegram_id: int, note: str) -> None:
        current = await self.get_user_profile(int(telegram_id))
        await self.upsert_user_profile(
            int(telegram_id),
            plan_id=current.plan_id if current else None,
            server_group_id=current.server_group_id if current else None,
            note=note,
            preserve_unspecified=False,
        )

    async def delete(self, telegram_id: int):
        async with aiosqlite.connect(self.path) as db:
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
    ) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                """
                INSERT INTO plans(
                    name, duration_days, traffic_gb, ip_limit,
                    price_minor, currency, server_group_id, active, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
                """,
                (
                    name.strip(), int(duration_days), int(traffic_gb), int(ip_limit),
                    int(price_minor), currency.strip().upper(), server_group_id,
                    int(time.time()),
                ),
            )
            await db.commit()
            return int(cur.lastrowid)

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

    async def count_audit(self) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT COUNT(*) FROM audit_log")
            row = await cur.fetchone()
            return int(row[0] if row else 0)

    # --- Job runs ------------------------------------------------------

    async def start_job_run(self, *, name: str, trigger: str, actor_id: int = 0) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                """
                INSERT INTO job_runs(name, trigger, actor_id, status, started_at)
                VALUES (?, ?, ?, 'running', ?)
                """,
                ((name or "")[:96], (trigger or "")[:32], int(actor_id), int(time.time())),
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

