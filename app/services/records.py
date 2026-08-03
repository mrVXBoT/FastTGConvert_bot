from datetime import datetime, timedelta, timezone

UTC = timezone.utc  # noqa: UP017
from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from app.db.models import FileRecord, Job
from app.services.files import FileAnalysis


def create_file_and_job(
    session: Session,
    *,
    user_id: int,
    telegram_file_id: str,
    original_name: str,
    storage_path: Path,
    analysis: FileAnalysis,
    operation: str,
    retention_minutes: int,
) -> tuple[FileRecord, Job]:
    file_record = FileRecord(
        id=str(uuid4()),
        user_id=user_id,
        telegram_file_id=telegram_file_id,
        original_name=original_name,
        media_type=analysis.media_type,
        size_bytes=analysis.size_bytes,
        sha256=analysis.sha256,
        storage_path=str(storage_path),
        purpose="input",
        expires_at=datetime.now(UTC) + timedelta(minutes=retention_minutes),
    )
    job = Job(
        id=str(uuid4()),
        user_id=user_id,
        operation=operation,
        input_file_id=file_record.id,
        status="running",
        progress=10,
        started_at=datetime.now(UTC),
    )
    session.add_all([file_record, job])
    session.commit()
    return file_record, job


def finish_job(session: Session, job: Job, error_code: str | None = None) -> None:
    job.status = "failed" if error_code else "completed"
    job.error_code = error_code
    job.progress = 100 if error_code is None else job.progress
    job.finished_at = datetime.now(UTC)
    session.commit()
