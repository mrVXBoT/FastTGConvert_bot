import pytest

from app.session_results import (
    SessionCheckResult,
    render_session_result,
    render_spam_result,
    session_result_menu,
)


def test_session_result_matches_reference_layout() -> None:
    result = SessionCheckResult(checked=1, active=1, frozen=0, invalid=0)
    session_text = render_session_result(result)
    spam_text = render_spam_result(result)
    menu = session_result_menu(result)

    assert "Session Check Done!" in session_text
    assert session_text == (
        "✅ <b>Session Check Done!</b>\n\n"
        "📊 Checked: <b>1</b>\n"
        "🟢 Active Account: <b>1</b>\n"
        "🟡 Freeze Account: <b>0</b>\n"
        "❌ Invalid Account: <b>0</b>"
    )
    assert "Inconclusive" not in session_text

    assert "Spam Check Done!" in spam_text
    assert "1 Checked" in spam_text

    assert len(menu.inline_keyboard) == 4
    assert [row[0].text for row in menu.inline_keyboard] == [
        "🔨 Checked",
        "🟢 Active Account",
        "🟡 Freeze Account",
        "❌ Invalid Account",
    ]
    assert [row[1].text for row in menu.inline_keyboard] == ["1", "1", "0", "0"]


def test_session_result_menu_calculates_spam_error_count() -> None:
    result = SessionCheckResult(checked=5, active=2, frozen=1, invalid=1, banned=1)
    menu = session_result_menu(result, spam_mode=True)

    # checked=5, active=2, spam (frozen+banned)=2, invalid/err (invalid+inconclusive)=1
    assert [row[1].text for row in menu.inline_keyboard] == ["5", "2", "2", "1"]


def test_invariant_violation_raises_at_construction() -> None:
    with pytest.raises(ValueError, match="checked"):
        SessionCheckResult(checked=10, active=1, frozen=0, invalid=0)
