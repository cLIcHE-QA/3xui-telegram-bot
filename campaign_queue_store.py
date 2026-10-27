"""Private, bounded campaign queue DAO. No transport or runtime registration."""
import hashlib
from contextlib import asynccontextmanager
import time

from campaign_store import CampaignConflict, CampaignLimit, CampaignNotFound, CampaignStore, CampaignUnavailable


MAX_RECIPIENTS = 1000
MAX_JOBS_PER_OWNER = 100
LEASE_SECONDS = 30
SEND_INTERVAL = 2
START_GRACE_SECONDS = 60
MAX_SQL_OPS = 10_000_000
MAX_SQL_SECONDS = 5
_FINAL = frozenset({"cancelled", "completed", "partial"})


class CampaignQueueStore:
    def __init__(self, db, *, clock=None):
        self._foundation = CampaignStore(db)
        self._clock_source = clock

    @asynccontextmanager
    async def _connection(self, *, write=False):
        async with self._foundation._connection(write=write) as conn:
            deadline = time.monotonic() + MAX_SQL_SECONDS
            operations = 0
            def progress():
                nonlocal operations
                operations += 1000
                return int(operations > MAX_SQL_OPS or time.monotonic() >= deadline)
            await conn.set_progress_handler(progress, 1000)
            try:
                yield conn
            finally:
                # Disable before the outer transaction's commit/rollback.
                await conn.set_progress_handler(None, 0)

    async def _clock(self, conn, now):
        cur = await conn.execute("SELECT * FROM service_campaign_control WHERE id=1")
        row = await cur.fetchone()
        now = self._clock_source() if self._clock_source else now
        if type(now) is not int or not 0 < now <= 2**63 - 1:
            raise CampaignUnavailable("Campaign clock unavailable")
        if row is None or now < row["clock_seen"]:
            raise CampaignUnavailable("Campaign clock unavailable")
        await conn.execute("UPDATE service_campaign_control SET clock_seen=? WHERE id=1", (now,))
        return dict(row), now

    @staticmethod
    async def _owned(conn, owner, job_id):
        cur = await conn.execute("SELECT * FROM service_campaign_jobs WHERE id=? AND owner_id=?", (job_id, owner))
        row = await cur.fetchone()
        if row is None:
            raise CampaignNotFound("Campaign job unavailable")
        return dict(row)

    @staticmethod
    async def _view(conn, job):
        cur = await conn.execute("SELECT state,COUNT(*) AS count FROM service_campaign_recipients "
                                 "WHERE job_id=? GROUP BY state", (job["id"],))
        return dict(job), {row["state"]: row["count"] for row in await cur.fetchall()}

    @staticmethod
    def _audience(include, exclude):
        parts = ["c.blocked_at=0"]
        params = []
        for groups, negate in ((include, False), (exclude, True)):
            if groups:
                marks = ",".join("?" for _ in groups)
                parts.append(("NOT " if negate else "") + "EXISTS (SELECT 1 FROM user_group_members m "
                             f"WHERE m.telegram_id=c.telegram_id AND m.group_id IN ({marks}))")
                params.extend(groups)
        return " AND ".join(parts), params

    async def get(self, owner, job_id):
        async with self._connection() as conn:
            return await self._view(conn, await self._owned(conn, owner, job_id))

    async def list_owned(self, owner, page):
        async with self._connection() as conn:
            cur = await conn.execute("SELECT COUNT(*) FROM service_campaign_jobs WHERE owner_id=?", (owner,))
            total = int((await cur.fetchone())[0])
            page = min(max(0, page), max(0, (total - 1) // 8))
            cur = await conn.execute("SELECT * FROM service_campaign_jobs WHERE owner_id=? "
                                     "ORDER BY id DESC LIMIT 8 OFFSET ?", (owner, page * 8))
            rows = await cur.fetchall()
            return page, total, tuple([await self._view(conn, dict(row)) for row in rows])

    async def prepare(self, owner, operation, revision, payload, digest, schedule, include, exclude, now):
        async with self._connection(write=True) as conn:
            _, now = await self._clock(conn, now)
            cur = await conn.execute("SELECT * FROM service_campaign_jobs WHERE owner_id=? AND operation_id=?",
                                     (owner, operation))
            existing = await cur.fetchone()
            if existing is not None:
                if ((existing["revision_id"], existing["payload_sha256"], existing["due_at"],
                     existing["timezone"], existing["local_time"]) !=
                        (revision, digest, schedule.due_at, schedule.timezone, schedule.local_time)):
                    raise CampaignConflict("Campaign operation changed")
                return await self._view(conn, dict(existing))
            if schedule.due_at <= now:
                raise CampaignConflict("Campaign schedule unavailable")
            cur = await conn.execute("SELECT r.payload_json,r.payload_sha256 FROM service_campaign_revisions r "
                                     "JOIN service_campaign_drafts d ON d.id=r.draft_id "
                                     "WHERE r.id=? AND r.owner_id=? AND d.owner_id=r.owner_id", (revision, owner))
            row = await cur.fetchone()
            if row is None or (row["payload_json"], row["payload_sha256"]) != (payload, digest):
                raise CampaignConflict("Campaign revision changed")
            await self._foundation._groups_exist(conn, tuple(sorted(set(include) | set(exclude))))
            cur = await conn.execute("SELECT COUNT(*) FROM service_campaign_jobs WHERE owner_id=?", (owner,))
            if int((await cur.fetchone())[0]) >= MAX_JOBS_PER_OWNER:
                raise CampaignLimit("Campaign job limit reached")
            cur = await conn.execute(
                "INSERT INTO service_campaign_jobs(owner_id,operation_id,revision_id,payload_sha256,due_at,"
                "timezone,local_time,ready_at,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (owner, operation, revision, digest, schedule.due_at, schedule.timezone, schedule.local_time,
                 schedule.due_at, now, now),
            )
            job_id = cur.lastrowid
            where, params = self._audience(include, exclude)
            await conn.execute(
                "INSERT INTO service_campaign_recipients(job_id,telegram_id,proof_generation,updated_at) "
                "SELECT ?,c.telegram_id,g.generation,? FROM service_campaign_contacts c "
                "JOIN users u ON u.telegram_id=c.telegram_id "
                "JOIN service_campaign_contact_generations g ON g.telegram_id=c.telegram_id WHERE "
                + where + " ORDER BY c.telegram_id LIMIT ?", (job_id, now, *params, MAX_RECIPIENTS + 1),
            )
            cur = await conn.execute("SELECT COUNT(*) FROM service_campaign_recipients WHERE job_id=?", (job_id,))
            count = int((await cur.fetchone())[0])
            if not 0 < count <= MAX_RECIPIENTS:
                raise CampaignLimit("Campaign audience unavailable")
            fingerprint = hashlib.sha256(f"{digest}|{schedule.due_at}|{schedule.timezone}|{schedule.local_time}\n".encode())
            cur = await conn.execute("SELECT telegram_id,proof_generation FROM service_campaign_recipients "
                                     "WHERE job_id=? ORDER BY telegram_id", (job_id,))
            while batch := await cur.fetchmany(100):
                for recipient in batch:
                    fingerprint.update(f"{recipient['telegram_id']}:{recipient['proof_generation']}\n".encode())
            await conn.execute("UPDATE service_campaign_jobs SET snapshot_sealed=1,snapshot_sha256=? WHERE id=?",
                               (fingerprint.hexdigest(), job_id))
            return await self._view(conn, await self._owned(conn, owner, job_id))

    async def confirm(self, owner, job_id, snapshot, now):
        async with self._connection(write=True) as conn:
            _, now = await self._clock(conn, now)
            job = await self._owned(conn, owner, job_id)
            if not job["snapshot_sealed"] or snapshot != job["snapshot_sha256"]:
                raise CampaignConflict("Campaign snapshot changed")
            if job["state"] in {"scheduled", "running"}:
                return await self._view(conn, job)
            if job["state"] != "draft" or job["due_at"] <= now:
                raise CampaignConflict("Campaign schedule unavailable")
            await conn.execute("UPDATE service_campaign_jobs SET state='scheduled',updated_at=? WHERE id=?", (now, job_id))
            return await self._view(conn, await self._owned(conn, owner, job_id))

    @staticmethod
    async def _clear_lease(conn):
        await conn.execute("UPDATE service_campaign_control SET lease_job=NULL,lease_token=NULL,lease_until=0 WHERE id=1")

    @staticmethod
    async def _unknown_intents(conn, job_id, now):
        await conn.execute("UPDATE service_campaign_attempts SET state='unknown',updated_at=? "
                           "WHERE job_id=? AND state='intent'", (now, job_id))
        await conn.execute("UPDATE service_campaign_recipients SET state='unknown',result_code='unknown',updated_at=? "
                           "WHERE job_id=? AND state='intent'", (now, job_id))

    async def control(self, owner, job_id, action, now, ready_at=None):
        async with self._connection(write=True) as conn:
            control, now = await self._clock(conn, now)
            job = await self._owned(conn, owner, job_id)
            if action == "resume":
                if job["state"] != "paused" or ready_at is None or ready_at <= now:
                    raise CampaignConflict("Campaign resume unavailable")
                cur = await conn.execute("SELECT 1 FROM service_campaign_attempts WHERE job_id=? AND state='intent' LIMIT 1", (job_id,))
                if control["lease_job"] == job_id or await cur.fetchone():
                    raise CampaignConflict("Campaign outcome unresolved")
                await conn.execute("UPDATE service_campaign_jobs SET state='scheduled',ready_at=?,updated_at=? WHERE id=?",
                                   (ready_at, now, job_id))
            elif action in {"pause", "cancel"}:
                if job["state"] in _FINAL:
                    return await self._view(conn, job)
                if action == "pause" and job["state"] == "draft":
                    raise CampaignConflict("Campaign pause unavailable")
                target = "paused" if action == "pause" else "cancelled"
                await conn.execute("UPDATE service_campaign_jobs SET state=?,updated_at=? WHERE id=?", (target, now, job_id))
                if action == "cancel":
                    await conn.execute("UPDATE service_campaign_recipients SET state='cancelled',result_code='cancelled',updated_at=? "
                                       "WHERE job_id=? AND state='pending'", (now, job_id))
                cur = await conn.execute("SELECT 1 FROM service_campaign_attempts WHERE job_id=? AND state='intent' LIMIT 1", (job_id,))
                if control["lease_job"] == job_id and await cur.fetchone() is None:
                    await self._clear_lease(conn)
            else:
                raise CampaignConflict("Campaign control unavailable")
            return await self._view(conn, await self._owned(conn, owner, job_id))

    async def _recover(self, conn, control, now):
        if control["lease_job"] is not None and control["lease_until"] <= now:
            await self._unknown_intents(conn, control["lease_job"], now)
            await conn.execute("UPDATE service_campaign_jobs SET state='paused',updated_at=? "
                               "WHERE id=? AND state='running'", (now, control["lease_job"]))
            await self._clear_lease(conn)
            control.update(lease_job=None, lease_token=None, lease_until=0)
        # A missing lease never authorizes replay of an interrupted intent.
        if control["lease_job"] is None:
            cur = await conn.execute("SELECT id FROM service_campaign_jobs WHERE state='running' ORDER BY id LIMIT ?",
                                     (MAX_JOBS_PER_OWNER + 1,))
            for row in await cur.fetchall():
                await self._unknown_intents(conn, row["id"], now)
                await conn.execute("UPDATE service_campaign_jobs SET state='paused',updated_at=? WHERE id=?", (now, row["id"]))

    @staticmethod
    async def _content(conn, job_id):
        cur = await conn.execute("SELECT j.*,r.payload_json FROM service_campaign_jobs j "
                                 "JOIN service_campaign_revisions r ON r.id=j.revision_id AND r.owner_id=j.owner_id "
                                 "WHERE j.id=? AND r.payload_sha256=j.payload_sha256", (job_id,))
        row = await cur.fetchone()
        if row is None:
            raise CampaignUnavailable("Campaign content unavailable")
        return dict(row)

    async def claim(self, token, now):
        async with self._connection(write=True) as conn:
            control, now = await self._clock(conn, now)
            await self._recover(conn, control, now)
            if control["lease_job"] is not None:
                if control["lease_token"] != token:
                    return None
                job = await self._content(conn, control["lease_job"])
                if job["state"] != "running":
                    return None
                await conn.execute("UPDATE service_campaign_control SET lease_until=? WHERE id=1", (now + LEASE_SECONDS,))
                return job if control["next_send_at"] <= now else None
            if control["next_send_at"] > now:
                return None
            cur = await conn.execute("SELECT id FROM service_campaign_jobs WHERE state='scheduled' AND ready_at<=? "
                                     "ORDER BY ready_at,id LIMIT 1", (now,))
            row = await cur.fetchone()
            if row is None:
                return None
            job = await self._content(conn, row["id"])
            if not job["started_at"] and now - job["ready_at"] > START_GRACE_SECONDS:
                await conn.execute("UPDATE service_campaign_jobs SET state='paused',updated_at=? WHERE id=?", (now, job["id"]))
                return None
            await conn.execute("UPDATE service_campaign_control SET lease_job=?,lease_token=?,lease_until=? WHERE id=1",
                               (job["id"], token, now + LEASE_SECONDS))
            await conn.execute("UPDATE service_campaign_jobs SET state='running',updated_at=? WHERE id=?", (now, job["id"]))
            job["state"] = "running"
            return job

    async def _eligible(self, conn, recipient, include, exclude):
        await self._foundation._groups_exist(conn, tuple(sorted(set(include) | set(exclude))))
        cur = await conn.execute("SELECT 1 FROM service_campaign_contacts c JOIN users u ON u.telegram_id=c.telegram_id "
                                 "JOIN service_campaign_contact_generations g ON g.telegram_id=c.telegram_id "
                                 "WHERE c.telegram_id=? AND g.generation=? AND c.blocked_at=0",
                                 (recipient["telegram_id"], recipient["proof_generation"]))
        if await cur.fetchone() is None:
            return False, "user_unavailable"
        where, params = self._audience(include, exclude)
        cur = await conn.execute("SELECT 1 FROM service_campaign_contacts c WHERE c.telegram_id=? AND " + where,
                                 (recipient["telegram_id"], *params))
        return (True, "") if await cur.fetchone() else (False, "group_changed")

    async def _settle(self, conn, job, now, *, pause=False, retry_at=None):
        cur = await conn.execute("SELECT COUNT(*) AS total, "
                                 "COALESCE(SUM(state IN ('pending','intent')),0) AS remaining, "
                                 "COALESCE(SUM(state='sent'),0) AS sent "
                                 "FROM service_campaign_recipients WHERE job_id=?", (job["id"],))
        counts = await cur.fetchone()
        state = job["state"]
        if state in {"cancelled", "paused"}:
            await self._clear_lease(conn)
        elif pause:
            state = "paused"
            await self._clear_lease(conn)
        elif not counts["remaining"]:
            state = "completed" if counts["total"] and counts["sent"] == counts["total"] else "partial"
            await self._clear_lease(conn)
        elif retry_at is not None:
            state = "scheduled"
            await conn.execute("UPDATE service_campaign_jobs SET ready_at=? WHERE id=?", (retry_at, job["id"]))
            await self._clear_lease(conn)
        else:
            await conn.execute("UPDATE service_campaign_control SET lease_until=? WHERE id=1", (now + LEASE_SECONDS,))
        await conn.execute("UPDATE service_campaign_jobs SET state=?,updated_at=? WHERE id=?", (state, now, job["id"]))

    async def begin_intent(self, token, job_id, include, exclude, now):
        async with self._connection(write=True) as conn:
            control, now = await self._clock(conn, now)
            await self._recover(conn, control, now)
            if (control["lease_job"] != job_id or control["lease_token"] != token
                    or control["lease_until"] <= now or control["next_send_at"] > now):
                return None
            job = await self._content(conn, job_id)
            if job["state"] != "running":
                return None
            cur = await conn.execute("SELECT * FROM service_campaign_recipients WHERE job_id=? AND state='pending' "
                                     "AND next_at<=? ORDER BY id LIMIT 1", (job_id, now))
            row = await cur.fetchone()
            if row is None:
                cur = await conn.execute("SELECT MIN(next_at) FROM service_campaign_recipients WHERE job_id=? AND state='pending'", (job_id,))
                next_at = (await cur.fetchone())[0]
                cur = await conn.execute("SELECT 1 FROM service_campaign_attempts WHERE job_id=? AND state='intent' LIMIT 1", (job_id,))
                if await cur.fetchone() is None:
                    await self._settle(conn, job, now, retry_at=next_at)
                return None
            recipient = dict(row)
            allowed, reason = await self._eligible(conn, recipient, include, exclude)
            if not allowed or recipient["attempt_count"] >= 3:
                state = "skipped" if not allowed else "failed"
                code = reason if not allowed else "retry_exhausted"
                await conn.execute("UPDATE service_campaign_recipients SET state=?,result_code=?,updated_at=? WHERE id=?",
                                   (state, code, now, recipient["id"]))
                await self._settle(conn, job, now)
                return None
            number = recipient["attempt_count"] + 1
            cur = await conn.execute("INSERT INTO service_campaign_attempts(job_id,recipient_id,attempt_no,lease_token,started_at,updated_at) "
                                     "VALUES (?,?,?,?,?,?)", (job_id, recipient["id"], number, token, now, now))
            attempt_id = cur.lastrowid
            await conn.execute("UPDATE service_campaign_recipients SET state='intent',attempt_count=?,updated_at=? WHERE id=?",
                               (number, now, recipient["id"]))
            await conn.execute("UPDATE service_campaign_control SET next_send_at=?,lease_until=? WHERE id=1",
                               (now + SEND_INTERVAL, now + LEASE_SECONDS))
            await conn.execute("UPDATE service_campaign_jobs SET started_at=CASE WHEN started_at=0 THEN ? ELSE started_at END,"
                               "updated_at=? WHERE id=?", (now, now, job_id))
            return {"id": attempt_id, "lease_until": now + LEASE_SECONDS, "job_id": job_id, "recipient_id": recipient["id"], "attempt_no": number,
                    "telegram_id": recipient["telegram_id"], "proof_generation": recipient["proof_generation"], "job": job}

    async def dispatch_status(self, token, attempt_id, include, exclude, now):
        async with self._connection() as conn:
            cur = await conn.execute("SELECT * FROM service_campaign_control WHERE id=1")
            control = await cur.fetchone()
            now = self._clock_source() if self._clock_source else now
            if (not control or control["lease_token"] != token or control["lease_until"] <= now
                    or now < control["clock_seen"]):
                return False, "unknown"
            cur = await conn.execute("SELECT a.job_id,j.state AS job_state,r.* FROM service_campaign_attempts a "
                                     "JOIN service_campaign_jobs j ON j.id=a.job_id "
                                     "JOIN service_campaign_recipients r ON r.id=a.recipient_id "
                                     "WHERE a.id=? AND a.lease_token=? AND a.state='intent' AND r.state='intent'",
                                     (attempt_id, token))
            row = await cur.fetchone()
            if row is None or row["job_id"] != control["lease_job"]:
                return False, "unknown"
            if row["job_state"] != "running":
                return False, "cancelled"
            return await self._eligible(conn, dict(row), include, exclude)

    async def finish(self, token, attempt_id, kind, now, *, retry_after=0, reason=""):
        async with self._connection(write=True) as conn:
            control, now = await self._clock(conn, now)
            await self._recover(conn, control, now)
            if control["lease_token"] != token or control["lease_until"] <= now:
                return None
            cur = await conn.execute("SELECT a.*,r.telegram_id,r.proof_generation,r.state AS recipient_state "
                                     "FROM service_campaign_attempts a JOIN service_campaign_recipients r ON r.id=a.recipient_id "
                                     "WHERE a.id=? AND a.job_id=? AND a.lease_token=?",
                                     (attempt_id, control["lease_job"], token))
            row = await cur.fetchone()
            if row is None:
                return None
            attempt = dict(row)
            job = await self._content(conn, attempt["job_id"])
            if attempt["state"] != "intent":
                return await self._view(conn, job)
            if kind not in {"sent", "rate_limited", "unavailable", "unknown", "not_sent"}:
                kind = "unknown"
            if kind == "rate_limited" and (type(retry_after) is not int or not 1 <= retry_after <= 3600):
                kind = "unknown"
            retry_after = retry_after if kind == "rate_limited" else 0
            state, code, next_at, pause, retry_at = kind, kind, 0, False, None
            if kind == "unknown":
                pause = True
            elif kind == "unavailable":
                code = "blocked" if reason == "blocked" else "user_unavailable"
                if code == "blocked":
                    await conn.execute("UPDATE service_campaign_contacts SET blocked_at=MAX(blocked_at,?) WHERE telegram_id=? "
                                       "AND EXISTS (SELECT 1 FROM service_campaign_contact_generations g "
                                       "WHERE g.telegram_id=service_campaign_contacts.telegram_id AND g.generation=?)",
                                       (now, attempt["telegram_id"], attempt["proof_generation"]))
            elif kind == "not_sent":
                code = reason if reason in {"policy_denied", "recipient_denied", "user_unavailable", "group_changed", "cancelled"} else "policy_denied"
                pause = code in {"policy_denied", "cancelled"}
                if job["state"] == "cancelled":
                    state, code = "cancelled", "cancelled"
                else:
                    state = "pending" if pause else "skipped"
            elif kind == "rate_limited":
                delay = max(retry_after, min(3600, SEND_INTERVAL * 2 ** (attempt["attempt_no"] - 1)))
                await conn.execute("UPDATE service_campaign_control SET next_send_at=MAX(next_send_at,?) WHERE id=1", (now + delay,))
                if job["state"] == "cancelled":
                    state, code = "cancelled", "cancelled"
                elif attempt["attempt_no"] >= 3:
                    state, code = "failed", "retry_exhausted"
                else:
                    state, code, next_at = "pending", "rate_limited", now + delay
                    retry_at = next_at
            await conn.execute("UPDATE service_campaign_attempts SET state=?,retry_after=?,updated_at=? WHERE id=? AND state='intent'",
                               (kind, retry_after, now, attempt_id))
            await conn.execute("UPDATE service_campaign_recipients SET state=?,result_code=?,next_at=?,updated_at=? "
                               "WHERE id=? AND state='intent'", (state, code, next_at, now, attempt["recipient_id"]))
            await self._settle(conn, job, now, pause=pause, retry_at=retry_at)
            return await self._view(conn, await self._owned(conn, job["owner_id"], job["id"]))

    async def suspend(self, token, now):
        async with self._connection(write=True) as conn:
            control, now = await self._clock(conn, now)
            await self._recover(conn, control, now)
            if control["lease_token"] != token:
                return False
            await self._unknown_intents(conn, control["lease_job"], now)
            await conn.execute("UPDATE service_campaign_jobs SET state='paused',updated_at=? "
                               "WHERE id=? AND state='running'", (now, control["lease_job"]))
            await self._clear_lease(conn)
            return True
