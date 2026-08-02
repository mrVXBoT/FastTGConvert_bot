from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import User


def upsert_user(session: Session, telegram_id: int, username: str | None) -> User:
    user = session.scalar(select(User).where(User.telegram_id == telegram_id))
    if user is None:
        user = User(telegram_id=telegram_id, username=username)
        session.add(user)
    else:
        user.username = username
        user.last_seen_at = datetime.now(UTC)
    session.commit()
    session.refresh(user)
    return user


def set_user_language(
    session: Session, telegram_id: int, username: str | None, language: str
) -> User:
    user = upsert_user(session, telegram_id, username)
    user.language = language
    session.commit()
    session.refresh(user)
    return user


def get_user_language(session: Session, telegram_id: int) -> str:
    user = session.scalar(select(User).where(User.telegram_id == telegram_id))
    return user.language if user is not None else "en"


def generate_unique_display_id(session: Session, prefix: str = "MM") -> str:
    """Generate a collision-proof unique display ID by verifying against the database."""
    from uuid import uuid4

    from app.db.models import Job

    now_date_str = datetime.now(UTC).strftime("%Y%m%d")
    for _ in range(10):
        unique_suffix = uuid4().hex[:8].upper()
        candidate = f"{prefix}-{now_date_str}-{unique_suffix}"
        exists = session.scalar(select(Job).where(Job.display_id == candidate))
        if not exists:
            return candidate
    return f"{prefix}-{now_date_str}-{uuid4().hex[:12].upper()}"
