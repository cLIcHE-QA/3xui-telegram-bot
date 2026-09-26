from __future__ import annotations

import asyncio
import os
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Awaitable, Callable, Sequence

import aiosqlite


class DatabaseMigrationError(RuntimeError):
    """Base error for bot SQLite schema migration failures."""


class DatabaseSchemaTooNewError(DatabaseMigrationError):
    """The database was migrated by a newer application version."""


class DatabaseMigrationBlockedError(DatabaseMigrationError):
    """A prior migration is unfinished/failed or the journal is inconsistent."""


class DatabaseMigrationBackupError(DatabaseMigrationError):
    """A required pre-migration recovery copy could not be created."""


MigrationApply = Callable[[aiosqlite.Connection], Awaitable[None]]


@dataclass(frozen=True)
class MigrationStep:
    version: int
    name: str
    apply: MigrationApply
    requires_backup: bool = False


JOURNAL_TABLE = "schema_migrations"

_JOURNAL_DDL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY CHECK(version > 0),
    name TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('running', 'success', 'failed')),
    requires_backup INTEGER NOT NULL DEFAULT 0,
    backup_path TEXT NOT NULL DEFAULT '',
    started_at INTEGER NOT NULL,
    finished_at INTEGER NOT NULL DEFAULT 0,
    error TEXT NOT NULL DEFAULT ''
)
"""

_BASELINE_DDL: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS users (
        telegram_id INTEGER PRIMARY KEY,
        email TEXT NOT NULL UNIQUE,
        sub_id TEXT NOT NULL UNIQUE,
        expiry_time INTEGER NOT NULL,
        created_at INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS server_groups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT COLLATE NOCASE NOT NULL UNIQUE,
        description TEXT NOT NULL DEFAULT '',
        created_at INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS server_group_members (
        group_id INTEGER NOT NULL,
        member_key TEXT NOT NULL,
        PRIMARY KEY(group_id, member_key)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS server_group_provisioning (
        group_id INTEGER PRIMARY KEY,
        inbound_mode TEXT NOT NULL DEFAULT 'all_managed',
        updated_at INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS server_group_inbounds (
        group_id INTEGER NOT NULL,
        inbound_id INTEGER NOT NULL,
        PRIMARY KEY(group_id, inbound_id)
    )
    """,
    """
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
    """,
    """
    CREATE TABLE IF NOT EXISTS hosts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        label TEXT NOT NULL,
        hostname TEXT NOT NULL,
        role TEXT NOT NULL,
        enabled INTEGER NOT NULL DEFAULT 1,
        created_at INTEGER NOT NULL,
        UNIQUE(hostname, role)
    )
    """,
    """
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
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_audit_log_created_at
    ON audit_log(created_at DESC)
    """,
    """
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
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_job_runs_name_started
    ON job_runs(name, started_at DESC)
    """,
    """
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
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_payments_user_created
    ON payments(telegram_id, created_at DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_payments_status_created
    ON payments(status, created_at DESC)
    """,
    """
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
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_promo_active_code
    ON promo_codes(active, code COLLATE NOCASE)
    """,
    """
    CREATE TABLE IF NOT EXISTS administrators (
        telegram_id INTEGER PRIMARY KEY,
        role TEXT NOT NULL,
        enabled INTEGER NOT NULL DEFAULT 1,
        added_by INTEGER NOT NULL DEFAULT 0,
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS runtime_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_by INTEGER NOT NULL DEFAULT 0,
        updated_at INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS user_profiles (
        telegram_id INTEGER PRIMARY KEY,
        plan_id INTEGER,
        server_group_id INTEGER,
        note TEXT NOT NULL DEFAULT '',
        updated_at INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS inbound_templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT COLLATE NOCASE NOT NULL UNIQUE,
        source_inbound_id INTEGER NOT NULL DEFAULT 0,
        protocol TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS alert_rules (
        code TEXT PRIMARY KEY,
        enabled INTEGER NOT NULL DEFAULT 1,
        threshold INTEGER NOT NULL DEFAULT 0,
        cooldown_sec INTEGER NOT NULL DEFAULT 1800,
        updated_at INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS alert_state (
        code TEXT NOT NULL,
        target TEXT NOT NULL,
        active INTEGER NOT NULL DEFAULT 0,
        last_value TEXT NOT NULL DEFAULT '',
        first_seen INTEGER NOT NULL DEFAULT 0,
        last_seen INTEGER NOT NULL DEFAULT 0,
        last_notified INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY(code, target)
    )
    """,
)

_EXPECTED_COLUMNS: dict[str, tuple[str, ...]] = {
    "users": ("telegram_id", "email", "sub_id", "expiry_time", "created_at"),
    "server_groups": ("id", "name", "description", "created_at"),
    "server_group_members": ("group_id", "member_key"),
    "server_group_provisioning": ("group_id", "inbound_mode", "updated_at"),
    "server_group_inbounds": ("group_id", "inbound_id"),
    "plans": (
        "id", "name", "duration_days", "traffic_gb", "ip_limit", "price_minor",
        "currency", "server_group_id", "active", "created_at",
    ),
    "hosts": ("id", "label", "hostname", "role", "enabled", "created_at"),
    "audit_log": (
        "id", "actor_id", "actor_username", "action", "target_type", "target_id",
        "details", "success", "created_at",
    ),
    "job_runs": (
        "id", "name", "trigger", "actor_id", "status", "started_at",
        "finished_at", "duration_ms", "details",
    ),
    "payments": (
        "id", "telegram_id", "plan_id", "amount_minor", "currency", "status",
        "provider", "external_id", "note", "created_by", "created_at", "updated_at",
        "paid_at",
    ),
    "promo_codes": (
        "id", "code", "discount_type", "value", "currency", "plan_id", "max_uses",
        "uses_count", "expires_at", "active", "created_at",
    ),
    "administrators": (
        "telegram_id", "role", "enabled", "added_by", "created_at", "updated_at",
    ),
    "runtime_settings": ("key", "value", "updated_by", "updated_at"),
    "user_profiles": (
        "telegram_id", "plan_id", "server_group_id", "note", "updated_at", "display_name",
    ),
    "inbound_templates": (
        "id", "name", "source_inbound_id", "protocol", "payload_json", "created_at",
        "updated_at",
    ),
    "alert_rules": ("code", "enabled", "threshold", "cooldown_sec", "updated_at"),
    "alert_state": (
        "code", "target", "active", "last_value", "first_seen", "last_seen",
        "last_notified",
    ),
}

_EXPECTED_INDEXES = {
    "idx_audit_log_created_at",
    "idx_job_runs_name_started",
    "idx_payments_user_created",
    "idx_payments_status_created",
    "idx_promo_active_code",
}


async def _validate_current_schema(db: aiosqlite.Connection) -> None:
    for table, expected in _EXPECTED_COLUMNS.items():
        cursor = await db.execute(f'PRAGMA table_info("{table}")')
        rows = await cursor.fetchall()
        actual = tuple(str(row[1]) for row in rows)
        if actual != expected:
            raise DatabaseMigrationError(
                f"Schema mismatch for {table}: expected columns {expected!r}, got {actual!r}."
            )

    cursor = await db.execute(
        "SELECT name FROM sqlite_master WHERE type = 'index' AND name LIKE 'idx_%'"
    )
    actual_indexes = {str(row[0]) for row in await cursor.fetchall()}
    missing_indexes = sorted(_EXPECTED_INDEXES - actual_indexes)
    if missing_indexes:
        raise DatabaseMigrationError(
            f"Schema is missing required indexes: {', '.join(missing_indexes)}"
        )


async def _validate_baseline_v1_schema(db: aiosqlite.Connection) -> None:
    for table, expected_current in _EXPECTED_COLUMNS.items():
        expected = (
            ("telegram_id", "plan_id", "server_group_id", "note", "updated_at")
            if table == "user_profiles"
            else expected_current
        )
        cursor = await db.execute(f'PRAGMA table_info("{table}")')
        rows = await cursor.fetchall()
        actual = tuple(str(row[1]) for row in rows)
        if actual != expected:
            raise DatabaseMigrationError(
                f"Schema mismatch for {table}: expected columns {expected!r}, got {actual!r}."
            )

    cursor = await db.execute(
        "SELECT name FROM sqlite_master WHERE type = 'index' AND name LIKE 'idx_%'"
    )
    actual_indexes = {str(row[0]) for row in await cursor.fetchall()}
    missing_indexes = sorted(_EXPECTED_INDEXES - actual_indexes)
    if missing_indexes:
        raise DatabaseMigrationError(
            f"Schema is missing required indexes: {', '.join(missing_indexes)}"
        )


async def _migration_0001_baseline_v4_14_2(db: aiosqlite.Connection) -> None:
    for statement in _BASELINE_DDL:
        await db.execute(statement)

    now = int(time.time())
    defaults = (
        ("master_down", 1, 0, 900),
        ("xray_down", 1, 0, 900),
        ("node_offline", 1, 0, 900),
        ("job_failed", 1, 0, 1800),
        ("disk_high", 1, 85, 1800),
        ("backup_stale", 1, 36, 3600),
    )
    await db.executemany(
        "INSERT OR IGNORE INTO alert_rules"
        "(code, enabled, threshold, cooldown_sec, updated_at) VALUES (?, ?, ?, ?, ?)",
        [(code, enabled, threshold, cooldown, now) for code, enabled, threshold, cooldown in defaults],
    )
    await _validate_baseline_v1_schema(db)


async def _migration_0002_user_display_name(db: aiosqlite.Connection) -> None:
    cursor = await db.execute('PRAGMA table_info("user_profiles")')
    columns = {str(row[1]) for row in await cursor.fetchall()}
    if "display_name" not in columns:
        await db.execute(
            "ALTER TABLE user_profiles ADD COLUMN display_name TEXT NOT NULL DEFAULT ''"
        )
    await _validate_current_schema(db)


MIGRATIONS: tuple[MigrationStep, ...] = (
    MigrationStep(
        version=1,
        name="baseline_v4_14_2",
        apply=_migration_0001_baseline_v4_14_2,
        requires_backup=False,
    ),
    MigrationStep(
        version=2,
        name="user_display_name_v4_21_0",
        apply=_migration_0002_user_display_name,
        requires_backup=False,
    ),
)

CURRENT_SCHEMA_VERSION = MIGRATIONS[-1].version


def _validate_migration_catalog(migrations: Sequence[MigrationStep]) -> None:
    if not migrations:
        raise DatabaseMigrationError("Migration catalog must not be empty.")
    versions = [item.version for item in migrations]
    if versions != list(range(1, len(migrations) + 1)):
        raise DatabaseMigrationError(
            f"Migration versions must be contiguous from 1; got {versions!r}."
        )
    names = [item.name for item in migrations]
    if len(set(names)) != len(names):
        raise DatabaseMigrationError("Migration names must be unique.")


async def _quick_check(db: aiosqlite.Connection) -> None:
    cursor = await db.execute("PRAGMA quick_check")
    rows = await cursor.fetchall()
    if not rows or any(str(row[0]) != "ok" for row in rows):
        detail = "; ".join(str(row[0]) for row in rows[:10]) if rows else "no result"
        raise DatabaseMigrationError(f"SQLite quick_check failed: {detail}")


def _sqlite_backup(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_uri = f"file:{source.resolve()}?mode=ro"
    with sqlite3.connect(source_uri, uri=True, timeout=15) as src:
        with sqlite3.connect(destination) as dst:
            src.backup(dst)
    os.chmod(destination, 0o600)
    with sqlite3.connect(f"file:{destination.resolve()}?mode=ro", uri=True, timeout=10) as check:
        rows = check.execute("PRAGMA quick_check").fetchall()
    if not rows or any(str(row[0]) != "ok" for row in rows):
        destination.unlink(missing_ok=True)
        raise DatabaseMigrationBackupError("Pre-migration recovery copy failed quick_check.")


async def _create_recovery_copy(
    db_path: str,
    backup_dir: str | None,
    migration: MigrationStep,
) -> Path:
    if not backup_dir:
        raise DatabaseMigrationBackupError(
            f"Migration v{migration.version} ({migration.name}) requires a recovery copy, "
            "but no migration backup directory is configured."
        )
    if db_path == ":memory:":
        raise DatabaseMigrationBackupError(
            "Dangerous migrations cannot create a recovery copy for an in-memory database."
        )

    root = Path(backup_dir)
    root.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(root, 0o700)
    except OSError:
        pass

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    target = root / f"migration-v{migration.version}-{stamp}.sqlite3"
    target.unlink(missing_ok=True)
    try:
        await asyncio.to_thread(_sqlite_backup, Path(db_path), target)
    except DatabaseMigrationBackupError:
        raise
    except Exception as exc:
        target.unlink(missing_ok=True)
        raise DatabaseMigrationBackupError(
            f"Could not create recovery copy for migration v{migration.version}: {exc}"
        ) from exc
    return target


async def run_migrations(
    db_path: str,
    *,
    backup_dir: str | None = None,
    migrations: Sequence[MigrationStep] = MIGRATIONS,
) -> int:
    """Bring one bot SQLite database to the exact schema known by this code.

    The migration journal is committed before each schema transaction. If the
    process crashes mid-migration, SQLite rolls the schema transaction back while
    the journal remains in running state; the next startup blocks instead of
    guessing or replaying the mutation.
    """

    steps = tuple(migrations)
    _validate_migration_catalog(steps)
    by_version = {item.version: item for item in steps}
    current_version = steps[-1].version

    async with aiosqlite.connect(db_path, timeout=15) as db:
        await db.execute(_JOURNAL_DDL)
        await db.commit()
        await _quick_check(db)

        cursor = await db.execute(
            "SELECT version, name, status, requires_backup, backup_path, error "
            "FROM schema_migrations ORDER BY version"
        )
        rows = await cursor.fetchall()

        for version, name, status, requires_backup, backup_path, error in rows:
            version = int(version)
            if version > current_version:
                raise DatabaseSchemaTooNewError(
                    f"Database schema v{version} is newer than supported v{current_version}."
                )
            expected = by_version.get(version)
            if expected is None:
                raise DatabaseMigrationBlockedError(
                    f"Migration journal contains unknown version v{version}."
                )
            if str(name) != expected.name:
                raise DatabaseMigrationBlockedError(
                    f"Migration v{version} name mismatch: journal={name!r}, code={expected.name!r}."
                )
            if bool(requires_backup) != bool(expected.requires_backup):
                raise DatabaseMigrationBlockedError(
                    f"Migration v{version} backup policy differs from the recorded journal."
                )
            if str(status) != "success":
                detail = str(error or "").strip()
                location = f"; recovery_copy={backup_path}" if backup_path else ""
                suffix = f"; error={detail}" if detail else ""
                raise DatabaseMigrationBlockedError(
                    f"Migration v{version} ({name}) is {status}{location}{suffix}."
                )

        applied = [int(row[0]) for row in rows if str(row[2]) == "success"]
        if applied and applied != list(range(1, max(applied) + 1)):
            raise DatabaseMigrationBlockedError(
                f"Migration journal has a version gap: {applied!r}."
            )

        applied_set = set(applied)
        for migration in steps:
            if migration.version in applied_set:
                continue

            backup_path = ""
            if migration.requires_backup:
                backup = await _create_recovery_copy(db_path, backup_dir, migration)
                backup_path = str(backup)

            started_at = int(time.time())
            await db.execute(
                "INSERT INTO schema_migrations"
                "(version, name, status, requires_backup, backup_path, started_at, finished_at, error) "
                "VALUES (?, ?, 'running', ?, ?, ?, 0, '')",
                (
                    migration.version,
                    migration.name,
                    1 if migration.requires_backup else 0,
                    backup_path,
                    started_at,
                ),
            )
            await db.commit()

            try:
                await db.execute("BEGIN IMMEDIATE")
                await migration.apply(db)
                await _quick_check(db)
                await db.execute(
                    "UPDATE schema_migrations "
                    "SET status = 'success', finished_at = ?, error = '' "
                    "WHERE version = ?",
                    (int(time.time()), migration.version),
                )
                await db.commit()
            except Exception as exc:
                try:
                    await db.rollback()
                finally:
                    message = f"{type(exc).__name__}: {exc}"[:1000]
                    await db.execute(
                        "UPDATE schema_migrations "
                        "SET status = 'failed', finished_at = ?, error = ? "
                        "WHERE version = ?",
                        (int(time.time()), message, migration.version),
                    )
                    await db.commit()
                raise DatabaseMigrationError(
                    f"Migration v{migration.version} ({migration.name}) failed: {exc}"
                ) from exc

        if steps == MIGRATIONS:
            await _validate_current_schema(db)
        await _quick_check(db)
        return current_version


async def current_schema_version(db_path: str) -> int:
    """Read the highest successfully applied version without mutating the schema."""

    async with aiosqlite.connect(
        f"file:{Path(db_path).resolve()}?mode=ro", uri=True, timeout=10
    ) as db:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
            (JOURNAL_TABLE,),
        )
        if await cursor.fetchone() is None:
            return 0
        cursor = await db.execute(
            "SELECT COALESCE(MAX(version), 0) FROM schema_migrations WHERE status = 'success'"
        )
        row = await cursor.fetchone()
        return int(row[0] or 0)
