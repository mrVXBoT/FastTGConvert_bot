"""Tests for app.login_email_results rendering, menus and captions."""

from __future__ import annotations

from pathlib import Path

from aiogram.types import InlineKeyboardMarkup

from app.login_email_results import (
    LOGIN_EMAIL_RESULT_LABELS,
    login_email_result_menu,
    login_email_zip_caption,
    render_login_email_result,
)
from app.services.login_email import LoginEmailBatchResult

LANGS = ("en", "bn", "hi", "ur", "ar", "zh")
REQUIRED_KEYS = (
    "title",
    "total",
    "updated",
    "no_email",
    "failed",
    "btn_total",
    "btn_updated",
    "btn_no_email",
    "btn_failed",
    "btn_archive_updated",
    "btn_archive_no_email",
    "btn_archive_failed",
    "btn_archive_all",
    "organize_hint",
    "zip_updated",
    "zip_no_email",
    "zip_failed",
    "zip_all",
    "expired",
    "btn_home",
)


def _sample_result() -> LoginEmailBatchResult:
    return LoginEmailBatchResult(
        total=10,
        changed_count=4,
        no_email_count=3,
        error_count=3,
        success_zip=Path("/tmp/s.zip"),
        failed_zip=Path("/tmp/f.zip"),
        failed_session_zip=Path("/tmp/e.zip"),
        classified_zip=Path("/tmp/c.zip"),
    )


def test_labels_complete_for_every_language() -> None:
    for lang in LANGS:
        for key in REQUIRED_KEYS:
            assert LOGIN_EMAIL_RESULT_LABELS[lang][key], (lang, key)


def test_render_includes_all_counts() -> None:
    text = render_login_email_result(_sample_result(), "en")
    assert "Total Accounts" in text
    assert len(text.splitlines()) == 8
    assert "4" in text
    assert "3" in text


def test_render_falls_back_to_english() -> None:
    en_text = render_login_email_result(_sample_result(), "en")
    fallback = render_login_email_result(_sample_result(), "xx")
    assert fallback == en_text


def test_menu_rows_and_organize_buttons() -> None:
    markup = login_email_result_menu(_sample_result(), "en")
    rows = markup.inline_keyboard
    assert len(rows) == 7
    for row in rows[:4]:
        assert len(row) == 2
    labels = [b.text for row in rows for b in row]
    assert "10" in labels
    assert "4" in labels
    assert "3" in labels
    organize = rows[4] + rows[5]
    callbacks = [b.callback_data for b in organize]
    assert callbacks == [
        "login_email:organize:updated",
        "login_email:organize:noemail",
        "login_email:organize:failed",
        "login_email:organize:all",
    ]
    assert rows[6][0].callback_data == "menu:back"


def test_menu_stat_rows_use_premium_emoji_when_registered(monkeypatch) -> None:
    from app.ui import EmojiRegistry

    def fake_custom(key: str) -> str | None:
        return {"TOTAL": "100", "ACTIVE": "101", "INVALID": "102", "FAILED": "103"}.get(
            key
        )

    monkeypatch.setattr(EmojiRegistry, "get_custom_emoji_id", staticmethod(fake_custom))
    markup: InlineKeyboardMarkup = login_email_result_menu(_sample_result(), "en")
    rows = markup.inline_keyboard
    for row, expected_icon in zip(rows[:4], ("100", "101", "102", "103")):
        label_button = row[0]
        assert label_button.text and not label_button.text.startswith(
            ("🔨 ", "🟢 ", "🟡 ", "❌ ")
        )
        assert label_button.icon_custom_emoji_id == expected_icon


def test_zip_captions() -> None:
    assert login_email_zip_caption("updated", 4, "en") == (
        "Login Email Updated - 4 accounts"
    )
    assert "3" in login_email_zip_caption("noemail", 3, "en")
    assert login_email_zip_caption("all", 10, "en").endswith(
        "Classified Archive (report.txt included)"
    )
    assert login_email_zip_caption("unknown", 1, "en") == login_email_zip_caption(
        "all", 1, "en"
    )
