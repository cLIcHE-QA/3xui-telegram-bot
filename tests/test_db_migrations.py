import sqlite3
import tempfile
import unittest
from pathlib import Path

from db import Database
from db_migrations import (
    CURRENT_SCHEMA_VERSION,
    DatabaseMigrationBackupError,
    DatabaseMigrationBlockedError,
    DatabaseMigrationError,
    DatabaseSchemaTooNewError,
    MigrationStep,
    MIGRATIONS,
    current_schema_version,
    run_migrations,
)


class DatabaseMigrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_fresh_database_reaches_current_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bot.sqlite3"
            database = Database(str(path))

            await database.init()

            self.assertEqual(await current_schema_version(str(path)), CURRENT_SCHEMA_VERSION)
            with sqlite3.connect(path) as conn:
                row = conn.execute(
                    "SELECT version, name, status FROM schema_migrations ORDER BY version DESC LIMIT 1"
                ).fetchone()
                self.assertEqual(row, (9, "telegram_stars_price_v5_0_0", "success"))
                columns = [
                    item[1] for item in conn.execute('PRAGMA table_info("user_profiles")').fetchall()
                ]
                self.assertIn("display_name", columns)
                self.assertEqual(conn.execute("PRAGMA quick_check").fetchone()[0], "ok")

    async def test_legacy_database_without_journal_is_upgraded_in_place(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bot.sqlite3"
            with sqlite3.connect(path) as conn:
                conn.execute(
                    """
                    CREATE TABLE users (
                        telegram_id INTEGER PRIMARY KEY,
                        email TEXT NOT NULL UNIQUE,
                        sub_id TEXT NOT NULL UNIQUE,
                        expiry_time INTEGER NOT NULL,
                        created_at INTEGER NOT NULL
                    )
                    """
                )
                conn.execute(
                    "INSERT INTO users VALUES (?, ?, ?, ?, ?)",
                    (123, "legacy@example.com", "legacy-sub", 456, 789),
                )
                conn.commit()

            await Database(str(path)).init()

            with sqlite3.connect(path) as conn:
                self.assertEqual(
                    conn.execute(
                        "SELECT telegram_id, email, sub_id, expiry_time, created_at FROM users"
                    ).fetchone(),
                    (123, "legacy@example.com", "legacy-sub", 456, 789),
                )
                tables = {
                    row[0]
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                }
                self.assertIn("payments", tables)
                self.assertIn("alert_rules", tables)
                self.assertIn("schema_migrations", tables)
                self.assertEqual(
                    conn.execute(
                        "SELECT status FROM schema_migrations WHERE version = 1"
                    ).fetchone()[0],
                    "success",
                )

    async def test_schema_v1_profile_upgrades_to_display_name_without_data_loss(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bot.sqlite3"
            await run_migrations(str(path), migrations=MIGRATIONS[:1])
            with sqlite3.connect(path) as conn:
                conn.execute(
                    "INSERT INTO user_profiles(telegram_id, plan_id, server_group_id, note, updated_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (101, 7, 9, "keep me", 123),
                )
                conn.commit()

            await Database(str(path)).init()

            with sqlite3.connect(path) as conn:
                row = conn.execute(
                    "SELECT telegram_id, plan_id, server_group_id, note, updated_at, display_name "
                    "FROM user_profiles WHERE telegram_id = 101"
                ).fetchone()
                self.assertEqual(row, (101, 7, 9, "keep me", 123, ""))
                self.assertEqual(
                    conn.execute(
                        "SELECT version, name, status FROM schema_migrations ORDER BY version"
                    ).fetchall(),
                    [
                        (1, "baseline_v4_14_2", "success"),
                        (2, "user_display_name_v4_21_0", "success"),
                        (3, "user_audience_groups_v4_22_0", "success"),
                        (4, "website_monitoring_v4_24_0", "success"),
                        (5, "website_watcher_lifecycle_v4_24_0", "success"),
                        (6, "client_portal_commerce_foundation_v5_0_0", "success"),
                        (7, "payment_event_reconciliation_v5_0_0", "success"),
                        (9, "telegram_stars_price_v5_0_0", "success"),
                        (9, "telegram_stars_price_v5_0_0", "success"),
                    ],
                )

    async def test_schema_v2_upgrades_to_user_groups_without_user_data_loss(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bot.sqlite3"
            await run_migrations(str(path), migrations=MIGRATIONS[:2])
            with sqlite3.connect(path) as conn:
                conn.execute(
                    "INSERT INTO users(telegram_id, email, sub_id, expiry_time, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (303, "preserve@example.com", "preserve-sub", 0, 123),
                )
                conn.commit()

            await Database(str(path)).init()

            with sqlite3.connect(path) as conn:
                self.assertEqual(
                    conn.execute(
                        "SELECT telegram_id, email FROM users WHERE telegram_id = 303"
                    ).fetchone(),
                    (303, "preserve@example.com"),
                )
                tables = {
                    row[0]
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                }
                self.assertIn("user_groups", tables)
                self.assertIn("user_group_members", tables)
                self.assertEqual(
                    conn.execute(
                        "SELECT version, name, status FROM schema_migrations ORDER BY version"
                    ).fetchall(),
                    [
                        (1, "baseline_v4_14_2", "success"),
                        (2, "user_display_name_v4_21_0", "success"),
                        (3, "user_audience_groups_v4_22_0", "success"),
                        (4, "website_monitoring_v4_24_0", "success"),
                        (5, "website_watcher_lifecycle_v4_24_0", "success"),
                        (6, "client_portal_commerce_foundation_v5_0_0", "success"),
                        (7, "payment_event_reconciliation_v5_0_0", "success"),
                        (9, "telegram_stars_price_v5_0_0", "success"),
                    ],
                )

    async def test_schema_v3_upgrades_to_website_monitoring_without_data_loss(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bot.sqlite3"
            await run_migrations(str(path), migrations=MIGRATIONS[:3])
            with sqlite3.connect(path) as conn:
                conn.execute(
                    "INSERT INTO users(telegram_id, email, sub_id, expiry_time, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (404, "keep@example.com", "keep-sub", 0, 123),
                )
                conn.commit()

            await Database(str(path)).init()

            with sqlite3.connect(path) as conn:
                self.assertEqual(
                    conn.execute(
                        "SELECT telegram_id, email FROM users WHERE telegram_id = 404"
                    ).fetchone(),
                    (404, "keep@example.com"),
                )
                tables = {
                    row[0]
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                }
                for table in (
                    "website_monitors",
                    "website_monitor_watchers",
                    "website_incidents",
                    "website_incident_notifications",
                ):
                    self.assertIn(table, tables)
                self.assertEqual(
                    conn.execute(
                        "SELECT version, name, status FROM schema_migrations ORDER BY version DESC LIMIT 1"
                    ).fetchone(),
                    (9, "telegram_stars_price_v5_0_0", "success"),
                )

    async def test_schema_v4_upgrades_watcher_lifecycle_without_data_loss(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bot.sqlite3"
            await run_migrations(str(path), migrations=MIGRATIONS[:4])
            with sqlite3.connect(path) as conn:
                conn.execute(
                    """
                    INSERT INTO website_monitors(
                        canonical_url, hostname, enabled, state, last_check_at,
                        next_check_at, last_http_status, last_latency_ms,
                        last_error_kind, consecutive_failures, created_at, updated_at
                    ) VALUES (?, ?, 1, 'up', 1, 2, 200, 12, '', 0, 3, 4)
                    """,
                    ("https://example.org/", "example.org"),
                )
                monitor_id = conn.execute(
                    "SELECT id FROM website_monitors WHERE hostname = 'example.org'"
                ).fetchone()[0]
                conn.execute(
                    """
                    INSERT INTO website_monitor_watchers(
                        monitor_id, telegram_id, notifications_enabled, created_at
                    ) VALUES (?, ?, 1, ?)
                    """,
                    (monitor_id, 707, 5),
                )
                conn.commit()

            await Database(str(path)).init()

            with sqlite3.connect(path) as conn:
                columns = {
                    row[1]
                    for row in conn.execute(
                        'PRAGMA table_info("website_monitor_watchers")'
                    ).fetchall()
                }
                self.assertIn("monitoring_enabled", columns)
                self.assertEqual(
                    conn.execute(
                        """
                        SELECT telegram_id, notifications_enabled, monitoring_enabled
                        FROM website_monitor_watchers
                        WHERE telegram_id = 707
                        """
                    ).fetchone(),
                    (707, 1, 1),
                )
                self.assertEqual(
                    conn.execute(
                        "SELECT version, name, status FROM schema_migrations ORDER BY version DESC LIMIT 1"
                    ).fetchone(),
                    (9, "telegram_stars_price_v5_0_0", "success"),
                )

    async def test_schema_v5_upgrades_to_commerce_foundation_without_legacy_payment_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bot.sqlite3"
            await run_migrations(str(path), migrations=MIGRATIONS[:5])
            with sqlite3.connect(path) as conn:
                conn.execute(
                    """
                    INSERT INTO payments(
                        telegram_id, plan_id, amount_minor, currency, status, provider,
                        external_id, note, created_by, created_at, updated_at, paid_at
                    ) VALUES (?, NULL, ?, 'RUB', 'paid', 'manual', ?, '', 1, 2, 3, 4)
                    """,
                    (808, 9900, "legacy-payment"),
                )
                conn.commit()

            await Database(str(path)).init()

            with sqlite3.connect(path) as conn:
                self.assertEqual(
                    conn.execute(
                        "SELECT telegram_id, amount_minor, status, external_id FROM payments"
                    ).fetchone(),
                    (808, 9900, "paid", "legacy-payment"),
                )
                tables = {
                    row[0] for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                }
                self.assertTrue({
                    "commerce_orders", "commerce_payments",
                    "payment_webhook_events", "entitlements",
                }.issubset(tables))
                self.assertEqual(
                    conn.execute(
                        "SELECT version, name, status FROM schema_migrations ORDER BY version DESC LIMIT 1"
                    ).fetchone(),
                    (9, "telegram_stars_price_v5_0_0", "success"),
                )

    async def test_schema_v6_adds_reconciliation_reference_without_losing_webhook_journal(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bot.sqlite3"
            await run_migrations(str(path), migrations=MIGRATIONS[:6])
            with sqlite3.connect(path) as conn:
                conn.execute(
                    """
                    INSERT INTO payment_webhook_events(
                        provider, provider_event_id, event_type, signature_valid,
                        payload_sha256, metadata_json, processing_status,
                        order_id, payment_id, received_at, applied_at, result_code
                    ) VALUES (
                        'generic_hmac', 'evt-v6', 'payment.confirmed', 1,
                        'abc', '{}', 'failed', NULL, NULL, 1, 2, 'payment_not_found'
                    )
                    """
                )
                conn.commit()

            await Database(str(path)).init()

            with sqlite3.connect(path) as conn:
                columns = [
                    row[1]
                    for row in conn.execute(
                        'PRAGMA table_info("payment_webhook_events")'
                    ).fetchall()
                ]
                self.assertIn("provider_payment_id", columns)
                self.assertEqual(
                    conn.execute(
                        """
                        SELECT provider_event_id, processing_status, result_code,
                               provider_payment_id
                        FROM payment_webhook_events WHERE provider_event_id = 'evt-v6'
                        """
                    ).fetchone(),
                    ("evt-v6", "failed", "payment_not_found", ""),
                )
                self.assertEqual(
                    conn.execute(
                        "SELECT version, name, status FROM schema_migrations ORDER BY version DESC LIMIT 1"
                    ).fetchone(),
                    (9, "telegram_stars_price_v5_0_0", "success"),
                )

    async def test_schema_v7_adds_checkout_reference_without_losing_payment_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bot.sqlite3"
            await run_migrations(str(path), migrations=MIGRATIONS[:7])
            with sqlite3.connect(path) as conn:
                conn.execute(
                    """
                    INSERT INTO commerce_orders(
                        telegram_id, plan_id, promo_code_id, amount_minor, currency,
                        status, created_at, updated_at, paid_at
                    ) VALUES (1, 2, NULL, 9900, 'RUB', 'awaiting_payment', 1, 1, 0)
                    """
                )
                order_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                conn.execute(
                    """
                    INSERT INTO commerce_payments(
                        order_id, provider, provider_payment_id, amount_minor, currency,
                        status, created_at, updated_at, confirmed_at
                    ) VALUES (?, 'generic_hmac', 'pay-v7', 9900, 'RUB', 'created', 1, 1, 0)
                    """,
                    (order_id,),
                )
                conn.commit()

            await Database(str(path)).init()

            with sqlite3.connect(path) as conn:
                columns = [
                    row[1]
                    for row in conn.execute('PRAGMA table_info("commerce_payments")').fetchall()
                ]
                self.assertIn("checkout_url", columns)
                self.assertIn("idempotency_key", columns)
                self.assertEqual(
                    conn.execute(
                        """
                        SELECT provider_payment_id, checkout_url, idempotency_key
                        FROM commerce_payments WHERE provider_payment_id = 'pay-v7'
                        """
                    ).fetchone(),
                    ("pay-v7", "", ""),
                )
                self.assertEqual(
                    conn.execute(
                        "SELECT version, name, status FROM schema_migrations ORDER BY version DESC LIMIT 1"
                    ).fetchone(),
                    (9, "telegram_stars_price_v5_0_0", "success"),
                )

    async def test_schema_v8_adds_stars_price_without_changing_existing_plan_price(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bot.sqlite3"
            await run_migrations(str(path), migrations=MIGRATIONS[:8])
            with sqlite3.connect(path) as conn:
                conn.execute(
                    """
                    INSERT INTO plans(
                        name, duration_days, traffic_gb, ip_limit,
                        price_minor, currency, server_group_id, active, created_at
                    ) VALUES ('Legacy plan', 30, 100, 2, 49900, 'RUB', NULL, 1, 1)
                    """
                )
                conn.commit()

            await Database(str(path)).init()

            with sqlite3.connect(path) as conn:
                columns = [
                    row[1] for row in conn.execute('PRAGMA table_info("plans")').fetchall()
                ]
                self.assertIn("stars_price", columns)
                self.assertEqual(
                    conn.execute(
                        "SELECT price_minor, currency, stars_price FROM plans WHERE name = 'Legacy plan'"
                    ).fetchone(),
                    (49900, "RUB", 0),
                )
                self.assertEqual(
                    conn.execute(
                        "SELECT version, name, status FROM schema_migrations ORDER BY version DESC LIMIT 1"
                    ).fetchone(),
                    (9, "telegram_stars_price_v5_0_0", "success"),
                )

    async def test_newer_schema_version_blocks_startup(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bot.sqlite3"
            await Database(str(path)).init()
            with sqlite3.connect(path) as conn:
                conn.execute(
                    """
                    INSERT INTO schema_migrations
                    (version, name, status, requires_backup, backup_path, started_at, finished_at, error)
                    VALUES (?, ?, 'success', 0, '', 1, 1, '')
                    """,
                    (CURRENT_SCHEMA_VERSION + 1, "future_schema"),
                )
                conn.commit()

            with self.assertRaises(DatabaseSchemaTooNewError):
                await Database(str(path)).init()

    async def test_failed_or_running_journal_blocks_replay(self):
        for status in ("running", "failed"):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "bot.sqlite3"
                with sqlite3.connect(path) as conn:
                    conn.execute(
                        """
                        CREATE TABLE schema_migrations (
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
                    )
                    conn.execute(
                        """
                        INSERT INTO schema_migrations
                        (version, name, status, requires_backup, backup_path, started_at, finished_at, error)
                        VALUES (1, 'baseline_v4_14_2', ?, 0, '', 1, 0, 'previous attempt')
                        """,
                        (status,),
                    )
                    conn.commit()

                with self.assertRaises(DatabaseMigrationBlockedError):
                    await Database(str(path)).init()

                with sqlite3.connect(path) as conn:
                    users = conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
                    ).fetchone()
                    self.assertIsNone(users)

    async def test_dangerous_migration_requires_verified_recovery_copy(self):
        async def migration_1(db):
            await db.execute("CREATE TABLE marker(value TEXT NOT NULL)")
            await db.execute("INSERT INTO marker VALUES ('before')")

        async def migration_2(db):
            await db.execute("INSERT INTO marker VALUES ('after')")

        first = MigrationStep(1, "seed", migration_1)
        dangerous = MigrationStep(2, "dangerous_change", migration_2, requires_backup=True)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bot.sqlite3"
            await run_migrations(str(path), migrations=(first,))

            with self.assertRaises(DatabaseMigrationBackupError):
                await run_migrations(
                    str(path),
                    migrations=(first, dangerous),
                    backup_dir=None,
                )

            with sqlite3.connect(path) as conn:
                self.assertEqual(
                    conn.execute("SELECT value FROM marker ORDER BY rowid").fetchall(),
                    [("before",)],
                )
                self.assertIsNone(
                    conn.execute(
                        "SELECT status FROM schema_migrations WHERE version = 2"
                    ).fetchone()
                )

    async def test_failed_dangerous_migration_rolls_back_and_records_backup(self):
        async def migration_1(db):
            await db.execute("CREATE TABLE marker(value TEXT NOT NULL)")
            await db.execute("INSERT INTO marker VALUES ('before')")

        async def migration_2(db):
            await db.execute("INSERT INTO marker VALUES ('should_rollback')")
            raise RuntimeError("synthetic migration failure")

        steps = (
            MigrationStep(1, "seed", migration_1),
            MigrationStep(2, "dangerous_failure", migration_2, requires_backup=True),
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "bot.sqlite3"
            backup_dir = root / "migration-backups"

            with self.assertRaises(DatabaseMigrationError):
                await run_migrations(
                    str(path),
                    migrations=steps,
                    backup_dir=str(backup_dir),
                )

            with sqlite3.connect(path) as conn:
                self.assertEqual(
                    conn.execute("SELECT value FROM marker ORDER BY rowid").fetchall(),
                    [("before",)],
                )
                status, backup_path, error = conn.execute(
                    "SELECT status, backup_path, error FROM schema_migrations WHERE version = 2"
                ).fetchone()
                self.assertEqual(status, "failed")
                self.assertIn("synthetic migration failure", error)

            recovery = Path(backup_path)
            self.assertTrue(recovery.is_file())
            self.assertEqual(recovery.parent, backup_dir)
            with sqlite3.connect(f"file:{recovery.resolve()}?mode=ro", uri=True) as conn:
                self.assertEqual(conn.execute("PRAGMA quick_check").fetchone()[0], "ok")
                self.assertEqual(
                    conn.execute("SELECT value FROM marker ORDER BY rowid").fetchall(),
                    [("before",)],
                )

            with self.assertRaises(DatabaseMigrationBlockedError):
                await run_migrations(
                    str(path),
                    migrations=steps,
                    backup_dir=str(backup_dir),
                )


if __name__ == "__main__":
    unittest.main()
