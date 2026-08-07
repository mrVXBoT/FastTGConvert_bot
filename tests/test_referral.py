"""tests/test_referral.py — Unit tests for the referral system (registration, tiers, rewards, pagination, admin helpers)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.migration import run_migrations
from app.db.models import Base, Referral, ReferralReward
from app.db.repositories import (
    add_referral_tier,
    delete_referral_tier,
    get_referral_stats,
    is_referral_enabled,
    list_referral_rewards_paginated,
    list_referral_tiers,
    list_referrals_paginated,
    register_referral,
    set_referral_enabled,
    sum_referral_reward_days,
    toggle_referral_tier,
    upsert_user,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    run_migrations(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield session
    session.close()


def test_default_tiers_and_enabled(db_session) -> None:
    tiers = list_referral_tiers(db_session)
    assert [(t.refs_required, t.reward_days, t.is_active) for t in tiers] == [
        (1, 1, True),
        (7, 7, True),
        (15, 15, True),
        (30, 30, True),
    ]
    assert is_referral_enabled(db_session) is True

    set_referral_enabled(db_session, False)
    assert is_referral_enabled(db_session) is False
    set_referral_enabled(db_session, True)
    assert is_referral_enabled(db_session) is True


def test_register_referral_guards(db_session) -> None:
    upsert_user(db_session, 100, "referrer")
    upsert_user(db_session, 200, "referee")
    db_session.commit()

    assert register_referral(db_session, 100, 200)["reason"] == "registered"
    assert register_referral(db_session, 100, 200)["reason"] == "already_referred"
    assert register_referral(db_session, 100, 100)["reason"] == "self_referral"
    assert register_referral(db_session, 999, 300)["reason"] == "unknown_referrer"

    set_referral_enabled(db_session, False)
    assert register_referral(db_session, 100, 250)["reason"] == "disabled"
    set_referral_enabled(db_session, True)


def test_referral_reward_flow(db_session) -> None:
    upsert_user(db_session, 100, "referrer")
    upsert_user(db_session, 200, "referee")
    db_session.commit()

    result = register_referral(db_session, 100, 200)
    assert result["granted_days"] == 1
    assert result["referred_count"] == 1
    assert sum_referral_reward_days(db_session, 100) == 1

    for i in range(6):
        upsert_user(db_session, 300 + i, f"u{i}")
    db_session.commit()
    for i in range(6):
        register_referral(db_session, 100, 300 + i)

    stats = get_referral_stats(db_session, 100)
    assert stats["referred"] == 7
    assert stats["earned_days"] == 8  # 1 + 7
    assert stats["next_tier"]["refs"] == 15

    upsert_user(db_session, 9991, "late")
    db_session.commit()
    register_referral(db_session, 100, 9991)
    assert sum_referral_reward_days(db_session, 100) == 8  # no double reward

    rewards, total = list_referral_rewards_paginated(db_session, referrer_telegram_id=100)
    assert total == 2
    assert sum(r.days for r in rewards) == 8


def test_vip_grant_extends_expiry(db_session) -> None:
    upsert_user(db_session, 100, "referrer")
    upsert_user(db_session, 200, "referee")
    db_session.commit()

    register_referral(db_session, 100, 200)
    first = sum_referral_reward_days(db_session, 100)

    # 6 more referees unlock tier 7 -> +7 days on top of the first 1
    for i in range(6):
        upsert_user(db_session, 300 + i, f"u{i}")
    db_session.commit()
    for i in range(6):
        register_referral(db_session, 100, 300 + i)

    assert sum_referral_reward_days(db_session, 100) == first + 7


def test_pagination_and_tiers_crud(db_session) -> None:
    upsert_user(db_session, 100, "referrer")
    db_session.commit()
    for i in range(20):
        upsert_user(db_session, 500 + i, f"ref{i}")
    db_session.commit()
    for i in range(20):
        register_referral(db_session, 100, 500 + i)

    page1, total = list_referrals_paginated(db_session, referrer_telegram_id=100, page=1, page_size=8)
    page3, _ = list_referrals_paginated(db_session, referrer_telegram_id=100, page=3, page_size=8)
    assert total == 20
    assert len(page1) == 8
    assert len(page3) == 4
    assert isinstance(page1[0], Referral)

    tier = add_referral_tier(db_session, refs_required=50, reward_days=30)
    assert tier.reward_days == 30
    assert any(t.refs_required == 50 for t in list_referral_tiers(db_session))

    toggle_referral_tier(db_session, tier.id)
    assert next(t for t in list_referral_tiers(db_session) if t.id == tier.id).is_active is False

    delete_referral_tier(db_session, tier.id)
    assert all(t.refs_required != 50 for t in list_referral_tiers(db_session))

    rewards, _ = list_referral_rewards_paginated(db_session, referrer_telegram_id=100, page_size=100)
    assert len(rewards) == 3
    assert all(isinstance(r, ReferralReward) for r in rewards)


def test_stats_for_clean_user(db_session) -> None:
    upsert_user(db_session, 777, "lonely")
    db_session.commit()
    stats = get_referral_stats(db_session, 777)
    assert stats["referred"] == 0
    assert stats["earned_days"] == 0
    assert stats["next_tier"]["refs"] == 1


@pytest.mark.asyncio
async def test_admin_tier_input_valid(db_session) -> None:
    """FSM input '10 | 10' must create a new tier via add_referral_tier."""
    from app.admin.handlers.referral import process_referral_tier_input

    message = MagicMock(spec=Message)
    message.text = "10 | 10"
    message.reply = AsyncMock()
    state = AsyncMock(spec=FSMContext)
    state.clear = AsyncMock()

    with patch("app.admin.handlers.referral.add_referral_tier") as add_tier:
        await process_referral_tier_input(message, state, db_session)

    add_tier.assert_called_once_with(db_session, refs_required=10, reward_days=10)
    state.clear.assert_awaited_once()
    message.reply.assert_awaited_once()


@pytest.mark.asyncio
async def test_admin_tier_input_invalid(db_session) -> None:
    """Malformed / non-positive FSM input must be rejected without adding a tier."""
    from app.admin.handlers.referral import process_referral_tier_input

    state = AsyncMock(spec=FSMContext)
    state.clear = AsyncMock()

    for bad_text in ("10", "10|10|10", "abc | 5", "5 | -3", "0 | 5"):
        message = MagicMock(spec=Message)
        message.text = bad_text
        message.reply = AsyncMock()
        with patch("app.admin.handlers.referral.add_referral_tier") as add_tier:
            await process_referral_tier_input(message, state, db_session)
        add_tier.assert_not_called()
        message.reply.assert_awaited_once()
    assert state.clear.await_count == len(("10", "10|10|10", "abc | 5", "5 | -3", "0 | 5"))


@pytest.mark.asyncio
async def test_admin_tier_toggle_callback(db_session) -> None:
    """Tier toggle callback flips is_active and refreshes the keyboard."""
    from app.admin.callbacks import ReferralTierAction
    from app.admin.handlers.referral import callback_referral_tier_toggle

    tier = list_referral_tiers(db_session)[0]
    query = MagicMock()
    query.answer = AsyncMock()

    await callback_referral_tier_toggle(query, ReferralTierAction(action="toggle", tier_id=tier.id), db_session)

    query.answer.assert_awaited_once()
    assert next(t for t in list_referral_tiers(db_session) if t.id == tier.id).is_active is False
