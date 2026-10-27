"""Private bot-DB persistence for #947. No transport, jobs or runtime assembly."""
from contextlib import asynccontextmanager
import hashlib
from pathlib import Path

import aiosqlite

from db import Database
from db_migrations import CURRENT_SCHEMA_VERSION, MIGRATIONS


class CampaignUnavailable(RuntimeError):
    pass


class CampaignOutcomeUnknown(CampaignUnavailable):
    """A local commit may have succeeded; read back before any manual retry."""


class CampaignNotFound(RuntimeError):
    pass


class CampaignConflict(RuntimeError):
    pass


class CampaignLimit(RuntimeError):
    pass


PAGE_SIZE = 8
MAX_DRAFTS = 100
MAX_FROZEN_REVISIONS = 64
MAX_CANDIDATES = 1000
_DRAFT_COLUMNS = "id, owner_id, revision, payload_json, created_at, updated_at"
_REVISION_COLUMNS = "id, draft_id, owner_id, revision, payload_json, payload_sha256, created_at"


class CampaignStore:
    def __init__(self, db: Database):
        self._path = db.path

    @asynccontextmanager
    async def _connection(self, *, write=False):
        # Only the migration framework may create/upgrade the database.
        try:
            uri = Path(self._path).resolve().as_uri() + ("?mode=rw" if write else "?mode=ro")
            async with aiosqlite.connect(uri, uri=True, timeout=10) as conn:
                conn.row_factory = aiosqlite.Row
                await conn.execute("PRAGMA foreign_keys=ON")
                await conn.execute("BEGIN IMMEDIATE" if write else "BEGIN")
                try:
                    cur = await conn.execute(
                        "SELECT version,name,status FROM schema_migrations ORDER BY version LIMIT ?",
                        (CURRENT_SCHEMA_VERSION + 1,),
                    )
                    actual = [tuple(row) for row in await cur.fetchall()]
                    if actual != [(step.version, step.name, "success") for step in MIGRATIONS]:
                        raise CampaignUnavailable("Campaign schema unavailable")
                    yield conn
                    if write:
                        try:
                            await conn.commit()
                        except aiosqlite.Error:
                            raise CampaignOutcomeUnknown("Campaign mutation outcome unknown") from None
                except BaseException:
                    try:
                        await conn.rollback()
                    except aiosqlite.Error:
                        raise CampaignOutcomeUnknown("Campaign mutation outcome unknown") from None
                    raise
        except (aiosqlite.Error, OSError):
            raise CampaignUnavailable("Campaign storage unavailable") from None

    @staticmethod
    async def _groups_exist(conn, groups):
        if not groups:
            return
        placeholders = ",".join("?" for _ in groups)
        cur = await conn.execute(f"SELECT COUNT(*) FROM user_groups WHERE id IN ({placeholders})", groups)
        if int((await cur.fetchone())[0]) != len(groups):
            raise CampaignUnavailable("Campaign audience unavailable")

    @staticmethod
    async def _owned(conn, owner, draft_id):
        cur = await conn.execute(
            f"SELECT {_DRAFT_COLUMNS} FROM service_campaign_drafts WHERE id=? AND owner_id=?",
            (draft_id, owner),
        )
        row = await cur.fetchone()
        if row is None:
            raise CampaignNotFound("Campaign unavailable")
        return dict(row)

    async def create(self, owner, payload, groups, now):
        async with self._connection(write=True) as conn:
            await self._groups_exist(conn, groups)
            cur = await conn.execute("SELECT COUNT(*) FROM service_campaign_drafts WHERE owner_id=?", (owner,))
            if int((await cur.fetchone())[0]) >= MAX_DRAFTS:
                raise CampaignLimit("Campaign draft limit reached")
            cur = await conn.execute(
                "INSERT INTO service_campaign_drafts(owner_id,revision,payload_json,created_at,updated_at) "
                "VALUES (?,1,?,?,?)", (owner, payload, now, now),
            )
            return await self._owned(conn, owner, cur.lastrowid)

    async def get(self, owner, draft_id):
        async with self._connection() as conn:
            return await self._owned(conn, owner, draft_id)

    async def list_owned(self, owner, page):
        async with self._connection() as conn:
            cur = await conn.execute("SELECT COUNT(*) FROM service_campaign_drafts WHERE owner_id=?", (owner,))
            total = int((await cur.fetchone())[0])
            page = min(max(0, page), max(0, (total - 1) // PAGE_SIZE))
            cur = await conn.execute(
                f"SELECT {_DRAFT_COLUMNS} FROM service_campaign_drafts WHERE owner_id=? "
                "ORDER BY updated_at DESC, id DESC LIMIT ? OFFSET ?", (owner, PAGE_SIZE, page * PAGE_SIZE),
            )
            return page, total, tuple(dict(row) for row in await cur.fetchall())

    async def edit(self, owner, draft_id, expected_revision, payload, groups, now):
        async with self._connection(write=True) as conn:
            old = await self._owned(conn, owner, draft_id)
            if old["revision"] != expected_revision:
                raise CampaignConflict("Campaign revision changed")
            await self._groups_exist(conn, groups)
            await conn.execute(
                "UPDATE service_campaign_drafts SET revision=revision+1,payload_json=?,updated_at=? "
                "WHERE id=? AND owner_id=? AND revision=?",
                (payload, max(now, old["updated_at"]), draft_id, owner, expected_revision),
            )
            return await self._owned(conn, owner, draft_id)

    async def freeze(self, owner, draft_id, revision, validated_payload, now):
        async with self._connection(write=True) as conn:
            draft = await self._owned(conn, owner, draft_id)
            if draft["revision"] != revision or draft["payload_json"] != validated_payload:
                raise CampaignConflict("Campaign revision changed")
            cur = await conn.execute(
                f"SELECT {_REVISION_COLUMNS} FROM service_campaign_revisions "
                "WHERE draft_id=? AND owner_id=? AND revision=?", (draft_id, owner, revision),
            )
            row = await cur.fetchone()
            if row is not None:
                return dict(row)
            cur = await conn.execute("SELECT COUNT(*) FROM service_campaign_revisions WHERE draft_id=?", (draft_id,))
            if int((await cur.fetchone())[0]) >= MAX_FROZEN_REVISIONS:
                raise CampaignLimit("Campaign revision limit reached")
            digest = hashlib.sha256(validated_payload.encode("utf-8")).hexdigest()
            cur = await conn.execute(
                "INSERT INTO service_campaign_revisions(draft_id,owner_id,revision,payload_json,payload_sha256,created_at) "
                "VALUES (?,?,?,?,?,?)", (draft_id, owner, revision, validated_payload, digest, now),
            )
            cur = await conn.execute(f"SELECT {_REVISION_COLUMNS} FROM service_campaign_revisions WHERE id=?", (cur.lastrowid,))
            return dict(await cur.fetchone())

    async def get_revision(self, owner, revision_id):
        async with self._connection() as conn:
            cur = await conn.execute(
                "SELECT r.id,r.draft_id,r.owner_id,r.revision,r.payload_json,r.payload_sha256,r.created_at "
                "FROM service_campaign_revisions r JOIN service_campaign_drafts d ON d.id=r.draft_id "
                "WHERE r.id=? AND r.owner_id=? AND d.owner_id=r.owner_id", (revision_id, owner),
            )
            row = await cur.fetchone()
            if row is None:
                raise CampaignNotFound("Campaign unavailable")
            return dict(row)

    async def observe_private(self, actor, now):
        """Internal trusted-adapter call; never call from user-supplied IDs/import."""
        async with self._connection(write=True) as conn:
            cur = await conn.execute(
                """INSERT INTO service_campaign_contacts(telegram_id,first_seen_at,last_seen_at,source)
                SELECT telegram_id,?,?,'private_update' FROM users WHERE telegram_id=?
                ON CONFLICT(telegram_id) DO UPDATE SET
                    last_seen_at=MAX(service_campaign_contacts.last_seen_at,excluded.last_seen_at)""",
                (now, now, actor),
            )
            return cur.rowcount == 1

    async def estimate(self, owner, draft_id, revision, validated_payload, include, exclude):
        async with self._connection() as conn:
            draft = await self._owned(conn, owner, draft_id)
            if draft["revision"] != revision or draft["payload_json"] != validated_payload:
                raise CampaignConflict("Campaign revision changed")
            await self._groups_exist(conn, tuple(sorted(set(include) | set(exclude))))
            where = ["c.blocked_at=0"]
            params = []
            for group_ids, negate in ((include, False), (exclude, True)):
                if not group_ids:
                    continue
                marks = ",".join("?" for _ in group_ids)
                where.append(("NOT " if negate else "") + "EXISTS (SELECT 1 FROM user_group_members m "
                             f"WHERE m.telegram_id=c.telegram_id AND m.group_id IN ({marks}))")
                params.extend(group_ids)
            cur = await conn.execute(
                "SELECT COUNT(*) FROM (SELECT c.telegram_id FROM service_campaign_contacts c "
                "JOIN users u ON u.telegram_id=c.telegram_id WHERE " + " AND ".join(where) +
                " ORDER BY c.telegram_id LIMIT ?)", (*params, MAX_CANDIDATES + 1),
            )
            count = int((await cur.fetchone())[0])
            return min(count, MAX_CANDIDATES), count > MAX_CANDIDATES
