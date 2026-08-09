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
        checked=15,
        ok=6,
        limited=2,
        two_fa=1,
        banned=1,
        invalid=4,
        inconclusive=1,
    )


def test_render_contacts_result_en() -> None:
    text = render_contacts_result(_sample_result(), "en")
    assert "Check Contact Permissions" in text
    assert "Checked: <b>15</b>" in text
    assert "Healthy account: <b>6</b>" in text
    assert "Restricted account: <b>2</b>" in text
    assert "Invalid account: <b>6</b>" in text
    assert "Error account: <b>1</b>" in text
    assert "Retry" in text


def test_render_contacts_result_no_retry_note_when_no_errors() -> None:
    result = ContactsCheckResult(
        checked=3, ok=3, limited=0, two_fa=0, banned=0, invalid=0, inconclusive=0
    )
    text = render_contacts_result(result, "en")
    assert "Retry" not in text


def test_contacts_result_menu_rows() -> None:
    menu = contacts_result_menu(_sample_result(), "en")
    rows = menu.inline_keyboard
    assert len(rows) == 6
    assert rows[0][0].text == "🔨 Checked"
    assert rows[0][1].text == "15"
    assert rows[1][0].text == "🟢 Healthy"
    assert rows[1][1].text == "6"
    assert rows[2][0].text == "🟡 Restricted"
    assert rows[2][1].text == "2"
    assert rows[3][0].text == "❌ Invalid"
    assert rows[3][1].text == "6"
    assert rows[4][0].text == "☑️ Error"
    assert rows[4][1].text == "1"
    assert rows[5][0].callback_data == "contacts_stat:retry"
    assert rows[5][1].callback_data == "contacts_stat:home"


def test_contacts_result_menu_all_languages() -> None:
    for lang in ("bn", "en", "hi", "ur", "ar", "zh"):
        menu = contacts_result_menu(_sample_result(), lang)
        assert len(menu.inline_keyboard) == 6
        labels = CONTACTS_RESULT_LABELS[lang]
        for key in (
            "title",
            "checked",
            "healthy",
            "restricted",
            "invalid",
            "error",
            "retry_note",
            "btn_checked",
            "btn_healthy",
            "btn_restricted",
            "btn_invalid",
            "btn_error",
            "btn_retry",
            "btn_home",
        ):
            assert key in labels


def test_contacts_status_zip_caption() -> None:
    assert contacts_status_zip_caption("ok", 3, "en") == "🟢 Healthy - 3 accounts"
    assert contacts_status_zip_caption("limited", 2, "en") == "🟡 Restricted - 2 accounts"
    assert contacts_status_zip_caption("2fa", 1, "en") == "❌ Invalid - 1 accounts"
    assert contacts_status_zip_caption("banned", 1, "en") == "❌ Invalid - 1 accounts"
    assert contacts_status_zip_caption("invalid", 4, "en") == "❌ Invalid - 4 accounts"
    assert contacts_status_zip_caption("inconclusive", 5, "en") == "☑️ Error - 5 accounts"
    assert contacts_status_zip_caption("ok", 3, "zh").startswith("🟢 健康")


def test_contacts_zip_captions_all_languages() -> None:
    for lang in ("bn", "en", "hi", "ur", "ar", "zh"):
        labels = CONTACTS_ZIP_CAPTIONS[lang]
        for key in ("accounts", "healthy", "restricted", "invalid", "error", "report"):
            assert key in labels
        assert contacts_report_caption(lang).startswith("📄")