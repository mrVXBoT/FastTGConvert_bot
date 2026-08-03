from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.models import (
    AdminUser,
    FeatureGate,
    ForceJoinChannel,
    Job,
    Payment,
    PaymentSetting,
    StatisticEvent,
    User,
    UserVIPSubscription,
    VIPPlan,
)


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


def set_user_proxy(
    session: Session, telegram_id: int, proxy: str | None, username: str | None = None
) -> User:
    from app.services.proxy import encrypt_proxy_password, parse_telethon_proxy

    user = upsert_user(session, telegram_id, username)
    if not proxy:
        user.proxy = None
        user.proxy_type = None
        user.proxy_host = None
        user.proxy_port = None
        user.proxy_username = None
        user.proxy_password_encrypted = None
    else:
        parsed = parse_telethon_proxy(proxy)
        if parsed:
            ptype, host, port, _, puser, ppass = parsed
            enc_pass = encrypt_proxy_password(ppass)
            user.proxy_type = ptype
            user.proxy_host = host
            user.proxy_port = port
            user.proxy_username = puser
            user.proxy_password_encrypted = enc_pass
            user.proxy = proxy

    session.commit()
    session.refresh(user)
    return user


def get_user_proxy(session: Session, telegram_id: int) -> str | None:
    user = session.scalar(select(User).where(User.telegram_id == telegram_id))
    if user is None:
        return None
    if user.proxy_host and user.proxy_port and user.proxy_type:
        auth_str = ""
        if user.proxy_username or user.proxy_password_encrypted:
            pass_str = user.proxy_password_encrypted or ""
            user_str = user.proxy_username or ""
            auth_str = f"{user_str}:{pass_str}@"
        return f"{user.proxy_type}://{auth_str}{user.proxy_host}:{user.proxy_port}"
    return user.proxy


def generate_unique_display_id(session: Session, prefix: str = "MM") -> str:
    """Generate a collision-proof unique display ID by verifying against the database."""
    from uuid import uuid4

    now_date_str = datetime.now(UTC).strftime("%Y%m%d")
    for _ in range(10):
        unique_suffix = uuid4().hex[:8].upper()
        candidate = f"{prefix}-{now_date_str}-{unique_suffix}"
        exists = session.scalar(select(Job).where(Job.display_id == candidate))
        if not exists:
            return candidate
    return f"{prefix}-{now_date_str}-{uuid4().hex[:12].upper()}"


# ==========================================
# 👥 USER MANAGEMENT REPOSITORY
# ==========================================

def get_user_by_telegram_id(session: Session, telegram_id: int) -> User | None:
    return session.scalar(select(User).where(User.telegram_id == telegram_id))


def get_users_paginated(
    session: Session, page: int = 1, page_size: int = 10, search_query: str | None = None
) -> tuple[list[User], int]:
    stmt = select(User)
    if search_query:
        query_str = f"%{search_query.strip()}%"
        if search_query.isdigit():
            stmt = stmt.where(User.telegram_id == int(search_query))
        else:
            stmt = stmt.where(or_(User.username.ilike(query_str)))

    total_count = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    users = list(
        session.scalars(
            stmt.order_by(User.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return users, total_count


def set_user_ban_status(session: Session, telegram_id: int, banned: bool) -> bool:
    user = session.scalar(select(User).where(User.telegram_id == telegram_id))
    if not user:
        return False
    user.status = "banned" if banned else "active"
    session.commit()
    return True


def grant_user_vip(session: Session, telegram_id: int, months: int = 1) -> User | None:
    user = session.scalar(select(User).where(User.telegram_id == telegram_id))
    if not user:
        return None
    now = datetime.now(UTC)
    current_expiry = user.vip_expires_at if (user.vip_expires_at and user.vip_expires_at > now) else now
    expires_at = current_expiry + timedelta(days=months * 30)

    # 1. Create UserVIPSubscription record
    sub = UserVIPSubscription(
        user_id=user.id,
        plan_id=None,
        payment_id=None,
        started_at=now,
        expires_at=expires_at,
        status="active",
    )
    session.add(sub)

    # 2. Update user cache flags for backward compatibility
    user.is_vip = True
    user.vip_expires_at = expires_at

    session.commit()
    session.refresh(user)
    return user


def revoke_user_vip(session: Session, telegram_id: int) -> bool:
    user = session.scalar(select(User).where(User.telegram_id == telegram_id))
    if not user:
        return False

    # Mark active subscriptions as cancelled
    active_subs = list(
        session.scalars(
            select(UserVIPSubscription).where(
                UserVIPSubscription.user_id == user.id,
                UserVIPSubscription.status == "active",
            )
        ).all()
    )
    for sub in active_subs:
        sub.status = "cancelled"

    user.is_vip = False
    user.vip_expires_at = None
    session.commit()
    return True


# ==========================================
# 👮 ADMIN & RBAC REPOSITORY
# ==========================================

def get_admin_user(session: Session, telegram_id: int) -> AdminUser | None:
    return session.scalar(select(AdminUser).where(AdminUser.telegram_id == telegram_id))


def get_admin_role(session: Session, telegram_id: int, owner_id: int | None = None) -> str | None:
    if owner_id and telegram_id == owner_id:
        return "OWNER"
    admin = get_admin_user(session, telegram_id)
    return admin.role if admin else None


def list_admins(session: Session) -> list[AdminUser]:
    return list(session.scalars(select(AdminUser).order_by(AdminUser.created_at.asc())).all())


def add_admin_user(session: Session, telegram_id: int, role: str = "ADMIN") -> AdminUser:
    admin = get_admin_user(session, telegram_id)
    if not admin:
        admin = AdminUser(telegram_id=telegram_id, role=role)
        session.add(admin)
    else:
        admin.role = role
    session.commit()
    session.refresh(admin)
    return admin


def remove_admin_user(session: Session, telegram_id: int) -> bool:
    admin = get_admin_user(session, telegram_id)
    if not admin:
        return False
    session.delete(admin)
    session.commit()
    return True


def update_admin_role(session: Session, telegram_id: int, new_role: str) -> AdminUser | None:
    admin = get_admin_user(session, telegram_id)
    if not admin:
        return None
    admin.role = new_role
    session.commit()
    session.refresh(admin)
    return admin


# ==========================================
# 📊 STATISTICS EVENT REPOSITORY
# ==========================================

def log_stat_event(
    session: Session, event_type: str, user_id: int | None = None, metadata: dict[str, Any] | None = None
) -> StatisticEvent:
    event = StatisticEvent(
        user_id=user_id,
        event_type=event_type,
        metadata_json=json.dumps(metadata or {}),
    )
    session.add(event)
    session.commit()
    return event


def get_dashboard_statistics(session: Session, since_time: datetime) -> dict[str, Any]:
    total_users = session.scalar(select(func.count(User.id))) or 0
    new_users = session.scalar(select(func.count(User.id)).where(User.created_at >= since_time)) or 0
    active_users = session.scalar(select(func.count(User.id)).where(User.last_seen_at >= since_time)) or 0
    vip_users = session.scalar(select(func.count(User.id)).where(User.is_vip == True)) or 0

    task_starts = session.scalar(
        select(func.count(StatisticEvent.id)).where(
            StatisticEvent.event_type == "TASK_START", StatisticEvent.created_at >= since_time
        )
    ) or 0
    task_successes = session.scalar(
        select(func.count(StatisticEvent.id)).where(
            StatisticEvent.event_type == "TASK_SUCCESS", StatisticEvent.created_at >= since_time
        )
    ) or 0
    task_failures = session.scalar(
        select(func.count(StatisticEvent.id)).where(
            StatisticEvent.event_type == "TASK_FAILED", StatisticEvent.created_at >= since_time
        )
    ) or 0
    vip_purchases = session.scalar(
        select(func.count(StatisticEvent.id)).where(
            StatisticEvent.event_type == "VIP_PURCHASE", StatisticEvent.created_at >= since_time
        )
    ) or 0

    revenue_total = session.scalar(
        select(func.sum(Payment.amount)).where(
            Payment.status == "paid", Payment.confirmed_at >= since_time
        )
    ) or 0.0

    return {
        "total_users": total_users,
        "new_users": new_users,
        "active_users": active_users,
        "vip_users": vip_users,
        "task_starts": task_starts,
        "task_successes": task_successes,
        "task_failures": task_failures,
        "vip_purchases": vip_purchases,
        "revenue_total": float(revenue_total),
    }


def get_user_usage_statistics(session: Session, user_db_id: int) -> dict[str, int]:
    task_starts = session.scalar(
        select(func.count(StatisticEvent.id)).where(
            StatisticEvent.user_id == user_db_id, StatisticEvent.event_type == "TASK_START"
        )
    ) or 0
    task_successes = session.scalar(
        select(func.count(StatisticEvent.id)).where(
            StatisticEvent.user_id == user_db_id, StatisticEvent.event_type == "TASK_SUCCESS"
        )
    ) or 0
    task_failures = session.scalar(
        select(func.count(StatisticEvent.id)).where(
            StatisticEvent.user_id == user_db_id, StatisticEvent.event_type == "TASK_FAILED"
        )
    ) or 0
    return {
        "task_starts": task_starts,
        "task_successes": task_successes,
        "task_failures": task_failures,
    }



# ==========================================
# 💎 FEATURE GATE REPOSITORY
# ==========================================

def get_feature_gate(session: Session, feature_key: str) -> FeatureGate | None:
    return session.scalar(select(FeatureGate).where(FeatureGate.feature_key == feature_key))


def list_feature_gates(session: Session) -> list[FeatureGate]:
    return list(session.scalars(select(FeatureGate).order_by(FeatureGate.id.asc())).all())


def toggle_feature_access_level(session: Session, feature_key: str) -> FeatureGate | None:
    fg = get_feature_gate(session, feature_key)
    if not fg:
        return None
    fg.access_level = "VIP_ONLY" if fg.access_level == "FREE" else "FREE"
    session.commit()
    session.refresh(fg)
    return fg


# ==========================================
# 💎 VIP PLANS & PAYMENTS REPOSITORY
# ==========================================

def list_vip_plans(session: Session, active_only: bool = True) -> list[VIPPlan]:
    stmt = select(VIPPlan)
    if active_only:
        stmt = stmt.where(VIPPlan.is_active == True)
    return list(session.scalars(stmt.order_by(VIPPlan.months.asc())).all())


def get_vip_plan(session: Session, plan_id: int) -> VIPPlan | None:
    return session.scalar(select(VIPPlan).where(VIPPlan.id == plan_id))


def add_vip_plan(session: Session, name: str, months: int, price: float) -> VIPPlan:
    plan = VIPPlan(name=name, months=months, price=price)
    session.add(plan)
    session.commit()
    session.refresh(plan)
    return plan


def delete_vip_plan(session: Session, plan_id: int) -> bool:
    plan = get_vip_plan(session, plan_id)
    if not plan:
        return False
    session.delete(plan)
    session.commit()
    return True


def get_payment_settings(session: Session) -> PaymentSetting:
    setting = session.scalar(select(PaymentSetting).limit(1))
    if not setting:
        setting = PaymentSetting(manual_enabled=True, auto_enabled=False)
        session.add(setting)
        session.commit()
        session.refresh(setting)
    return setting


def update_payment_settings(
    session: Session,
    binance_id: str | None = None,
    trc20_address: str | None = None,
    bep20_address: str | None = None,
    manual_enabled: bool | None = None,
) -> PaymentSetting:
    setting = get_payment_settings(session)
    if binance_id is not None:
        setting.binance_id = binance_id
    if trc20_address is not None:
        setting.trc20_address = trc20_address
    if bep20_address is not None:
        setting.bep20_address = bep20_address
    if manual_enabled is not None:
        setting.manual_enabled = manual_enabled
    setting.updated_at = datetime.now(UTC)
    session.commit()
    session.refresh(setting)
    return setting


# ==========================================
# 💳 PAYMENT & SUBSCRIPTION FLOW REPOSITORY
# ==========================================

def create_payment_order(
    session: Session,
    user_id: int,
    plan_id: int,
    amount: float,
    payment_method: str,
    currency: str = "USD",
    transaction_id: str | None = None,
    receipt_file_id: str | None = None,
) -> Payment:
    payment = Payment(
        user_id=user_id,
        plan_id=plan_id,
        amount=amount,
        currency=currency,
        payment_method=payment_method,
        status="pending",
        transaction_id=transaction_id,
        receipt_file_id=receipt_file_id,
    )
    session.add(payment)
    session.commit()
    session.refresh(payment)
    return payment


def get_payment_by_id(session: Session, payment_id: int) -> Payment | None:
    return session.scalar(select(Payment).where(Payment.id == payment_id))


def list_pending_payments(session: Session) -> list[Payment]:
    return list(session.scalars(select(Payment).where(Payment.status == "pending").order_by(Payment.created_at.asc())).all())


def reject_payment(session: Session, payment_id: int) -> bool:
    payment = get_payment_by_id(session, payment_id)
    if not payment or payment.status != "pending":
        return False
    payment.status = "rejected"
    session.commit()
    return True


def activate_vip_subscription_flow(session: Session, payment_id: int) -> UserVIPSubscription | None:
    """Strict activation pipeline: Payment Paid -> Create Subscription -> Update Access."""
    payment = get_payment_by_id(session, payment_id)
    if not payment or payment.status not in ("pending", "paid"):
        return None

    now = datetime.now(UTC)
    payment.status = "paid"
    payment.confirmed_at = now

    plan = get_vip_plan(session, payment.plan_id)
    months = plan.months if plan else 1

    user = session.scalar(select(User).where(User.id == payment.user_id))
    if not user:
        return None

    current_expiry = user.vip_expires_at if (user.vip_expires_at and user.vip_expires_at > now) else now
    expires_at = current_expiry + timedelta(days=months * 30)

    # 1. Create Subscription history record
    sub = UserVIPSubscription(
        user_id=user.id,
        plan_id=payment.plan_id,
        payment_id=payment.id,
        started_at=now,
        expires_at=expires_at,
        status="active",
    )
    session.add(sub)

    # 2. Sync user access flags
    user.is_vip = True
    user.vip_expires_at = expires_at

    # 3. Log event
    log_stat_event(
        session,
        event_type="VIP_PURCHASE",
        user_id=user.id,
        metadata={"payment_id": payment.id, "plan_id": payment.plan_id, "amount": payment.amount},
    )

    session.commit()
    session.refresh(sub)
    return sub


# ==========================================
# 📌 FORCE JOIN CHANNELS REPOSITORY
# ==========================================

def list_force_join_channels(session: Session, active_only: bool = True) -> list[ForceJoinChannel]:
    stmt = select(ForceJoinChannel)
    if active_only:
        stmt = stmt.where(ForceJoinChannel.is_active == True)
    return list(session.scalars(stmt.order_by(ForceJoinChannel.created_at.asc())).all())


def add_force_join_channel(
    session: Session, channel_id: str, title: str, username: str | None = None, invite_link: str | None = None
) -> ForceJoinChannel:
    ch = session.scalar(select(ForceJoinChannel).where(ForceJoinChannel.channel_id == channel_id))
    if not ch:
        ch = ForceJoinChannel(
            channel_id=channel_id,
            title=title,
            username=username,
            invite_link=invite_link,
            channel_type="public" if username else "private",
        )
        session.add(ch)
    else:
        ch.title = title
        ch.username = username
        ch.invite_link = invite_link
        ch.is_active = True
    session.commit()
    session.refresh(ch)
    return ch


def remove_force_join_channel(session: Session, channel_id: str) -> bool:
    ch = session.scalar(select(ForceJoinChannel).where(ForceJoinChannel.channel_id == channel_id))
    if not ch:
        return False
    session.delete(ch)
    session.commit()
    return True


# ==========================================
# ⚙️ SYSTEM SETTINGS & BROADCAST PERSISTENCE
# ==========================================

from app.db.models import BroadcastJobRecord, SystemSetting


def get_system_setting(session: Session, key: str, default_value: str = "") -> str:
    setting = session.scalar(select(SystemSetting).where(SystemSetting.key == key))
    return setting.value if setting else default_value


def set_system_setting(session: Session, key: str, value: str) -> SystemSetting:
    setting = session.scalar(select(SystemSetting).where(SystemSetting.key == key))
    if not setting:
        setting = SystemSetting(key=key, value=value)
        session.add(setting)
    else:
        setting.value = value
        setting.updated_at = datetime.now(UTC)
    session.commit()
    session.refresh(setting)
    return setting


def get_support_contact(session: Session) -> str:
    return get_system_setting(session, "support_contact", "@support")


def set_support_contact(session: Session, contact: str) -> SystemSetting:
    return set_system_setting(session, "support_contact", contact)


def save_broadcast_job_record(
    session: Session,
    job_id: str,
    message_type: str,
    from_chat_id: int | None = None,
    message_id: int | None = None,
    text: str | None = None,
    photo: str | None = None,
    video: str | None = None,
    document: str | None = None,
    total_users: int = 0,
    status: str = "pending",
) -> BroadcastJobRecord:
    rec = session.scalar(select(BroadcastJobRecord).where(BroadcastJobRecord.id == job_id))
    if not rec:
        rec = BroadcastJobRecord(
            id=job_id,
            message_type=message_type,
            from_chat_id=from_chat_id,
            message_id=message_id,
            text=text,
            photo=photo,
            video=video,
            document=document,
            total_users=total_users,
            status=status,
        )
        session.add(rec)
    else:
        rec.status = status
    session.commit()
    session.refresh(rec)
    return rec


def update_broadcast_job_progress(
    session: Session,
    job_id: str,
    sent_count: int,
    failed_count: int,
    current_index: int,
    status: str,
) -> None:
    rec = session.scalar(select(BroadcastJobRecord).where(BroadcastJobRecord.id == job_id))
    if rec:
        rec.sent_count = sent_count
        rec.failed_count = failed_count
        rec.current_index = current_index
        rec.status = status
        session.commit()


def get_pending_broadcast_job_records(session: Session) -> list[BroadcastJobRecord]:
    return list(
        session.scalars(
            select(BroadcastJobRecord).where(BroadcastJobRecord.status.in_(["pending", "running"]))
        ).all()
    )

