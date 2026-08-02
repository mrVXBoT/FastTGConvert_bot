from pathlib import Path

from sqlalchemy import text

from app.db.repositories import get_user_language, set_user_language
from app.db.session import build_engine, build_session_factory, create_schema
from app.handlers import build_router


def test_schema_and_router_are_created(tmp_path: Path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'test.db'}")
    try:
        create_schema(engine)
        with engine.connect() as connection:
            tables = set(
                connection.execute(
                    text(
                        "SELECT name FROM sqlite_master "
                        "WHERE type='table' ORDER BY name"
                    )
                ).scalars()
            )
        assert {"users", "files", "jobs"} <= tables
        assert build_router().name == "root"
    finally:
        engine.dispose()


def test_selected_language_is_persisted(tmp_path: Path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'test.db'}")
    try:
        create_schema(engine)
        session_factory = build_session_factory(engine)
        with session_factory() as session:
            set_user_language(session, 123456, "tester", "ar")
        with session_factory() as session:
            assert get_user_language(session, 123456) == "ar"
    finally:
        engine.dispose()


def test_database_migration(tmp_path: Path) -> None:
    """Verify that programmatic database migrations cleanly upgrade legacy schemas
    without losing data, add the unique display_id column, and support null input_file_id."""
    from sqlalchemy import create_engine, text

    from app.db.migration import run_migrations

    # Create an in-memory or file-based DB with the legacy schema manually
    db_file = tmp_path / "legacy.db"
    engine = create_engine(f"sqlite:///{db_file}")

    with engine.begin() as conn:
        conn.execute(
            text("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT
            )
        """)
        )
        conn.execute(
            text("""
            CREATE TABLE files (
                id VARCHAR(36) PRIMARY KEY,
                user_id INTEGER NOT NULL,
                original_name TEXT,
                media_type TEXT,
                size_bytes INTEGER,
                sha256 TEXT,
                storage_path TEXT,
                expires_at DATETIME,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)
        )
        # Old table: input_file_id is NOT NULL, and NO display_id column exists
        conn.execute(
            text("""
            CREATE TABLE jobs (
                id VARCHAR(36) PRIMARY KEY,
                user_id INTEGER NOT NULL,
                operation VARCHAR(64) NOT NULL,
                input_file_id VARCHAR(36) NOT NULL,
                output_file_id VARCHAR(36),
                status VARCHAR(16) NOT NULL DEFAULT 'queued',
                progress INTEGER NOT NULL DEFAULT 0,
                options_json TEXT NOT NULL DEFAULT '{}',
                error_code VARCHAR(64),
                created_at DATETIME NOT NULL,
                started_at DATETIME,
                finished_at DATETIME,
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(input_file_id) REFERENCES files(id)
            )
        """)
        )

        # Populate legacy data
        conn.execute(
            text(
                "INSERT INTO users (id, telegram_id, username) VALUES (1, 12345, 'legacy_user')"
            )
        )
        conn.execute(
            text("""
            INSERT INTO files (id, user_id, original_name, media_type, size_bytes, sha256)
            VALUES ('file-uuid-001', 1, 'legacy_input.zip', 'application/zip', 100, 'sha')
        """)
        )
        conn.execute(
            text("""
            INSERT INTO jobs (id, user_id, operation, input_file_id, created_at)
            VALUES ('job-uuid-001', 1, 'mass_message', 'file-uuid-001', '2026-08-02 22:00:00')
        """)
        )

    # Run the programmatic migration utility
    run_migrations(engine)

    # Verify schema and data persistence
    with engine.connect() as conn:
        # Check if columns are updated
        cursor = conn.execute(text("PRAGMA table_info(jobs)"))
        columns = {row[1]: row for row in cursor.fetchall()}

        # Verify display_id column exists
        assert "display_id" in columns

        # Verify input_file_id is nullable (notnull is 0 in table_info)
        assert columns["input_file_id"][3] == 0

        # Verify legacy job was successfully migrated and display_id populated
        job_row = conn.execute(
            text("SELECT id, display_id, input_file_id FROM jobs")
        ).fetchone()
        assert job_row is not None
        assert job_row[0] == "job-uuid-001"
        assert job_row[1] == "MM-LEGACY-0001"
        assert job_row[2] == "file-uuid-001"

        # Verify new jobs can be created with nullable input_file_id
        conn.execute(
            text("""
            INSERT INTO jobs (id, display_id, user_id, operation, input_file_id, created_at)
            VALUES ('job-uuid-002', 'MM-20260802-NEW001', 1, 'mass_message', NULL, '2026-08-02 23:00:00')
        """)
        )
        new_job = conn.execute(
            text(
                "SELECT id, display_id, input_file_id FROM jobs WHERE id='job-uuid-002'"
            )
        ).fetchone()
        assert new_job is not None
        assert new_job[2] is None
