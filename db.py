import aiosqlite
from dataclasses import dataclass

@dataclass
class UserRecord:
    telegram_id: int
    email: str
    sub_id: str
    expiry_time: int
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
            await db.commit()

    async def get(self, telegram_id: int) -> UserRecord | None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM users WHERE telegram_id = ?",
                (telegram_id,),
            )
            row = await cur.fetchone()
            return UserRecord(**dict(row)) if row else None

    async def put(self, rec: UserRecord):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("""
                INSERT INTO users(telegram_id, email, sub_id, expiry_time, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(telegram_id) DO UPDATE SET
                    email = excluded.email,
                    sub_id = excluded.sub_id,
                    expiry_time = excluded.expiry_time,
                    created_at = excluded.created_at
            """, (
                rec.telegram_id,
                rec.email,
                rec.sub_id,
                rec.expiry_time,
                rec.created_at,
            ))
            await db.commit()

    async def delete(self, telegram_id: int):
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "DELETE FROM users WHERE telegram_id = ?",
                (telegram_id,),
            )
            await db.commit()
