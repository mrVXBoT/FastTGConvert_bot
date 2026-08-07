"""app/db/backup.py — Automated online SQLite database backup, restore, and retention manager."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone

UTC = timezone.utc  # noqa: UP017
from pathlib import Path

LOGGER = logging.getLogger(__name__)


def sqlite_db_path_from_url(database_url: str) -> Path | None:
    """Resolve the on-disk SQLite path from a SQLAlchemy ``database_url``.

    Returns ``None`` for non-SQLite backends (backup via sqlite3 is not
    applicable there) or for URLs that do not decode to a file path.
    """
    if not database_url:
        return None
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        LOGGER.debug("Backup skipped: non-SQLite database URL (%s)", database_url)
        return None
    path_part = database_url[len(prefix):]
    # sqlite:////absolute/path -> /absolute/path (4th slash is the root)
    if path_part.startswith("/"):
        return Path(path_part)
    return Path(path_part or "data/bot.db")


def perform_database_backup(
    db_path: Path | str | None = "data/bot.db",
    backup_dir: Path | str = "data/backups",
    max_backups: int = 7,
) -> Path | None:
    """Perform a thread-safe online SQLite database backup and maintain retention limits.

    Uses sqlite3.backup() API to ensure non-blocking, transactionally consistent backups.
    """
    if db_path is None:
        LOGGER.warning("No resolvable database path, skipping backup.")
        return None
    db_file = Path(db_path)
    if not db_file.exists():
        LOGGER.warning("Database file %s does not exist, skipping backup.", db_file)
        return None

    target_dir = Path(backup_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
    backup_file = target_dir / f"bot_backup_{timestamp}.db"

    try:
        source_conn = sqlite3.connect(db_file)
        dest_conn = sqlite3.connect(backup_file)
        with dest_conn:
            source_conn.backup(dest_conn)
        source_conn.close()
        dest_conn.close()
        LOGGER.info("Online database backup created successfully: %s", backup_file)

        # Enforce retention policy
        existing_backups = sorted(
            target_dir.glob("bot_backup_*.db"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if len(existing_backups) > max_backups:
            for old_backup in existing_backups[max_backups:]:
                try:
                    old_backup.unlink()
                    LOGGER.info("Removed old database backup: %s", old_backup)
                except Exception as exc:  # noqa: BLE001
                    LOGGER.warning("Failed to remove old backup %s: %s", old_backup, exc)

        return backup_file
    except Exception as exc:  # noqa: BLE001
        LOGGER.error("Failed to perform online database backup: %s", exc)
        return None


def restore_database_backup(
    backup_path: Path | str,
    target_db_path: Path | str = "data/bot.db",
) -> bool:
    """Restore database state from a specified backup file using sqlite3.backup()."""
    b_file = Path(backup_path)
    if not b_file.exists():
        LOGGER.error("Backup file %s does not exist. Cannot restore.", b_file)
        return False

    t_file = Path(target_db_path)
    t_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        backup_conn = sqlite3.connect(b_file)
        target_conn = sqlite3.connect(t_file)
        with target_conn:
            backup_conn.backup(target_conn)
        backup_conn.close()
        target_conn.close()
        LOGGER.info("Database successfully restored from %s to %s", b_file, t_file)
        return True
    except Exception as exc:  # noqa: BLE001
        LOGGER.error("Failed to restore database from backup %s: %s", b_file, exc)
        return False
