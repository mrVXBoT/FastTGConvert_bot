from pathlib import Path

from app.handlers.otp import get_session_metadata
from app.keyboards import otp_checked_menu, otp_initial_menu
from app.locales import READ_OTP_MESSAGES, READ_OTP_PROMPTS


def test_read_otp_prompts_and_messages_all_languages() -> None:
    for lang in ("en", "bn", "hi", "ur", "ar", "zh"):
        assert lang in READ_OTP_PROMPTS
        assert lang in READ_OTP_MESSAGES
        msgs = READ_OTP_MESSAGES[lang]
        assert "account_header" in msgs
        assert "account_details" in msgs
        assert "account_details_again" in msgs
        assert "btn_check" in msgs
        assert "btn_skip" in msgs
        assert "btn_check_again" in msgs
        assert "btn_logout" in msgs


def test_otp_keyboards_structure() -> None:
    for lang in ("en", "bn", "hi", "ur", "ar", "zh"):
        init_menu = otp_initial_menu(lang)
        assert len(init_menu.inline_keyboard) == 3
        assert init_menu.inline_keyboard[0][0].callback_data == "otp:check"
        assert init_menu.inline_keyboard[1][0].callback_data == "otp:skip"
        assert init_menu.inline_keyboard[2][0].callback_data == "action:cancel"

        checked_menu = otp_checked_menu(lang)
        assert len(checked_menu.inline_keyboard) == 3
        assert checked_menu.inline_keyboard[0][0].callback_data == "otp:check_again"
        assert checked_menu.inline_keyboard[1][0].callback_data == "otp:skip"
        assert checked_menu.inline_keyboard[2][0].callback_data == "action:cancel"


def test_get_session_metadata_does_not_invent_identity() -> None:
    meta = get_session_metadata(Path("573118508561.session"))
    assert meta["session_id"] == "573118508561"
    assert meta["user"] == "N/A"
    assert meta["phone"] == "+573118508561"
    assert meta["username"] == "N/A"


def test_session_metadata_uses_original_name_not_random_storage_name() -> None:
    meta = get_session_metadata(
        Path("4b8ecea3cd0343848f25944e05dbb96b.session"),
        original_name="573118508561.session",
    )
    assert meta["session_id"] == "573118508561"


def test_otp_messages_formatting() -> None:
    for messages in READ_OTP_MESSAGES.values():
        rendered = messages["account_details"].format(
            current=1,
            total=1,
            user="Echo > Null",
            phone="+573118508561",
            username="@Over_Replyz",
            otp_content=messages["no_otps_2h"],
        )
        assert "Echo > Null" in rendered
        assert "+573118508561" in rendered
        assert "@Over_Replyz" in rendered
        assert "3" in messages["skipped_one"].format(count=3)


def test_extract_zip_sessions_duplicate_basenames() -> None:
    import tempfile
    import zipfile

    from app.handlers.otp import extract_zip_sessions

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        zip_path = tmp_dir / "test.zip"
        with zipfile.ZipFile(zip_path, "w") as z:
            z.writestr("folder1/sess.session", b"data1")
            z.writestr("folder2/sess.session", b"data2")

        extracted = extract_zip_sessions(zip_path, tmp_dir)
        assert len(extracted) == 2
        path1 = Path(extracted[0]["session_path"])
        path2 = Path(extracted[1]["session_path"])
        assert path1.exists() and path2.exists()
        assert path1 != path2
        assert path1.read_bytes() == b"data1"
        assert path2.read_bytes() == b"data2"
