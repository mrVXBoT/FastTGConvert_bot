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
    # 1. Check if table 'jobs' exists first (if not, metadata.create_all handles it)
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='jobs'")
    if not cursor.fetchone():
        return

    # 2. Check if we already migrated (check if display_id exists in jobs table)
    cursor.execute("PRAGMA table_info(jobs)")
    columns = [row[1] for row in cursor.fetchall()]

    if "display_id" in columns:
        return

    LOGGER.info("Applying migration v1: upgrading jobs schema...")

    # Create the new schema table
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

    # Copy existing data
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

    # Populate display_id for legacy jobs with unique fallback values
    cursor.execute("SELECT id FROM jobs_new WHERE display_id IS NULL")
    rows = cursor.fetchall()
    for idx, row in enumerate(rows):
        job_uuid = row[0]
        legacy_id = f"MM-LEGACY-{idx + 1:04d}"
        cursor.execute(
            "UPDATE jobs_new SET display_id = ? WHERE id = ?",
            (legacy_id, job_uuid),
        )

    # Recreate indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_jobs_user_id ON jobs_new(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_jobs_status ON jobs_new(status)")

    # Disable foreign keys temporarily, drop old table, rename new table
    cursor.execute("PRAGMA foreign_keys=OFF")
    cursor.execute("DROP TABLE jobs")
    cursor.execute("ALTER TABLE jobs_new RENAME TO jobs")
    cursor.execute("PRAGMA foreign_keys=ON")


# Registry of migrations mapped to target version numbers
MIGRATIONS = {
    1: migrate_to_v1,
}
LATEST_VERSION = 1


def run_migrations(engine: Engine) -> None:
    """Programmatic migration runner for SQLite version-by-version using a registry."""
    connection = engine.raw_connection()
    try:
        cursor = connection.cursor()

        # Check database schema version first
        cursor.execute("PRAGMA user_version")
        row = cursor.fetchone()
        db_version = row[0] if row else 0

        # Execute migrations sequentially if database version is behind LATEST_VERSION
        if db_version < LATEST_VERSION:
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
