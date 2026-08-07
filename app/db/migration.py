import logging
from typing import Any

from sqlalchemy import Engine

LOGGER = logging.getLogger(__name__)


def migrate_to_v1(cursor: Any) -> None:
    """Migration v1:
    - Adds unique display_id column to jobs table.
    - Makes input_file_id column nullable.
    - Preserves legacy job records by generating fallback legacy display IDs.
    """
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='jobs'")
    if not cursor.fetchone():
        return

    cursor.execute("PRAGMA table_info(jobs)")
    columns = [row[1] for row in cursor.fetchall()]

    if "display_id" in columns:
        return

    LOGGER.info("Applying migration v1: upgrading jobs schema...")

    cursor.execute("""
        CREATE TABLE jobs_new (
            id VARCHAR(36) NOT NULL PRIMARY KEY,
            display_id VARCHAR(32) UNIQUE,
            user_id INTEGER NOT NULL,
            operation VARCHAR(64) NOT NULL,
            input_file_id VARCHAR(36),
            output_file_id VARCHAR(36),
            status VARCHAR(16) NOT NULL DEFAULT 'queued',
            progress INTEGER NOT NULL DEFAULT 0,
            options_json TEXT NOT NULL DEFAULT '{}',
            error_code VARCHAR(64),
            created_at DATETIME NOT NULL,
            started_at DATETIME,
            finished_at DATETIME,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(input_file_id) REFERENCES files(id),
            FOREIGN KEY(output_file_id) REFERENCES files(id)
        )
    """)

    cursor.execute("""
        INSERT INTO jobs_new (
            id, user_id, operation, input_file_id, output_file_id,
            status, progress, options_json, error_code,
            created_at, started_at, finished_at
        )
        SELECT 
            id, user_id, operation, input_file_id, output_file_id,
            status, progress, options_json, error_code,
            created_at, started_at, finished_at
        FROM jobs
    """)

    cursor.execute("SELECT id FROM jobs_new WHERE display_id IS NULL")
    rows = cursor.fetchall()
    for idx, row in enumerate(rows):
        job_uuid = row[0]
        legacy_id = f"MM-LEGACY-{idx + 1:04d}"
        cursor.execute(
            "UPDATE jobs_new SET display_id = ? WHERE id = ?",
            (legacy_id, job_uuid),
        )

    cursor.execute("CREATE INDEX IF NOT EXISTS ix_jobs_user_id ON jobs_new(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_jobs_status ON jobs_new(status)")

    cursor.execute("PRAGMA foreign_keys=OFF")
    cursor.execute("DROP TABLE jobs")
    cursor.execute("ALTER TABLE jobs_new RENAME TO jobs")
    cursor.execute("PRAGMA foreign_keys=ON")


def migrate_to_v2(cursor: Any) -> None:
    """Migration v2:
    - Adds proxy column to users table if missing.
    """
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    if not cursor.fetchone():
        return

    cursor.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in cursor.fetchall()]

    if "proxy" not in columns:
        LOGGER.info("Applying migration v2: adding proxy column to users table...")
        cursor.execute("ALTER TABLE users ADD COLUMN proxy TEXT")


def migrate_to_v3(cursor: Any) -> None:
    """Migration v3:
    - Adds structured proxy columns to users table.
    """
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    if not cursor.fetchone():
        return

    cursor.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in cursor.fetchall()]

    new_cols = {
        "proxy_type": "VARCHAR(10)",
        "proxy_host": "VARCHAR(255)",
        "proxy_port": "INTEGER",
        "proxy_username": "VARCHAR(255)",
        "proxy_password_encrypted": "TEXT",
    }

    for col_name, col_type in new_cols.items():
        if col_name not in columns:
            LOGGER.info(
                "Applying migration v3: adding %s column to users table...",
                col_name,
            )
            cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")


def migrate_to_v4(cursor: Any) -> None:
    """Migration v4:
    - Adds is_vip & vip_expires_at to users table.
    - Creates admin_users, statistic_events, force_join_channels, feature_gates, vip_plans, payment_settings tables.
    - Seeds default feature gates and initial VIP plans.
    """
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    if cursor.fetchone():
        cursor.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cursor.fetchall()]
        if "is_vip" not in columns:
            LOGGER.info("Applying migration v4: adding is_vip column to users...")
            cursor.execute("ALTER TABLE users ADD COLUMN is_vip BOOLEAN DEFAULT 0")
        if "vip_expires_at" not in columns:
            LOGGER.info("Applying migration v4: adding vip_expires_at column to users...")
            cursor.execute("ALTER TABLE users ADD COLUMN vip_expires_at DATETIME")

    # 1. Create admin_users
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admin_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id BIGINT UNIQUE NOT NULL,
            role VARCHAR(16) NOT NULL DEFAULT 'ADMIN',
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_admin_users_telegram_id ON admin_users(telegram_id)")

    # 2. Create statistic_events
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS statistic_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            event_type VARCHAR(32) NOT NULL,
            metadata_json TEXT DEFAULT '{}',
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_statistic_events_event_type ON statistic_events(event_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_statistic_events_created_at ON statistic_events(created_at)")

    # 3. Create force_join_channels
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS force_join_channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id VARCHAR(64) UNIQUE NOT NULL,
            title VARCHAR(255) NOT NULL,
            username VARCHAR(64),
            invite_link TEXT,
            channel_type VARCHAR(16) NOT NULL DEFAULT 'public',
            is_active BOOLEAN NOT NULL DEFAULT 1,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 4. Create feature_gates
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS feature_gates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            feature_key VARCHAR(32) UNIQUE NOT NULL,
            title VARCHAR(64) NOT NULL,
            access_level VARCHAR(16) NOT NULL DEFAULT 'FREE',
            is_enabled BOOLEAN NOT NULL DEFAULT 1
        )
    """)

    # Seed all bot features — INSERT OR IGNORE preserves existing VIP_ONLY settings
    all_features = [
        # Session & Account Tools
        ("session_check",     "✅ Session Checker",               "FREE", 1),
        ("spam_check",        "🚫 Spam & Restriction Checker",    "FREE", 1),
        ("check_contacts",    "📋 Contact Checker",               "FREE", 1),
        ("account_age",       "🎂 Account Age Checker",           "FREE", 1),
        ("account_to_txt",    "📄 Account to TXT Export",         "FREE", 1),
        ("analyze",           "🔍 Session Analyzer",              "FREE", 1),
        # Conversion Tools
        ("session_to_tdata",  "🔄 Session → TData Converter",    "FREE", 1),
        ("tdata_to_session",  "🔄 TData → Session Converter",    "FREE", 1),
        ("session_to_json",   "📦 Session → JSON Export",        "FREE", 1),
        ("file_merge",        "🗂️ File Merge",                    "FREE", 1),
        ("split",             "✂️ Session Split",                 "FREE", 1),
        # Security Tools
        ("change_2fa",        "🔐 Change 2FA Password",          "FREE", 1),
        ("disable_2fa",       "🔓 Disable 2FA",                  "FREE", 1),
        ("reset_2fa",         "♻️ Reset 2FA",                    "FREE", 1),
        # Messaging & Channel Tools
        ("mass_message",      "📢 Mass Message Sender",           "FREE", 1),
        ("clean_chat",        "🧹 Chat Cleaner",                  "FREE", 1),
        ("channel_join",      "📌 Channel Join",                  "FREE", 1),
        ("leave_channel",     "🚪 Channel Leave",                 "FREE", 1),
        ("kill_sessions",     "💀 Kill Active Sessions",          "FREE", 1),
        # Contact Tools
        ("delete_contact",    "🗑️ Delete Contact",               "FREE", 1),
        ("clear_contact",     "🧽 Clear All Contacts",            "FREE", 1),
        ("list_checker",      "📝 List Checker",                  "FREE", 1),
        # Profile & Settings Tools
        ("privacy_settings",  "🔒 Privacy Settings Manager",     "FREE", 1),
        ("privacy_check",     "🛡️ Privacy Check",                "FREE", 1),
        ("profile_setup",     "👤 Profile Setup",                 "FREE", 1),
        # OTP Tool
        ("read_otp",          "📱 OTP Reader",                    "FREE", 1),
        # Generation Tools
        ("fresh_session",     "🆕 Fresh Session Generator",      "FREE", 1),
    ]
    cursor.executemany(
        "INSERT OR IGNORE INTO feature_gates (feature_key, title, access_level, is_enabled) VALUES (?, ?, ?, ?)",
        all_features,
    )

    # 5. Create vip_plans
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vip_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(64) NOT NULL,
            months INTEGER NOT NULL DEFAULT 1,
            price FLOAT NOT NULL DEFAULT 10.0,
            currency VARCHAR(8) NOT NULL DEFAULT 'USD',
            is_active BOOLEAN NOT NULL DEFAULT 1,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Seed initial default VIP plans
    cursor.execute("SELECT COUNT(*) FROM vip_plans")
    if cursor.fetchone()[0] == 0:
        default_plans = [
            ("1 Month VIP", 1, 10.0, "USD", 1),
            ("3 Months VIP", 3, 25.0, "USD", 1),
            ("6 Months VIP", 6, 50.0, "USD", 1),
            ("12 Months VIP", 12, 80.0, "USD", 1),
        ]
        cursor.executemany(
            "INSERT INTO vip_plans (name, months, price, currency, is_active, created_at) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
            default_plans,
        )

    # 6. Create payment_settings
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payment_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            manual_enabled BOOLEAN NOT NULL DEFAULT 1,
            binance_id VARCHAR(128),
            trc20_address VARCHAR(255),
            bep20_address VARCHAR(255),
            auto_enabled BOOLEAN NOT NULL DEFAULT 0,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("SELECT COUNT(*) FROM payment_settings")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO payment_settings (manual_enabled, auto_enabled, updated_at) VALUES (1, 0, CURRENT_TIMESTAMP)")


def migrate_to_v5(cursor: Any) -> None:
    """Migration v5:
    - Creates payments table.
    - Creates user_vip_subscriptions table.
    - Creates indexes for payments, user_vip_subscriptions, and statistic_events.
    """
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            plan_id INTEGER NOT NULL,
            amount FLOAT NOT NULL,
            currency VARCHAR(8) NOT NULL DEFAULT 'USD',
            payment_method VARCHAR(32) NOT NULL,
            status VARCHAR(16) NOT NULL DEFAULT 'pending',
            transaction_id VARCHAR(128),
            receipt_file_id VARCHAR(255),
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            confirmed_at DATETIME,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(plan_id) REFERENCES vip_plans(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_payments_user_id ON payments(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_payments_status ON payments(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_payments_created_at ON payments(created_at)")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_vip_subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            plan_id INTEGER,
            payment_id INTEGER,
            started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            expires_at DATETIME NOT NULL,
            status VARCHAR(16) NOT NULL DEFAULT 'active',
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(plan_id) REFERENCES vip_plans(id),
            FOREIGN KEY(payment_id) REFERENCES payments(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_user_vip_subscriptions_user_id ON user_vip_subscriptions(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_user_vip_subscriptions_expires_at ON user_vip_subscriptions(expires_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_user_vip_subscriptions_status ON user_vip_subscriptions(status)")

    cursor.execute("CREATE INDEX IF NOT EXISTS ix_statistic_events_type_created ON statistic_events(event_type, created_at)")


def migrate_to_v6(cursor: Any) -> None:
    """Migration v6:
    - Creates broadcast_jobs table for persistent Queue/Worker execution across bot restarts.
    - Creates system_settings table for dynamic system configurations (e.g. support_contact).
    """
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS broadcast_jobs (
            id VARCHAR(36) PRIMARY KEY,
            message_type VARCHAR(16) NOT NULL DEFAULT 'custom',
            from_chat_id BIGINT,
            message_id INTEGER,
            text TEXT,
            photo VARCHAR(255),
            video VARCHAR(255),
            document VARCHAR(255),
            status VARCHAR(16) NOT NULL DEFAULT 'pending',
            total_users INTEGER NOT NULL DEFAULT 0,
            sent_count INTEGER NOT NULL DEFAULT 0,
            failed_count INTEGER NOT NULL DEFAULT 0,
            current_index INTEGER NOT NULL DEFAULT 0,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_broadcast_jobs_status ON broadcast_jobs(status)")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_settings (
            key VARCHAR(64) PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("SELECT COUNT(*) FROM system_settings WHERE key='support_contact'")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO system_settings (key, value, updated_at) VALUES ('support_contact', '@support', CURRENT_TIMESTAMP)"
        )


def migrate_to_v7(cursor: Any) -> None:
    """Migration v7:
    - Adds referred_by column to users table.
    - Creates referrals, referral_tiers, referral_rewards tables.
    - Seeds default referral reward tiers and referral_enabled setting.
    """
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    if cursor.fetchone():
        cursor.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cursor.fetchall()]
        if "referred_by" not in columns:
            LOGGER.info("Applying migration v7: adding referred_by column to users...")
            cursor.execute("ALTER TABLE users ADD COLUMN referred_by BIGINT")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_users_referred_by ON users(referred_by)")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_telegram_id BIGINT NOT NULL,
            referred_telegram_id BIGINT UNIQUE NOT NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_referrals_referrer ON referrals(referrer_telegram_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_referrals_created_at ON referrals(created_at)")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS referral_tiers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            refs_required INTEGER UNIQUE NOT NULL,
            reward_days INTEGER NOT NULL DEFAULT 1,
            is_active BOOLEAN NOT NULL DEFAULT 1,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("SELECT COUNT(*) FROM referral_tiers")
    if cursor.fetchone()[0] == 0:
        default_tiers = [
            (1, 1),
            (7, 7),
            (15, 15),
            (30, 30),
        ]
        cursor.executemany(
            "INSERT INTO referral_tiers (refs_required, reward_days, is_active, created_at) VALUES (?, ?, 1, CURRENT_TIMESTAMP)",
            default_tiers,
        )

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS referral_rewards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_telegram_id BIGINT NOT NULL,
            tier_id INTEGER,
            days INTEGER NOT NULL DEFAULT 0,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(tier_id) REFERENCES referral_tiers(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_referral_rewards_referrer ON referral_rewards(referrer_telegram_id)")

    cursor.execute("SELECT COUNT(*) FROM system_settings WHERE key='referral_enabled'")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO system_settings (key, value, updated_at) VALUES ('referral_enabled', '1', CURRENT_TIMESTAMP)"
        )


def migrate_to_v8(cursor: Any) -> None:
    """Migration v8:
    - Adds auto wallet addresses (auto_trc20_address, auto_bep20_address) to payment_settings.
    - Adds auto payment order columns (order_code, network, wallet_address, expected_amount, expires_at) to payments.
    - Creates indexes for payments.order_code and payments.expires_at.
    """
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='payment_settings'")
    if cursor.fetchone():
        cursor.execute("PRAGMA table_info(payment_settings)")
        columns = [row[1] for row in cursor.fetchall()]

        new_cols = {
            "auto_trc20_address": "VARCHAR(255)",
            "auto_bep20_address": "VARCHAR(255)",
        }

        for col_name, col_type in new_cols.items():
            if col_name not in columns:
                LOGGER.info(
                    "Applying migration v8: adding %s column to payment_settings table...",
                    col_name,
                )
                cursor.execute(f"ALTER TABLE payment_settings ADD COLUMN {col_name} {col_type}")

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='payments'")
    if cursor.fetchone():
        cursor.execute("PRAGMA table_info(payments)")
        columns = [row[1] for row in cursor.fetchall()]

        new_cols = {
            "order_code": "VARCHAR(32)",
            "network": "VARCHAR(16)",
            "wallet_address": "VARCHAR(255)",
            "expected_amount": "FLOAT",
            "expires_at": "DATETIME",
        }

        for col_name, col_type in new_cols.items():
            if col_name not in columns:
                LOGGER.info(
                    "Applying migration v8: adding %s column to payments table...",
                    col_name,
                )
                cursor.execute(f"ALTER TABLE payments ADD COLUMN {col_name} {col_type}")

        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_payments_order_code ON payments(order_code)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_payments_expires_at ON payments(expires_at)")


def migrate_to_v9(cursor: Any) -> None:
    """Migration v9:
    - Deduplicates any legacy live pending auto orders that share the same
      (wallet_address, network, expected_amount), keeping the oldest.
    - Creates a partial unique index enforcing that live pending auto orders can
      never collide on (wallet_address, network, expected_amount), so a single
      on-chain transfer can never be claimed by two orders.
    """
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='payments'")
    if not cursor.fetchone():
        return
    cursor.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='index' "
        "AND name='ux_payments_pending_auto_amount'"
    )
    if cursor.fetchone()[0]:
        return

    LOGGER.info(
        "Applying migration v9: deduplicating colliding pending auto orders..."
    )
    cursor.execute(
        """
        UPDATE payments SET status = 'cancelled'
        WHERE status = 'pending'
          AND network IN ('trc20', 'bep20')
          AND expected_amount IS NOT NULL
          AND wallet_address IS NOT NULL
          AND id NOT IN (
              SELECT MIN(id)
              FROM payments
              WHERE status = 'pending'
                AND network IN ('trc20', 'bep20')
                AND expected_amount IS NOT NULL
                AND wallet_address IS NOT NULL
              GROUP BY wallet_address, network, expected_amount
          )
        """
    )
    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_payments_pending_auto_amount
        ON payments(wallet_address, network, expected_amount)
        WHERE status = 'pending'
        """
    )


def migrate_to_v10(cursor: Any) -> None:
    """Migration v10:
    - Deduplicates legacy duplicate subscription rows created through the old
      non-atomic activate path (keep the oldest per payment_id).
    - Creates a unique index on `user_vip_subscriptions.payment_id` so a single
      payment can never be granted VIP twice even across racing processes.
    """
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name='user_vip_subscriptions'"
    )
    if not cursor.fetchone():
        return
    cursor.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='index' "
        "AND name='ux_user_vip_subscriptions_payment'"
    )
    if cursor.fetchone()[0]:
        return

    LOGGER.info(
        "Applying migration v10: deduplicating double-granted subscriptions..."
    )
    cursor.execute(
        """
        DELETE FROM user_vip_subscriptions
        WHERE payment_id IS NOT NULL
          AND id NOT IN (
              SELECT MIN(id)
              FROM user_vip_subscriptions
              WHERE payment_id IS NOT NULL
              GROUP BY payment_id
          )
        """
    )
    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_user_vip_subscriptions_payment
        ON user_vip_subscriptions(payment_id)
        WHERE payment_id IS NOT NULL
        """
    )


# Registry of migrations mapped to target version numbers
MIGRATIONS = {
    1: migrate_to_v1,
    2: migrate_to_v2,
    3: migrate_to_v3,
    4: migrate_to_v4,
    5: migrate_to_v5,
    6: migrate_to_v6,
    7: migrate_to_v7,
    8: migrate_to_v8,
    9: migrate_to_v9,
    10: migrate_to_v10,
}
LATEST_VERSION = 10


def run_migrations(engine: Engine) -> None:
    """Programmatic migration runner for SQLite version-by-version using a registry."""
    connection = engine.raw_connection()
    try:
        cursor = connection.cursor()

        cursor.execute("PRAGMA user_version")
        row = cursor.fetchone()
        db_version = row[0] if row else 0

        if db_version < LATEST_VERSION:
            try:
                from app.db.backup import perform_database_backup
                db_file_str = str(engine.url.database) if engine.url and engine.url.database else "data/bot.db"
                perform_database_backup(db_path=db_file_str)
            except Exception as backup_err:  # noqa: BLE001
                LOGGER.warning("Pre-migration backup skipped: %s", backup_err)

            for version in range(db_version + 1, LATEST_VERSION + 1):
                cursor.execute("BEGIN TRANSACTION")
                try:
                    LOGGER.info(
                        "Running database schema migration to version %d...",
                        version,
                    )
                    MIGRATIONS[version](cursor)
                    cursor.execute(f"PRAGMA user_version = {version}")
                    connection.commit()
                    LOGGER.info(
                        "Database successfully migrated to version %d.", version
                    )
                except Exception:
                    connection.rollback()
                    raise

    except Exception:
        LOGGER.exception("Schema migration runner encountered an error.")
        raise
    finally:
        connection.close()
