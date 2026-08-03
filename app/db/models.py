from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(64))
    language: Mapped[str] = mapped_column(String(8), default="en")
    status: Mapped[str] = mapped_column(String(16), default="active")
    proxy: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    proxy_type: Mapped[str | None] = mapped_column(String(10), nullable=True, default=None)
    proxy_host: Mapped[str | None] = mapped_column(String(255), nullable=True, default=None)
    proxy_port: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    proxy_username: Mapped[str | None] = mapped_column(String(255), nullable=True, default=None)
    proxy_password_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    is_vip: Mapped[bool] = mapped_column(Boolean, default=False)
    vip_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class FileRecord(Base):
    __tablename__ = "files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    telegram_file_id: Mapped[str | None] = mapped_column(Text)
    original_name: Mapped[str] = mapped_column(String(255))
    media_type: Mapped[str] = mapped_column(String(128))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    storage_path: Mapped[str] = mapped_column(Text)
    purpose: Mapped[str] = mapped_column(String(16), default="input")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    display_id: Mapped[str | None] = mapped_column(String(32), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    operation: Mapped[str] = mapped_column(String(64))
    input_file_id: Mapped[str | None] = mapped_column(
        ForeignKey("files.id"), nullable=True
    )
    output_file_id: Mapped[str | None] = mapped_column(
        ForeignKey("files.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    options_json: Mapped[str] = mapped_column(Text, default="{}")
    error_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    role: Mapped[str] = mapped_column(String(16), default="ADMIN")  # OWNER, SUPER_ADMIN, ADMIN, SUPPORT
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class StatisticEvent(Base):
    __tablename__ = "statistic_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(32), index=True)  # USER_REGISTER, VIP_PURCHASE, TASK_START, TASK_SUCCESS, TASK_FAILED
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    __table_args__ = (
        Index("ix_statistic_events_type_created", "event_type", "created_at"),
    )


class ForceJoinChannel(Base):
    __tablename__ = "force_join_channels"

    id: Mapped[int] = mapped_column(primary_key=True)
    channel_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    invite_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    channel_type: Mapped[str] = mapped_column(String(16), default="public")  # public, private
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FeatureGate(Base):
    __tablename__ = "feature_gates"

    id: Mapped[int] = mapped_column(primary_key=True)
    feature_key: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(64))
    access_level: Mapped[str] = mapped_column(String(16), default="FREE")  # FREE, VIP_ONLY
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class VIPPlan(Base):
    __tablename__ = "vip_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    months: Mapped[int] = mapped_column(Integer, default=1)
    price: Mapped[float] = mapped_column(Float, default=10.0)
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PaymentSetting(Base):
    __tablename__ = "payment_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    manual_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    binance_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    trc20_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bep20_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    auto_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("vip_plans.id"), index=True)
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    payment_method: Mapped[str] = mapped_column(String(32))  # manual, binance, trc20, bep20, auto
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)  # pending, paid, rejected, refunded, cancelled
    transaction_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    receipt_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UserVIPSubscription(Base):
    __tablename__ = "user_vip_subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    plan_id: Mapped[int | None] = mapped_column(ForeignKey("vip_plans.id"), nullable=True, index=True)
    payment_id: Mapped[int | None] = mapped_column(ForeignKey("payments.id"), nullable=True, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)  # active, expired, cancelled
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class BroadcastJobRecord(Base):
    __tablename__ = "broadcast_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    message_type: Mapped[str] = mapped_column(String(16), default="custom")  # custom, forward
    from_chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    video: Mapped[str | None] = mapped_column(String(255), nullable=True)
    document: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)  # pending, running, completed, cancelled, paused
    total_users: Mapped[int] = mapped_column(Integer, default=0)
    sent_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    current_index: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SystemSetting(Base):
    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

