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

    async def delete(self, telegram_id: int):
        async with aiosqlite.connect(self.path) as db:
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
                "DELETE FROM server_group_members WHERE group_id = ?",
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
