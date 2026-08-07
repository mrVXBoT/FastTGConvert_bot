import pytest

from app.session_results import (
    SessionCheckResult,
    render_session_result,
    render_spam_result,
    session_result_menu,
    status_zip_caption,
)
from app.ui import EmojiRegistry


def test_session_result_matches_reference_layout() -> None:
    result = SessionCheckResult(checked=1, active=1, frozen=0, invalid=0)
    session_text = render_session_result(result)
    spam_text = render_spam_result(result)
    menu = session_result_menu(result)
    divider = EmojiRegistry.divider_line()

    assert "Session Check Done!" in session_text
    assert session_text == (
        "✅ <b>Session Check Done!</b>\n"
        f"{divider}\n"
        "📊 Checked: <b>1</b>\n"
        "🟢 Active Account: <b>1</b>\n"
        "🛡️ Spam Account: <b>0</b>\n"
        "🟡 Freeze Account: <b>0</b>\n"
        "❌ Invalid Account: <b>0</b>\n"
        "🚫 Banned / Deactivated: <b>0</b>\n"
        "❓ Inconclusive: <b>0</b>"
    )
    assert "Inconclusive: <b>0</b>" in session_text

    assert "Spam Check Done!" in spam_text

    assert len(menu.inline_keyboard) == 7
    assert [row[0].text for row in menu.inline_keyboard] == [
        "🔨 Checked",
        "🟢 Active Account",
        "🛡️ Spam Account",
        "🟡 Freeze Account",
        "❌ Invalid Account",
        "🚫 Banned / Deactivated",
        "❓ Inconclusive",
    ]
    assert [row[1].text for row in menu.inline_keyboard] == [
        "1",
        "1",
        "0",
        "0",
        "0",
        "0",
        "0",
    ]


def test_spam_result_text_matches_buttons() -> None:
    result = SessionCheckResult(
        checked=9, active=2, frozen=2, spam=1, invalid=1, banned=2, inconclusive=1
    )
    spam_text = render_spam_result(result)
    menu = session_result_menu(result, spam_mode=True)
    divider = EmojiRegistry.divider_line()

    # Spam = spam + frozen + banned, Error = invalid + inconclusive –
    # identical in both the message text and the button labels.
    assert spam_text == (
        "🛡️ <b>Spam Check Done!</b>\n"
        f"{divider}\n"
        "🔨 Checked: <b>9</b>\n"
        "🟢 Clean: <b>2</b>\n"
        "🚫 Spam: <b>5</b>\n"
        "❌ Invalid/Error: <b>2</b>"
    )
    assert [row[0].text for row in menu.inline_keyboard] == [
        "🔨 Checked",
        "🟢 Clean",
        "🚫 Spam",
        "❌ Invalid/Error",
    ]
    assert [row[1].text for row in menu.inline_keyboard] == ["9", "2", "5", "2"]


def test_session_result_menu_calculates_spam_error_count() -> None:
    result = SessionCheckResult(
        checked=6, active=2, frozen=1, spam=1, invalid=1, banned=1
    )
    menu = session_result_menu(result, spam_mode=True)

    # checked=6, active=2, spam (spam+frozen+banned)=3, invalid/err (invalid+inconclusive)=1
    assert [row[1].text for row in menu.inline_keyboard] == ["6", "2", "3", "1"]


def test_invariant_violation_raises_at_construction() -> None:
    with pytest.raises(ValueError, match="checked"):
        SessionCheckResult(checked=10, active=1, frozen=0, invalid=0)


def test_status_zip_caption_matches_reference_format() -> None:
    # Reference bot: "📦 No Restriction - 9 accounts", "📦 Spam - 1 accounts".
    assert status_zip_caption("active", 9) == "📦 No Restriction - 9 accounts"
    assert status_zip_caption("spam", 1) == "📦 Spam - 1 accounts"
    assert status_zip_caption("frozen", 1) == "📦 Frozen - 1 accounts"
    assert status_zip_caption("banned", 2) == "📦 Banned - 2 accounts"
    assert status_zip_caption("invalid", 3) == "📦 Invalid - 3 accounts"
    assert status_zip_caption("inconclusive", 4) == "📦 Error - 4 accounts"
    assert status_zip_caption("active", 9, "zh") == "📦 无限制 - 9 个账号"
