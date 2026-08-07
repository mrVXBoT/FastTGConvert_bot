from app.contacts_results import (
    CONTACTS_RESULT_LABELS,
    CONTACTS_ZIP_CAPTIONS,
    contacts_report_caption,
    contacts_result_menu,
    contacts_status_zip_caption,
    render_contacts_result,
)
from app.services.contacts_checker import ContactsCheckResult


def _sample_result() -> ContactsCheckResult:
    return ContactsCheckResult(
        checked=10,
        ok=6,
        limited=0,
        two_fa=1,
        banned=1,
        invalid=1,
        inconclusive=1,
    )


def test_render_contacts_result_en() -> None:
    text = render_contacts_result(_sample_result(), "en")
    assert "Contact Check Done!" in text
    assert "Checked: <b>10</b>" in text
    assert "OK: <b>6</b>" in text
    assert "2FA Locked: <b>1</b>" in text
    assert "Banned: <b>1</b>" in text
    assert "Invalid: <b>1</b>" in text
    assert "Inconclusive: <b>1</b>" in text


def test_contacts_result_menu_rows() -> None:
    menu = contacts_result_menu(_sample_result(), "en")
    rows = menu.inline_keyboard
    assert len(rows) == 8
    assert rows[0][0].text == "🔨 Checked"
    assert rows[0][1].text == "10"
    assert rows[1][0].text == "✅ OK"
    assert rows[1][1].text == "6"
    assert rows[2][0].text == "⚠️ Limited"
    assert rows[2][1].text == "0"
    assert rows[3][0].text == "🔑 2FA Locked"
    assert rows[3][1].text == "1"
    assert rows[4][0].text == "🚫 Banned"
    assert rows[4][1].text == "1"
    assert rows[5][0].text == "❌ Invalid"
    assert rows[5][1].text == "1"
    assert rows[6][0].text == "❓ Inconclusive"
    assert rows[6][1].text == "1"
    assert rows[7][0].callback_data == "contacts_stat:retry"
    assert rows[7][1].callback_data == "contacts_stat:home"


def test_contacts_result_menu_all_languages() -> None:
    for lang in ("bn", "en", "hi", "ur", "ar", "zh"):
        menu = contacts_result_menu(_sample_result(), lang)
        assert len(menu.inline_keyboard) == 8
        labels = CONTACTS_RESULT_LABELS[lang]
        for key in (
            "title",
            "checked",
            "ok",
            "limited",
            "two_fa",
            "banned",
            "invalid",
            "inconclusive",
            "btn_checked",
            "btn_ok",
            "btn_limited",
            "btn_two_fa",
            "btn_banned",
            "btn_invalid",
            "btn_inconclusive",
            "btn_retry",
            "btn_home",
        ):
            assert key in labels


def test_contacts_status_zip_caption() -> None:
    assert contacts_status_zip_caption("ok", 3, "en") == "📦 OK - 3 accounts"
    assert contacts_status_zip_caption("2fa", 2, "en") == "📦 2FA Locked - 2 accounts"
    assert contacts_status_zip_caption("banned", 1, "en") == "📦 Banned - 1 accounts"
    assert contacts_status_zip_caption("invalid", 4, "zh").startswith("📦 无效")


def test_contacts_zip_captions_all_languages() -> None:
    for lang in ("bn", "en", "hi", "ur", "ar", "zh"):
        labels = CONTACTS_ZIP_CAPTIONS[lang]
        for key in (
            "accounts",
            "ok",
            "limited",
            "two_fa",
            "banned",
            "invalid",
            "inconclusive",
            "report",
        ):
            assert key in labels
        assert contacts_report_caption(lang).startswith("📄")
