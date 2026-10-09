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
        "currency", "server_group_id", "active", "created_at", "stars_price",
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
    "bot_update_acknowledgments": (
        "job_run_id", "actor_id", "actor_username", "reason_code", "evidence_code",
        "operation_id", "target_release", "agent_state", "target_sha",
        "current_release", "current_sha", "postcondition", "acknowledged_at",
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
    "user_groups": (
        "id", "name", "description", "created_at", "updated_at",
    ),
    "user_group_members": (
        "group_id", "telegram_id", "created_at",
    ),
    "website_monitors": (
        "id", "canonical_url", "hostname", "enabled", "state", "last_check_at",
        "next_check_at", "last_http_status", "last_latency_ms", "last_error_kind",
        "consecutive_failures", "created_at", "updated_at",
    ),
    "website_monitor_watchers": (
        "monitor_id", "telegram_id", "notifications_enabled", "created_at",
        "monitoring_enabled",
    ),
    "website_incidents": (
        "id", "monitor_id", "opened_at", "resolved_at", "reason_kind",
        "first_http_status", "last_http_status", "alert_count", "last_alert_at",
    ),
    "website_incident_notifications": (
        "incident_id", "telegram_id", "kind", "sequence", "sent_at",
    ),
    "commerce_orders": (
        "id", "telegram_id", "plan_id", "promo_code_id", "amount_minor", "currency",
        "status", "created_at", "updated_at", "paid_at",
    ),
    "commerce_payments": (
        "id", "order_id", "provider", "provider_payment_id", "amount_minor", "currency",
        "status", "created_at", "updated_at", "confirmed_at", "checkout_url",
        "idempotency_key",
    ),
    "payment_webhook_events": (
        "id", "provider", "provider_event_id", "event_type", "signature_valid",
        "payload_sha256", "metadata_json", "processing_status", "order_id", "payment_id",
        "received_at", "applied_at", "result_code", "provider_payment_id",
    ),
    "entitlements": (
        "id", "telegram_id", "order_id", "plan_id", "status", "starts_at",
        "expires_at", "created_at", "updated_at", "quota_reset_status",
    ),
    "customer_terms_acceptance": (
        "telegram_id", "terms_version", "accepted_at",
    ),
    "stars_refund_operations": (
        "id", "operation_id", "payment_id", "telegram_id", "provider_payment_id",
        "status", "requested_by", "created_at", "updated_at", "error",
    ),
}

_EXPECTED_INDEXES = {
    "idx_audit_log_created_at",
    "idx_job_runs_name_started",
    "idx_payments_user_created",
    "idx_payments_status_created",
    "idx_promo_active_code",
    "idx_user_group_members_user",
    "idx_website_monitors_due",
    "idx_website_watchers_user",
    "idx_website_incidents_monitor_open",
    "idx_website_notifications_recipient",
    "idx_commerce_orders_user_created",
    "idx_commerce_orders_status_created",
    "idx_commerce_payments_order",
    "idx_commerce_payments_provider_identity",
    "idx_commerce_payments_provider_idempotency",
    "idx_payment_webhook_provider_event",
    "idx_payment_webhook_processing",
    "idx_entitlements_user_status",
    "idx_entitlements_order",
    "idx_stars_refund_status_created",
}


async def _validate_current_schema(
    db: aiosqlite.Connection,
    *,
    include_user_groups: bool = True,
    include_website_monitoring: bool = True,
    include_website_watcher_lifecycle: bool = True,
    include_commerce: bool = True,
    include_payment_event_reference: bool = True,
    include_checkout_reference: bool = True,
    include_plan_stars_price: bool = True,
    include_stars_hardening: bool = True,
    include_entitlement_quota_cycle: bool = True,
    include_bot_update_acknowledgments: bool = False,
) -> None:
    skipped_tables: set[str] = set()
    if not include_user_groups:
        skipped_tables.update({"user_groups", "user_group_members"})
    if not include_website_monitoring:
        skipped_tables.update({
            "website_monitors",
            "website_monitor_watchers",
            "website_incidents",
            "website_incident_notifications",
        })
    if not include_commerce:
        skipped_tables.update({
            "commerce_orders",
            "commerce_payments",
            "payment_webhook_events",
            "entitlements",
            "customer_terms_acceptance",
            "stars_refund_operations",
        })
    elif not include_stars_hardening:
        skipped_tables.update({
            "customer_terms_acceptance",
            "stars_refund_operations",
        })
    if not include_bot_update_acknowledgments:
        skipped_tables.add("bot_update_acknowledgments")
    for table, expected in _EXPECTED_COLUMNS.items():
        if table in skipped_tables:
            continue
        if table == "website_monitor_watchers" and not include_website_watcher_lifecycle:
            expected = tuple(
                column for column in expected if column != "monitoring_enabled"
            )
        if table == "payment_webhook_events" and not include_payment_event_reference:
            expected = tuple(
                column for column in expected if column != "provider_payment_id"
            )
        if table == "commerce_payments" and not include_checkout_reference:
            expected = tuple(
                column for column in expected
                if column not in {"checkout_url", "idempotency_key"}
            )
        if table == "plans" and not include_plan_stars_price:
            expected = tuple(
                column for column in expected if column != "stars_price"
            )
        if table == "entitlements" and not include_entitlement_quota_cycle:
            expected = tuple(
                column for column in expected if column != "quota_reset_status"
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
    expected_indexes = set(_EXPECTED_INDEXES)
    if not include_user_groups:
        expected_indexes.discard("idx_user_group_members_user")
    if not include_website_monitoring:
        expected_indexes -= {
            "idx_website_monitors_due",
            "idx_website_watchers_user",
            "idx_website_incidents_monitor_open",
            "idx_website_notifications_recipient",
        }
    if not include_checkout_reference:
        expected_indexes.discard("idx_commerce_payments_provider_idempotency")
    if not include_stars_hardening:
        expected_indexes.discard("idx_stars_refund_status_created")
    if not include_commerce:
        expected_indexes -= {
            "idx_commerce_orders_user_created",
            "idx_commerce_orders_status_created",
            "idx_commerce_payments_order",
            "idx_commerce_payments_provider_identity",
            "idx_commerce_payments_provider_idempotency",
            "idx_payment_webhook_provider_event",
            "idx_payment_webhook_processing",
            "idx_entitlements_user_status",
            "idx_entitlements_order",
        }
    missing_indexes = sorted(expected_indexes - actual_indexes)
    if missing_indexes:
        raise DatabaseMigrationError(
            f"Schema is missing required indexes: {', '.join(missing_indexes)}"
        )


async def _validate_baseline_v1_schema(db: aiosqlite.Connection) -> None:
    for table, expected_current in _EXPECTED_COLUMNS.items():
        if table in {
            "user_groups", "user_group_members",
            "website_monitors", "website_monitor_watchers",
            "website_incidents", "website_incident_notifications",
            "commerce_orders", "commerce_payments", "payment_webhook_events", "entitlements",
            "customer_terms_acceptance", "stars_refund_operations",
            "bot_update_acknowledgments",
        }:
            continue
        if table == "user_profiles":
            expected = ("telegram_id", "plan_id", "server_group_id", "note", "updated_at")
        elif table == "plans":
            expected = tuple(
                column for column in expected_current if column != "stars_price"
            )
        else:
            expected = expected_current
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
    missing_indexes = sorted(
        (
            _EXPECTED_INDEXES
            - {
                "idx_user_group_members_user",
                "idx_website_monitors_due",
                "idx_website_watchers_user",
                "idx_website_incidents_monitor_open",
                "idx_website_notifications_recipient",
                "idx_commerce_orders_user_created",
                "idx_commerce_orders_status_created",
                "idx_commerce_payments_order",
                "idx_commerce_payments_provider_identity",
                "idx_commerce_payments_provider_idempotency",
                "idx_payment_webhook_provider_event",
                "idx_payment_webhook_processing",
                "idx_entitlements_user_status",
                "idx_entitlements_order",
                "idx_stars_refund_status_created",
            }
        ) - actual_indexes
    )
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
    await _validate_current_schema(
        db,
        include_user_groups=False,
        include_website_monitoring=False,
        include_commerce=False,
        include_plan_stars_price=False,
        include_stars_hardening=False,
        include_entitlement_quota_cycle=False,
    )


async def _migration_0003_user_audience_groups(db: aiosqlite.Connection) -> None:
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS user_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT COLLATE NOCASE NOT NULL UNIQUE,
            description TEXT NOT NULL DEFAULT '',
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )
        """
    )
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS user_group_members (
            group_id INTEGER NOT NULL,
            telegram_id INTEGER NOT NULL,
            created_at INTEGER NOT NULL,
            PRIMARY KEY(group_id, telegram_id)
        )
        """
    )
    await db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_user_group_members_user
        ON user_group_members(telegram_id, group_id)
        """
    )
    await _validate_current_schema(
        db,
        include_website_monitoring=False,
        include_commerce=False,
        include_plan_stars_price=False,
        include_stars_hardening=False,
    )


async def _migration_0004_website_monitoring_v4_24_0(
    db: aiosqlite.Connection,
) -> None:
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS website_monitors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            canonical_url TEXT NOT NULL UNIQUE,
            hostname TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0, 1)),
            state TEXT NOT NULL DEFAULT 'unknown'
                CHECK(state IN ('unknown', 'up', 'suspect', 'down')),
            last_check_at INTEGER NOT NULL DEFAULT 0,
            next_check_at INTEGER NOT NULL DEFAULT 0,
            last_http_status INTEGER NOT NULL DEFAULT 0,
            last_latency_ms INTEGER NOT NULL DEFAULT 0,
            last_error_kind TEXT NOT NULL DEFAULT '',
            consecutive_failures INTEGER NOT NULL DEFAULT 0,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )
        """
    )
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS website_monitor_watchers (
            monitor_id INTEGER NOT NULL,
            telegram_id INTEGER NOT NULL,
            notifications_enabled INTEGER NOT NULL DEFAULT 1
                CHECK(notifications_enabled IN (0, 1)),
            created_at INTEGER NOT NULL,
            PRIMARY KEY(monitor_id, telegram_id)
        )
        """
    )
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS website_incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            monitor_id INTEGER NOT NULL,
            opened_at INTEGER NOT NULL,
            resolved_at INTEGER NOT NULL DEFAULT 0,
            reason_kind TEXT NOT NULL,
            first_http_status INTEGER NOT NULL DEFAULT 0,
            last_http_status INTEGER NOT NULL DEFAULT 0,
            alert_count INTEGER NOT NULL DEFAULT 0,
            last_alert_at INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS website_incident_notifications (
            incident_id INTEGER NOT NULL,
            telegram_id INTEGER NOT NULL,
            kind TEXT NOT NULL CHECK(kind IN ('opened', 'repeat', 'recovered')),
            sequence INTEGER NOT NULL DEFAULT 0 CHECK(sequence >= 0),
            sent_at INTEGER NOT NULL,
            PRIMARY KEY(incident_id, telegram_id, kind, sequence)
        )
        """
    )
    await db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_website_monitors_due
        ON website_monitors(enabled, next_check_at, id)
        """
    )
    await db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_website_watchers_user
        ON website_monitor_watchers(telegram_id, monitor_id)
        """
    )
    await db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_website_incidents_monitor_open
        ON website_incidents(monitor_id, resolved_at, opened_at DESC)
        """
    )
    await db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_website_notifications_recipient
        ON website_incident_notifications(telegram_id, sent_at DESC)
        """
    )
    await _validate_current_schema(
        db,
        include_website_watcher_lifecycle=False,
        include_commerce=False,
        include_plan_stars_price=False,
        include_stars_hardening=False,
    )


async def _migration_0005_website_watcher_lifecycle_v4_24_0(
    db: aiosqlite.Connection,
) -> None:
    cursor = await db.execute('PRAGMA table_info("website_monitor_watchers")')
    columns = {str(row[1]) for row in await cursor.fetchall()}
    if "monitoring_enabled" not in columns:
        await db.execute(
            "ALTER TABLE website_monitor_watchers "
            "ADD COLUMN monitoring_enabled INTEGER NOT NULL DEFAULT 1 "
            "CHECK(monitoring_enabled IN (0, 1))"
        )
    await _validate_current_schema(
        db,
        include_commerce=False,
        include_plan_stars_price=False,
        include_stars_hardening=False,
    )


async def _migration_0006_client_portal_commerce_foundation(
    db: aiosqlite.Connection,
) -> None:
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS commerce_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            plan_id INTEGER NOT NULL,
            promo_code_id INTEGER,
            amount_minor INTEGER NOT NULL CHECK(amount_minor >= 0),
            currency TEXT NOT NULL,
            status TEXT NOT NULL
                CHECK(status IN ('created', 'awaiting_payment', 'paid', 'cancelled', 'expired')),
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            paid_at INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS commerce_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            provider TEXT NOT NULL,
            provider_payment_id TEXT NOT NULL,
            amount_minor INTEGER NOT NULL CHECK(amount_minor >= 0),
            currency TEXT NOT NULL,
            status TEXT NOT NULL
                CHECK(status IN ('created', 'pending', 'confirmed', 'failed', 'refunded', 'unknown')),
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            confirmed_at INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS payment_webhook_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT NOT NULL,
            provider_event_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            signature_valid INTEGER NOT NULL CHECK(signature_valid IN (0, 1)),
            payload_sha256 TEXT NOT NULL,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            processing_status TEXT NOT NULL
                CHECK(processing_status IN ('received', 'applied', 'ignored', 'failed')),
            order_id INTEGER,
            payment_id INTEGER,
            received_at INTEGER NOT NULL,
            applied_at INTEGER NOT NULL DEFAULT 0,
            result_code TEXT NOT NULL DEFAULT ''
        )
        """
    )
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS entitlements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            order_id INTEGER NOT NULL,
            plan_id INTEGER NOT NULL,
            status TEXT NOT NULL
                CHECK(status IN ('pending', 'provisioning', 'active', 'suspended', 'expired', 'failed')),
            starts_at INTEGER NOT NULL DEFAULT 0,
            expires_at INTEGER NOT NULL DEFAULT 0,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )
        """
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_commerce_orders_user_created "
        "ON commerce_orders(telegram_id, created_at DESC)"
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_commerce_orders_status_created "
        "ON commerce_orders(status, created_at DESC)"
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_commerce_payments_order "
        "ON commerce_payments(order_id, created_at DESC)"
    )
    await db.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_commerce_payments_provider_identity "
        "ON commerce_payments(provider, provider_payment_id)"
    )
    await db.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_payment_webhook_provider_event "
        "ON payment_webhook_events(provider, provider_event_id)"
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_payment_webhook_processing "
        "ON payment_webhook_events(processing_status, received_at)"
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_entitlements_user_status "
        "ON entitlements(telegram_id, status, updated_at DESC)"
    )
    await db.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_entitlements_order "
        "ON entitlements(order_id)"
    )
    await _validate_current_schema(
        db,
        include_payment_event_reference=False,
        include_checkout_reference=False,
        include_plan_stars_price=False,
        include_stars_hardening=False,
        include_entitlement_quota_cycle=False,
    )


async def _migration_0007_payment_event_reconciliation_v5_0_0(
    db: aiosqlite.Connection,
) -> None:
    cursor = await db.execute('PRAGMA table_info("payment_webhook_events")')
    columns = {str(row[1]) for row in await cursor.fetchall()}
    if "provider_payment_id" not in columns:
        await db.execute(
            "ALTER TABLE payment_webhook_events "
            "ADD COLUMN provider_payment_id TEXT NOT NULL DEFAULT ''"
        )
    await _validate_current_schema(
        db,
        include_checkout_reference=False,
        include_plan_stars_price=False,
        include_stars_hardening=False,
        include_entitlement_quota_cycle=False,
    )


async def _migration_0008_checkout_reference_v5_0_0(
    db: aiosqlite.Connection,
) -> None:
    cursor = await db.execute('PRAGMA table_info("commerce_payments")')
    columns = {str(row[1]) for row in await cursor.fetchall()}
    if "checkout_url" not in columns:
        await db.execute(
            "ALTER TABLE commerce_payments "
            "ADD COLUMN checkout_url TEXT NOT NULL DEFAULT ''"
        )
    if "idempotency_key" not in columns:
        await db.execute(
            "ALTER TABLE commerce_payments "
            "ADD COLUMN idempotency_key TEXT NOT NULL DEFAULT ''"
        )
    await db.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_commerce_payments_provider_idempotency "
        "ON commerce_payments(provider, idempotency_key) "
        "WHERE idempotency_key <> ''"
    )
    await _validate_current_schema(
        db,
        include_plan_stars_price=False,
        include_stars_hardening=False,
        include_entitlement_quota_cycle=False,
    )


async def _migration_0009_telegram_stars_price_v5_0_0(
    db: aiosqlite.Connection,
) -> None:
    cursor = await db.execute('PRAGMA table_info("plans")')
    columns = {str(row[1]) for row in await cursor.fetchall()}
    if "stars_price" not in columns:
        await db.execute(
            "ALTER TABLE plans "
            "ADD COLUMN stars_price INTEGER NOT NULL DEFAULT 0 "
            "CHECK(stars_price >= 0)"
        )
    await _validate_current_schema(
        db,
        include_stars_hardening=False,
        include_entitlement_quota_cycle=False,
    )


async def _migration_0010_stars_production_hardening_v5_0_0(
    db: aiosqlite.Connection,
) -> None:
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS customer_terms_acceptance (
            telegram_id INTEGER NOT NULL,
            terms_version TEXT NOT NULL,
            accepted_at INTEGER NOT NULL,
            PRIMARY KEY(telegram_id, terms_version)
        )
        """
    )
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS stars_refund_operations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            operation_id TEXT NOT NULL UNIQUE,
            payment_id INTEGER NOT NULL UNIQUE,
            telegram_id INTEGER NOT NULL,
            provider_payment_id TEXT NOT NULL,
            status TEXT NOT NULL
                CHECK(status IN ('in_flight', 'success', 'failed', 'unknown')),
            requested_by INTEGER NOT NULL,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            error TEXT NOT NULL DEFAULT ''
        )
        """
    )
    await db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_stars_refund_status_created
        ON stars_refund_operations(status, created_at)
        """
    )
    await _validate_current_schema(
        db,
        include_entitlement_quota_cycle=False,
    )


async def _migration_0011_entitlement_quota_cycle_v5_0_0(
    db: aiosqlite.Connection,
) -> None:
    cursor = await db.execute('PRAGMA table_info("entitlements")')
    columns = {str(row[1]) for row in await cursor.fetchall()}
    if "quota_reset_status" not in columns:
        await db.execute(
            "ALTER TABLE entitlements "
            "ADD COLUMN quota_reset_status TEXT NOT NULL DEFAULT 'pending' "
            "CHECK(quota_reset_status IN "
            "('pending', 'legacy', 'not_required', 'in_flight', "
            "'success', 'failed', 'unknown'))"
        )
        # Existing entitlements predate the durable quota-reset journal. Do not
        # infer that their traffic was reset and never mutate them automatically.
        await db.execute(
            "UPDATE entitlements SET quota_reset_status = 'legacy'"
        )
    await _validate_current_schema(db)



async def _migration_0012_bot_update_unknown_ack_v5_0_0(
    db: aiosqlite.Connection,
) -> None:
    # Additive evidence only: no job status/history is touched or reclassified.
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS bot_update_acknowledgments (
            job_run_id INTEGER PRIMARY KEY REFERENCES job_runs(id),
            actor_id INTEGER NOT NULL,
            actor_username TEXT NOT NULL DEFAULT '',
            reason_code TEXT NOT NULL CHECK(
                reason_code IN ('reviewed', 'recovered', 'insufficient')
            ),
            evidence_code TEXT NOT NULL,
            operation_id TEXT NOT NULL DEFAULT '',
            target_release TEXT NOT NULL DEFAULT '',
            agent_state TEXT NOT NULL DEFAULT '',
            target_sha TEXT NOT NULL DEFAULT '',
            current_release TEXT NOT NULL DEFAULT '',
            current_sha TEXT NOT NULL DEFAULT '',
            postcondition TEXT NOT NULL DEFAULT 'not_proven',
            acknowledged_at INTEGER NOT NULL
        )
        """
    )
    for action in ("UPDATE", "DELETE"):
        await db.execute(
            f"""
            CREATE TRIGGER IF NOT EXISTS
                trg_bot_update_ack_no_{action.lower()}
            BEFORE {action} ON bot_update_acknowledgments
            BEGIN
                SELECT RAISE(ABORT, 'historical acknowledgment is immutable');
            END
            """
        )
    await _validate_current_schema(db, include_bot_update_acknowledgments=True)


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
    MigrationStep(
        version=3,
        name="user_audience_groups_v4_22_0",
        apply=_migration_0003_user_audience_groups,
        requires_backup=False,
    ),
    MigrationStep(
        version=4,
        name="website_monitoring_v4_24_0",
        apply=_migration_0004_website_monitoring_v4_24_0,
        requires_backup=False,
    ),
    MigrationStep(
        version=5,
        name="website_watcher_lifecycle_v4_24_0",
        apply=_migration_0005_website_watcher_lifecycle_v4_24_0,
        requires_backup=False,
    ),
    MigrationStep(
        version=6,
        name="client_portal_commerce_foundation_v5_0_0",
        apply=_migration_0006_client_portal_commerce_foundation,
        requires_backup=False,
    ),
    MigrationStep(
        version=7,
        name="payment_event_reconciliation_v5_0_0",
        apply=_migration_0007_payment_event_reconciliation_v5_0_0,
        requires_backup=False,
    ),
    MigrationStep(
        version=8,
        name="checkout_reference_v5_0_0",
        apply=_migration_0008_checkout_reference_v5_0_0,
        requires_backup=False,
    ),
    MigrationStep(
        version=9,
        name="telegram_stars_price_v5_0_0",
        apply=_migration_0009_telegram_stars_price_v5_0_0,
        requires_backup=False,
    ),
    MigrationStep(
        version=10,
        name="stars_production_hardening_v5_0_0",
        apply=_migration_0010_stars_production_hardening_v5_0_0,
        requires_backup=False,
    ),
    MigrationStep(
        version=11,
        name="entitlement_quota_cycle_v5_0_0",
        apply=_migration_0011_entitlement_quota_cycle_v5_0_0,
        requires_backup=False,
    ),
    MigrationStep(
        version=12,
        name="bot_update_unknown_ack_v5_0_0",
        apply=_migration_0012_bot_update_unknown_ack_v5_0_0,
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
            await _validate_current_schema(db, include_bot_update_acknowledgments=True)
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
