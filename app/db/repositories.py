from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

UTC = timezone.utc  # noqa: UP017
from typing import Any

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import (
    AdminUser,
    FeatureGate,
    ForceJoinChannel,
    Job,
    Payment,
    PaymentSetting,
    Referral,
    ReferralReward,
    ReferralTier,
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
    current_expiry = user.vip_expires_at if (
        user.vip_expires_at
        and (user.vip_expires_at if user.vip_expires_at.tzinfo else user.vip_expires_at.replace(tzinfo=UTC)) > now
    ) else now
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


def get_vip_feature_keys(session: Session) -> set[str]:
    """Return set of feature_keys that are currently VIP_ONLY."""
    stmt = select(FeatureGate.feature_key).where(FeatureGate.access_level == "VIP_ONLY")
    return set(session.scalars(stmt).all())


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
    auto_trc20_address: str | None = None,
    auto_bep20_address: str | None = None,
    manual_enabled: bool | None = None,
    auto_enabled: bool | None = None,
) -> PaymentSetting:
    setting = get_payment_settings(session)
    if binance_id is not None:
        setting.binance_id = binance_id
    if trc20_address is not None:
        setting.trc20_address = trc20_address
    if bep20_address is not None:
        setting.bep20_address = bep20_address
    if auto_trc20_address is not None:
        setting.auto_trc20_address = auto_trc20_address
    if auto_bep20_address is not None:
        setting.auto_bep20_address = auto_bep20_address
    if manual_enabled is not None:
        setting.manual_enabled = manual_enabled
    if auto_enabled is not None:
        setting.auto_enabled = auto_enabled
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


def get_active_subscription(
    session: Session, telegram_id: int
) -> UserVIPSubscription | None:
    """Return the user's most recent active VIP subscription, if any."""
    user = get_user_by_telegram_id(session, telegram_id)
    if not user:
        return None
    return session.scalar(
        select(UserVIPSubscription)
        .where(
            UserVIPSubscription.user_id == user.id,
            UserVIPSubscription.status == "active",
        )
        .order_by(UserVIPSubscription.expires_at.desc())
        .limit(1)
    )


def generate_unique_order_code(session: Session) -> str:
    """Generate a collision-proof 8-char uppercase hex order code against the database."""
    candidate = ""
    for _ in range(10):
        candidate = uuid4().hex[:8].upper()
        exists = session.scalar(select(Payment).where(Payment.order_code == candidate))
        if not exists:
            return candidate
    return candidate


def _live_pending_expected_amounts(
    session: Session, network: str, wallet_address: str
) -> set[float]:
    """Return expected amounts of all live pending orders for the same wallet+network.

    Used to stop two live orders ever sharing an expected amount, which would let a
    single on-chain transfer match (and thus activate) the wrong order.
    """
    rows = session.scalars(
        select(Payment.expected_amount).where(
            Payment.status == "pending",
            Payment.network == network,
            Payment.wallet_address == wallet_address,
            Payment.expected_amount.is_not(None),
        )
    ).all()
    return {value for value in rows if value is not None}


def create_auto_payment_orders(
    session: Session,
    user_id: int,
    plan_id: int,
    amount: float,
    currency: str = "USD",
    trc20_wallet: str = "",
    bep20_wallet: str = "",
    trc20_amount: float | None = None,
    bep20_amount: float | None = None,
    order_hours: int = 2,
) -> list[Payment]:
    """Create a pair of pending auto-payment orders (TRC20 + BEP20) with unique codes.

    Expected amounts are allocated so they never collide with any other LIVE pending
    order on the same wallet/network, backed by a partial unique index so a racing
    concurrent creation is impossible rather than merely improbable.
    """
    from app.services.payments import generate_expected_amount

    now = datetime.now(UTC)
    expires_at = now + timedelta(hours=order_hours)

    for _attempt in range(5):
        batch_used: set[float] = set()

        def _resolve_amount(
            network: str,
            wallet: str,
            suggested: float | None,
            batch: set[float],
        ) -> float:
            blocked = batch | _live_pending_expected_amounts(session, network, wallet)
            if suggested is None or suggested in blocked:
                candidate = generate_expected_amount(amount, blocked)
            else:
                candidate = suggested
            batch.add(candidate)
            return candidate

        trc20_amount = _resolve_amount("trc20", trc20_wallet, trc20_amount, batch_used)
        bep20_amount = _resolve_amount("bep20", bep20_wallet, bep20_amount, batch_used)

        orders = [
            Payment(
                user_id=user_id,
                plan_id=plan_id,
                amount=amount,
                currency=currency,
                payment_method="trc20",
                status="pending",
                order_code=generate_unique_order_code(session),
                network="trc20",
                wallet_address=trc20_wallet,
                expected_amount=trc20_amount,
                expires_at=expires_at,
            ),
            Payment(
                user_id=user_id,
                plan_id=plan_id,
                amount=amount,
                currency=currency,
                payment_method="bep20",
                status="pending",
                order_code=generate_unique_order_code(session),
                network="bep20",
                wallet_address=bep20_wallet,
                expected_amount=bep20_amount,
                expires_at=expires_at,
            ),
        ]
        session.add_all(orders)
        try:
            session.commit()
        except IntegrityError:
            # Concurrent creation allocated a colliding (wallet, network, amount).
            session.rollback()
            trc20_amount = None
            bep20_amount = None
            continue
        for order in orders:
            session.refresh(order)
        return orders
    raise RuntimeError("Could not allocate unique auto-payment amounts")


def list_pending_auto_payments(session: Session) -> list[Payment]:
    """List pending auto-payment orders (TRC20/BEP20), oldest first."""
    return list(
        session.scalars(
            select(Payment)
            .where(
                Payment.status == "pending",
                Payment.network.in_(["trc20", "bep20"]),
            )
            .order_by(Payment.created_at.asc())
        ).all()
    )


def list_pending_payments(session: Session) -> list[Payment]:
    return list(
        session.scalars(
            select(Payment)
            .where(Payment.status == "pending", Payment.network.is_(None))
            .order_by(Payment.created_at.asc())
        ).all()
    )


def expire_auto_payments(session: Session, grace_seconds: int = 0) -> int:
    """Atomically cancel pending auto-payment orders past their expiry (+ grace).

    A single UPDATE guarantees a just-claimed (already ``paid``) payment is never
    overwritten by an expiry sweep. Orders touched by a confirmed transfer
    (``completed_at``/``transaction_id`` set) are never cancelled here.
    """
    now = datetime.now(UTC)
    cutoff = now - timedelta(seconds=max(0, grace_seconds))
    result = session.execute(
        update(Payment)
        .where(
            Payment.status == "pending",
            Payment.network.in_(["trc20", "bep20"]),
            Payment.expires_at.is_not(None),
            Payment.transaction_id.is_(None),
            Payment.expires_at <= cutoff,
        )
        .values(status="cancelled")
        .execution_options(synchronize_session=False)
    )
    session.commit()
    return int(result.rowcount or 0)


def cancel_sibling_auto_orders(session: Session, payment: Payment) -> int:
    """Cancel other pending auto orders for the same user and plan."""
    siblings = list(
        session.scalars(
            select(Payment).where(
                Payment.status == "pending",
                Payment.network.in_(["trc20", "bep20"]),
                Payment.user_id == payment.user_id,
                Payment.plan_id == payment.plan_id,
                Payment.id != payment.id,
            )
        ).all()
    )
    for sibling in siblings:
        sibling.status = "cancelled"
    session.commit()
    return len(siblings)


def is_transaction_used(session: Session, tx_hash: str) -> bool:
    """Whether a transaction hash was already confirmed on a paid payment."""
    exists = session.scalar(
        select(Payment).where(
            Payment.transaction_id == tx_hash,
            Payment.status == "paid",
        )
    )
    return exists is not None


def reject_payment(session: Session, payment_id: int) -> bool:
    payment = get_payment_by_id(session, payment_id)
    if not payment or payment.status != "pending":
        return False
    payment.status = "rejected"
    session.commit()
    return True


def activate_vip_subscription_flow(session: Session, payment_id: int) -> UserVIPSubscription | None:
    """Strict activation pipeline: Payment Paid -> Create Subscription -> Update Access.

    Idempotent per payment: if a subscription was already created for this payment it
    is returned untouched, so duplicate config (double admin approve, approve racing
    the poll loop) can never extend VIP twice or create duplicate subscriptions.
    """
    payment = get_payment_by_id(session, payment_id)
    if not payment or payment.status not in ("pending", "paid"):
        return None

    existing_sub = session.scalar(
        select(UserVIPSubscription).where(UserVIPSubscription.payment_id == payment.id)
    )
    if existing_sub is not None:
        return existing_sub

    now = datetime.now(UTC)
    payment.status = "paid"
    payment.confirmed_at = now
    sub = _create_subscription_record(session, payment, now)
    session.commit()
    session.refresh(sub)
    return sub


def claim_and_activate_vip_subscription(
    session: Session, payment_id: int, tx_hash: str
) -> UserVIPSubscription | None:
    """Atomically claim a pending payment and activate VIP in one commit.

    The rowcount guard makes the pending->paid transition single-winner even when
    the expiry sweep and a payment scan run in separate processes, so a transfer can
    never be counted as both paid and voided. Returns ``None`` (no changes persisted)
    when the payment was already claimed or expired.
    """
    now = datetime.now(UTC)
    claimed = session.execute(
        update(Payment)
        .where(Payment.id == payment_id, Payment.status == "pending")
        .values(
            status="paid",
            transaction_id=tx_hash,
            confirmed_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    if claimed.rowcount != 1:
        session.rollback()
        return None
    payment = get_payment_by_id(session, payment_id)
    if payment is None:
        session.rollback()
        return None
    sub = _create_subscription_record(session, payment, now)
    session.commit()
    session.refresh(sub)
    return sub


def _create_subscription_record(
    session: Session, payment: Payment, now: datetime
) -> UserVIPSubscription:
    """Create the subscription row and sync user flags, without committing."""
    plan = get_vip_plan(session, payment.plan_id)
    months = plan.months if plan else 1

    user = session.scalar(select(User).where(User.id == payment.user_id))
    if not user:
        raise ValueError(f"No user for payment {payment.id}")

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
    session: Session,
    channel_id: str,
    title: str,
    username: str | None = None,
    invite_link: str | None = None,
    channel_type: str = "public",
) -> ForceJoinChannel:
    existed = False
    ch = session.scalar(select(ForceJoinChannel).where(ForceJoinChannel.channel_id == channel_id))
    if not ch:
        ch = ForceJoinChannel(
            channel_id=channel_id,
            title=title,
            username=username,
            invite_link=invite_link,
            channel_type=channel_type,
        )
        session.add(ch)
    else:
        existed = True
        ch.title = title
        ch.username = username
        ch.invite_link = invite_link
        ch.channel_type = channel_type
        ch.is_active = True
    session.commit()
    session.refresh(ch)
    ch._previously_existed = existed
    return ch


def remove_force_join_channel(session: Session, channel_id: str) -> bool:
    ch = session.scalar(select(ForceJoinChannel).where(ForceJoinChannel.channel_id == channel_id))
    if not ch:
        return False
    session.delete(ch)
    session.commit()
    return True


def toggle_force_join_channel(session: Session, channel_id: str) -> bool:
    """Toggle the active state of a force-join channel."""
    ch = session.scalar(select(ForceJoinChannel).where(ForceJoinChannel.channel_id == channel_id))
    if not ch:
        return False
    ch.is_active = not ch.is_active
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
        if total_users:
            rec.total_users = total_users
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
    total_users: int | None = None,
) -> None:
    rec = session.scalar(select(BroadcastJobRecord).where(BroadcastJobRecord.id == job_id))
    if rec:
        rec.sent_count = sent_count
        rec.failed_count = failed_count
        rec.current_index = current_index
        rec.status = status
        if total_users is not None:
            rec.total_users = total_users
        session.commit()


def get_pending_broadcast_job_records(session: Session) -> list[BroadcastJobRecord]:
    return list(
        session.scalars(
            select(BroadcastJobRecord).where(BroadcastJobRecord.status.in_(["pending", "running"]))
        ).all()
    )



# ==========================================
# 🔗 REFERRAL SYSTEM REPOSITORY
# ==========================================

def is_referral_enabled(session: Session) -> bool:
    """Whether the referral system is enabled (SystemSetting referral_enabled)."""
    return get_system_setting(session, "referral_enabled", "1") == "1"


def set_referral_enabled(session: Session, enabled: bool) -> None:
    set_system_setting(session, "referral_enabled", "1" if enabled else "0")


def list_referral_tiers(
    session: Session, active_only: bool = False
) -> list[ReferralTier]:
    stmt = select(ReferralTier).order_by(ReferralTier.refs_required.asc())
    if active_only:
        stmt = stmt.where(ReferralTier.is_active.is_(True))
    return list(session.scalars(stmt).all())


def get_referral_tier(session: Session, tier_id: int) -> ReferralTier | None:
    return session.scalar(
        select(ReferralTier).where(ReferralTier.id == tier_id)
    )


def add_referral_tier(session: Session, refs_required: int, reward_days: int) -> ReferralTier:
    existing = session.scalar(
        select(ReferralTier).where(ReferralTier.refs_required == refs_required)
    )
    if existing:
        existing.reward_days = reward_days
        existing.is_active = True
        tier = existing
    else:
        tier = ReferralTier(refs_required=refs_required, reward_days=reward_days)
        session.add(tier)
    session.commit()
    session.refresh(tier)
    return tier


def delete_referral_tier(session: Session, tier_id: int) -> bool:
    tier = session.scalar(select(ReferralTier).where(ReferralTier.id == tier_id))
    if not tier:
        return False
    session.delete(tier)
    session.commit()
    return True


def toggle_referral_tier(session: Session, tier_id: int) -> ReferralTier | None:
    tier = session.scalar(select(ReferralTier).where(ReferralTier.id == tier_id))
    if not tier:
        return None
    tier.is_active = not tier.is_active
    session.commit()
    session.refresh(tier)
    return tier


def count_referrals(session: Session, referrer_telegram_id: int) -> int:
    return (
        session.scalar(
            select(func.count())
            .select_from(Referral)
            .where(Referral.referrer_telegram_id == referrer_telegram_id)
        )
        or 0
    )


def list_referrals_paginated(
    session: Session,
    referrer_telegram_id: int | None = None,
    page: int = 1,
    page_size: int = 8,
) -> tuple[list[Referral], int]:
    """Paginated referral records, optionally filtered by referrer. Newest first."""
    stmt = select(Referral)
    if referrer_telegram_id is not None:
        stmt = stmt.where(Referral.referrer_telegram_id == referrer_telegram_id)
    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = list(
        session.scalars(
            stmt.order_by(Referral.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return rows, total


def list_referral_rewards_paginated(
    session: Session,
    referrer_telegram_id: int | None = None,
    page: int = 1,
    page_size: int = 8,
) -> tuple[list[ReferralReward], int]:
    """Paginated reward events, optionally filtered by referrer. Newest first."""
    stmt = select(ReferralReward)
    if referrer_telegram_id is not None:
        stmt = stmt.where(ReferralReward.referrer_telegram_id == referrer_telegram_id)
    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = list(
        session.scalars(
            stmt.order_by(ReferralReward.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return rows, total


def sum_referral_reward_days(session: Session, referrer_telegram_id: int) -> int:
    return (
        session.scalar(
            select(func.coalesce(func.sum(ReferralReward.days), 0)).where(
                ReferralReward.referrer_telegram_id == referrer_telegram_id
            )
        )
        or 0
    )


def get_referral_stats(
    session: Session, telegram_id: int
) -> dict[str, Any]:
    """Aggregated referral stats for a user (used by /referral)."""
    referred = count_referrals(session, telegram_id)
    earned_days = sum_referral_reward_days(session, telegram_id)
    next_tier: dict[str, int] | None = None
    for tier in list_referral_tiers(session, active_only=True):
        if tier.refs_required > referred:
            next_tier = {"refs": tier.refs_required, "days": tier.reward_days}
            break
    return {"referred": referred, "earned_days": earned_days, "next_tier": next_tier}


def grant_user_vip_days(session: Session, telegram_id: int, days: int) -> User | None:
    """Extend a user's VIP subscription by *days* (used by referral rewards)."""
    user = session.scalar(select(User).where(User.telegram_id == telegram_id))
    if not user:
        return None
    now = datetime.now(UTC)
    current_expiry = user.vip_expires_at if (
        user.vip_expires_at
        and (user.vip_expires_at if user.vip_expires_at.tzinfo else user.vip_expires_at.replace(tzinfo=UTC)) > now
    ) else now
    expires_at = current_expiry + timedelta(days=days)

    sub = UserVIPSubscription(
        user_id=user.id,
        plan_id=None,
        payment_id=None,
        started_at=now,
        expires_at=expires_at,
        status="active",
    )
    session.add(sub)
    user.is_vip = True
    user.vip_expires_at = expires_at
    session.commit()
    session.refresh(user)
    return user


def register_referral(
    session: Session, referrer_telegram_id: int, referred_telegram_id: int
) -> dict[str, Any]:
    """Register a new referral. Returns outcome dict.

    Guards: self-referral, duplicate referral, unknown referrer.
    On success, evaluates reward tiers and grants the next unlocked tier once.
    """
    if referrer_telegram_id == referred_telegram_id:
        return {"ok": False, "reason": "self_referral"}
    if not is_referral_enabled(session):
        return {"ok": False, "reason": "disabled"}

    referrer = session.scalar(
        select(User).where(User.telegram_id == referrer_telegram_id)
    )
    if referrer is None:
        return {"ok": False, "reason": "unknown_referrer"}

    referred_user = session.scalar(
        select(User).where(User.telegram_id == referred_telegram_id)
    )
    if referred_user is None:
        referred_user = upsert_user(session, referred_telegram_id, None)
    if referred_user.referred_by is not None:
        return {"ok": False, "reason": "already_referred"}

    existing = session.scalar(
        select(Referral).where(
            Referral.referred_telegram_id == referred_telegram_id
        )
    )
    if existing:
        return {"ok": False, "reason": "already_referred"}

    referred_user.referred_by = referrer_telegram_id
    session.add(
        Referral(
            referrer_telegram_id=referrer_telegram_id,
            referred_telegram_id=referred_telegram_id,
        )
    )
    session.flush()

    referred_count = count_referrals(session, referrer_telegram_id)
    granted = 0
    granted_tier: ReferralTier | None = None
    claimed = {
        r.tier_id
        for r in session.scalars(
            select(ReferralReward).where(
                ReferralReward.referrer_telegram_id == referrer_telegram_id
            )
        ).all()
        if r.tier_id is not None
    }

    for tier in list_referral_tiers(session, active_only=True):
        if referred_count >= tier.refs_required and tier.id not in claimed:
            session.add(
                ReferralReward(
                    referrer_telegram_id=referrer_telegram_id,
                    tier_id=tier.id,
                    days=tier.reward_days,
                )
            )
            claimed.add(tier.id)
            granted += tier.reward_days
            granted_tier = tier

    if granted > 0:
        grant_user_vip_days(session, referrer_telegram_id, granted)

    session.commit()
    return {
        "ok": True,
        "reason": "registered",
        "referred_count": referred_count,
        "granted_days": granted,
        "tier": granted_tier,
    }


def get_activated_subscription_since(
    session: Session, user_id: int, since: datetime
) -> UserVIPSubscription | None:
    """Return the most recent VIP subscription linked to an auto-confirmed payment.

    Covers the M2 case where the payment poll loop already activated the user in the
    background before they pressed "Check Payment": the pending scan then finds no
    order, but the user *did* pay and should be shown a confirmation.
    """
    return session.scalar(
        select(UserVIPSubscription)
        .join(Payment, Payment.id == UserVIPSubscription.payment_id)
        .where(
            UserVIPSubscription.user_id == user_id,
            Payment.status == "paid",
            Payment.transaction_id.is_not(None),
            Payment.confirmed_at.is_not(None),
            Payment.confirmed_at >= since,
        )
        .order_by(UserVIPSubscription.started_at.desc())
    )
