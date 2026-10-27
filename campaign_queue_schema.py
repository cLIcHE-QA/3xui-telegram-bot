"""Static additive schema for #948; only the migration framework applies it."""
import re


QUEUE_SCHEMA = {
    "service_campaign_contact_generations": """CREATE TABLE service_campaign_contact_generations (
        telegram_id INTEGER PRIMARY KEY REFERENCES service_campaign_contacts(telegram_id) ON DELETE CASCADE,
        generation TEXT NOT NULL CHECK(length(generation)=32 AND generation NOT GLOB '*[^0-9a-f]*')
    )""",
    "service_campaign_contact_created": """CREATE TRIGGER service_campaign_contact_created
        AFTER INSERT ON service_campaign_contacts BEGIN
            INSERT INTO service_campaign_contact_generations(telegram_id,generation)
            VALUES (NEW.telegram_id,lower(hex(randomblob(16))));
        END""",
    "service_campaign_contact_deleted": """CREATE TRIGGER service_campaign_contact_deleted
        AFTER DELETE ON service_campaign_contacts BEGIN
            DELETE FROM service_campaign_contact_generations WHERE telegram_id=OLD.telegram_id;
        END""",
    "service_campaign_generation_identity": """CREATE TRIGGER service_campaign_generation_identity
        BEFORE UPDATE ON service_campaign_contact_generations
        WHEN NEW.telegram_id IS NOT OLD.telegram_id OR NEW.generation IS NOT OLD.generation
        BEGIN SELECT RAISE(ABORT,'Campaign proof identity is immutable'); END""",
    "service_campaign_jobs": """CREATE TABLE service_campaign_jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id INTEGER NOT NULL CHECK(typeof(owner_id)='integer' AND owner_id>0),
        operation_id TEXT NOT NULL CHECK(length(operation_id)=36),
        revision_id INTEGER NOT NULL REFERENCES service_campaign_revisions(id),
        payload_sha256 TEXT NOT NULL CHECK(length(payload_sha256)=64 AND payload_sha256 NOT GLOB '*[^0-9a-f]*'),
        due_at INTEGER NOT NULL CHECK(typeof(due_at)='integer' AND due_at>0),
        timezone TEXT NOT NULL CHECK(length(timezone) BETWEEN 1 AND 100),
        local_time TEXT NOT NULL CHECK(length(local_time)=16),
        snapshot_sealed INTEGER NOT NULL DEFAULT 0 CHECK(snapshot_sealed IN (0,1)),
        snapshot_sha256 TEXT NOT NULL DEFAULT '' CHECK(
            (snapshot_sealed=0 AND snapshot_sha256='') OR
            (snapshot_sealed=1 AND length(snapshot_sha256)=64 AND snapshot_sha256 NOT GLOB '*[^0-9a-f]*')),
        state TEXT NOT NULL DEFAULT 'draft' CHECK(state IN
            ('draft','scheduled','running','paused','cancelled','completed','partial')),
        ready_at INTEGER NOT NULL CHECK(typeof(ready_at)='integer' AND ready_at>0),
        started_at INTEGER NOT NULL DEFAULT 0 CHECK(typeof(started_at)='integer' AND started_at>=0),
        created_at INTEGER NOT NULL CHECK(typeof(created_at)='integer' AND created_at>0),
        updated_at INTEGER NOT NULL CHECK(typeof(updated_at)='integer' AND updated_at>=created_at),
        UNIQUE(owner_id,operation_id)
    )""",
    "service_campaign_recipients": """CREATE TABLE service_campaign_recipients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL REFERENCES service_campaign_jobs(id),
        telegram_id INTEGER NOT NULL CHECK(typeof(telegram_id)='integer' AND telegram_id>0),
        proof_generation TEXT NOT NULL CHECK(length(proof_generation)=32 AND proof_generation NOT GLOB '*[^0-9a-f]*'),
        state TEXT NOT NULL DEFAULT 'pending' CHECK(state IN
            ('pending','intent','sent','unavailable','unknown','failed','cancelled','skipped')),
        next_at INTEGER NOT NULL DEFAULT 0 CHECK(typeof(next_at)='integer' AND next_at>=0),
        attempt_count INTEGER NOT NULL DEFAULT 0 CHECK(attempt_count BETWEEN 0 AND 3),
        result_code TEXT NOT NULL DEFAULT '' CHECK(result_code IN
            ('','sent','rate_limited','blocked','unknown','policy_denied','user_unavailable',
             'group_changed','cancelled','retry_exhausted','recipient_denied')),
        updated_at INTEGER NOT NULL CHECK(typeof(updated_at)='integer' AND updated_at>0),
        UNIQUE(job_id,telegram_id)
    )""",
    "service_campaign_attempts": """CREATE TABLE service_campaign_attempts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL REFERENCES service_campaign_jobs(id),
        recipient_id INTEGER NOT NULL REFERENCES service_campaign_recipients(id),
        attempt_no INTEGER NOT NULL CHECK(attempt_no BETWEEN 1 AND 3),
        lease_token TEXT NOT NULL CHECK(length(lease_token)=32 AND lease_token NOT GLOB '*[^0-9a-f]*'),
        state TEXT NOT NULL DEFAULT 'intent' CHECK(state IN
            ('intent','sent','rate_limited','unavailable','unknown','not_sent')),
        started_at INTEGER NOT NULL CHECK(typeof(started_at)='integer' AND started_at>0),
        updated_at INTEGER NOT NULL CHECK(typeof(updated_at)='integer' AND updated_at>=started_at),
        retry_after INTEGER NOT NULL DEFAULT 0 CHECK(retry_after BETWEEN 0 AND 3600),
        UNIQUE(recipient_id,attempt_no)
    )""",
    "service_campaign_control": """CREATE TABLE service_campaign_control (
        id INTEGER PRIMARY KEY CHECK(id=1),
        lease_job INTEGER REFERENCES service_campaign_jobs(id),
        lease_token TEXT,
        lease_until INTEGER NOT NULL DEFAULT 0 CHECK(typeof(lease_until)='integer' AND lease_until>=0),
        next_send_at INTEGER NOT NULL DEFAULT 0 CHECK(typeof(next_send_at)='integer' AND next_send_at>=0),
        clock_seen INTEGER NOT NULL DEFAULT 0 CHECK(typeof(clock_seen)='integer' AND clock_seen>=0),
        CHECK((lease_job IS NULL AND lease_token IS NULL AND lease_until=0) OR
              (lease_job IS NOT NULL AND lease_token IS NOT NULL AND length(lease_token)=32
               AND lease_token NOT GLOB '*[^0-9a-f]*' AND lease_until>0))
    )""",
    "idx_service_campaign_jobs_due": """CREATE INDEX idx_service_campaign_jobs_due
        ON service_campaign_jobs(state,ready_at,id)""",
    "idx_service_campaign_recipient_due": """CREATE INDEX idx_service_campaign_recipient_due
        ON service_campaign_recipients(job_id,state,next_at,id)""",
    "idx_service_campaign_one_recipient_intent": """CREATE UNIQUE INDEX idx_service_campaign_one_recipient_intent
        ON service_campaign_attempts(recipient_id) WHERE state='intent'""",
    "idx_service_campaign_one_job_intent": """CREATE UNIQUE INDEX idx_service_campaign_one_job_intent
        ON service_campaign_attempts(job_id) WHERE state='intent'""",
    "service_campaign_snapshot_insert": """CREATE TRIGGER service_campaign_snapshot_insert
        BEFORE INSERT ON service_campaign_recipients WHEN NOT EXISTS (
            SELECT 1 FROM service_campaign_jobs WHERE id=NEW.job_id AND snapshot_sealed=0 AND state='draft'
        ) BEGIN SELECT RAISE(ABORT,'Campaign snapshot is sealed'); END""",
    "service_campaign_attempt_intent": """CREATE TRIGGER service_campaign_attempt_intent
        BEFORE INSERT ON service_campaign_attempts WHEN NEW.state!='intent' OR NOT EXISTS (
            SELECT 1 FROM service_campaign_recipients r
            JOIN service_campaign_jobs j ON j.id=r.job_id
            JOIN service_campaign_control c ON c.lease_job=j.id AND c.id=1
            WHERE r.id=NEW.recipient_id AND r.job_id=NEW.job_id AND r.state='pending'
                AND NEW.attempt_no=r.attempt_count+1 AND j.state='running' AND j.snapshot_sealed=1
                AND c.lease_token=NEW.lease_token AND c.lease_until>NEW.started_at
        ) BEGIN SELECT RAISE(ABORT,'Invalid campaign attempt'); END""",
    "service_campaign_attempt_terminal": """CREATE TRIGGER service_campaign_attempt_terminal
        BEFORE UPDATE ON service_campaign_attempts WHEN OLD.state!='intent'
        BEGIN SELECT RAISE(ABORT,'Campaign attempt is terminal'); END""",
    "service_campaign_recipient_terminal": """CREATE TRIGGER service_campaign_recipient_terminal
        BEFORE UPDATE ON service_campaign_recipients WHEN OLD.state NOT IN ('pending','intent')
        BEGIN SELECT RAISE(ABORT,'Campaign recipient is terminal'); END""",
    "service_campaign_recipient_transition": """CREATE TRIGGER service_campaign_recipient_transition
        BEFORE UPDATE OF state ON service_campaign_recipients WHEN NEW.state!=OLD.state AND NOT (
            (OLD.state='pending' AND NEW.state IN ('intent','failed','cancelled','skipped')) OR
            (OLD.state='intent' AND NEW.state IN ('pending','sent','unavailable','unknown','failed','cancelled','skipped'))
        ) BEGIN SELECT RAISE(ABORT,'Invalid campaign recipient transition'); END""",
    "service_campaign_job_transition": """CREATE TRIGGER service_campaign_job_transition
        BEFORE UPDATE OF state ON service_campaign_jobs WHEN NEW.state!=OLD.state AND NOT (
            (OLD.state='draft' AND NEW.state IN ('scheduled','cancelled')) OR
            (OLD.state='scheduled' AND NEW.state IN ('running','paused','cancelled')) OR
            (OLD.state='running' AND NEW.state IN ('scheduled','paused','cancelled','completed','partial')) OR
            (OLD.state='paused' AND NEW.state IN ('scheduled','cancelled'))
        ) BEGIN SELECT RAISE(ABORT,'Invalid campaign job transition'); END""",
    "service_campaign_control_no_delete": """CREATE TRIGGER service_campaign_control_no_delete
        BEFORE DELETE ON service_campaign_control
        BEGIN SELECT RAISE(ABORT,'Campaign control is required'); END""",
}

for _table, _fields, _condition in (
    ("service_campaign_jobs",
     ("id", "owner_id", "operation_id", "revision_id", "payload_sha256", "due_at", "timezone",
      "local_time", "snapshot_sha256", "snapshot_sealed", "created_at"), "OLD.snapshot_sealed=1 AND "),
    ("service_campaign_recipients", ("id", "job_id", "telegram_id", "proof_generation"), ""),
    ("service_campaign_attempts", ("id", "job_id", "recipient_id", "attempt_no", "lease_token", "started_at"), ""),
):
    _name = _table + "_identity"
    _changed = " OR ".join(f"NEW.{field} IS NOT OLD.{field}" for field in _fields)
    QUEUE_SCHEMA[_name] = (f"CREATE TRIGGER {_name} BEFORE UPDATE OF {','.join(_fields)} ON {_table} "
                           f"WHEN {_condition}({_changed}) "
                           "BEGIN SELECT RAISE(ABORT,'Campaign identity is immutable'); END")
    _name = _table + "_no_delete"
    QUEUE_SCHEMA[_name] = (f"CREATE TRIGGER {_name} BEFORE DELETE ON {_table} "
                           "BEGIN SELECT RAISE(ABORT,'Campaign history is immutable'); END")


async def create_queue_schema(conn):
    for name in QUEUE_SCHEMA:
        cur = await conn.execute("SELECT 1 FROM sqlite_master WHERE name=?", (name,))
        if await cur.fetchone():
            raise ValueError("Unjournaled campaign delivery object")
    for sql in QUEUE_SCHEMA.values():
        await conn.execute(sql)
    # Existing proof comes only from the verified v16 ledger, never users/import.
    await conn.execute("INSERT INTO service_campaign_contact_generations(telegram_id,generation) "
                       "SELECT telegram_id,lower(hex(randomblob(16))) FROM service_campaign_contacts")
    await conn.execute("INSERT INTO service_campaign_control(id) VALUES (1)")


async def queue_schema_valid(conn):
    for name, expected in QUEUE_SCHEMA.items():
        cur = await conn.execute("SELECT sql FROM sqlite_master WHERE name=?", (name,))
        row = await cur.fetchone()
        if not row or re.sub(r"\s+", "", row[0] or "") != re.sub(r"\s+", "", expected):
            return False
    cur = await conn.execute("SELECT COUNT(*) FROM service_campaign_control WHERE id=1")
    if (await cur.fetchone())[0] != 1:
        return False
    cur = await conn.execute("SELECT 1 FROM service_campaign_contacts c LEFT JOIN "
                             "service_campaign_contact_generations g ON g.telegram_id=c.telegram_id "
                             "WHERE g.telegram_id IS NULL LIMIT 1")
    if await cur.fetchone():
        return False
    cur = await conn.execute("SELECT 1 FROM service_campaign_contact_generations g LEFT JOIN "
                             "service_campaign_contacts c ON c.telegram_id=g.telegram_id "
                             "WHERE c.telegram_id IS NULL LIMIT 1")
    return await cur.fetchone() is None
