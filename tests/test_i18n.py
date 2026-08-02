from app.locales import (
    ACCOUNT_AGE_MESSAGES,
    ANALYSIS_MESSAGES,
    ANALYZE_PROMPTS,
    ARCHIVE_ERRORS,
    CANCEL_LABELS,
    DOWNLOAD_ERRORS,
    HELP_BUTTON_LABELS,
    HELP_MESSAGES,
    INVALID_LANGUAGE_MESSAGES,
    LANGUAGES,
    MENU_LABELS,
    PLAN_MESSAGES,
    PRIVACY_MESSAGES,
    READ_OTP_MESSAGES,
    READ_OTP_PROMPTS,
    SESSION_CHECK_PROMPTS,
    SPAM_CHECK_PROMPTS,
    SPLIT_CHUNK_PROMPTS,
    SPLIT_ERRORS,
    SPLIT_MESSAGES,
    SPLIT_PROMPTS,
    SUPPORT_UNAVAILABLE,
    action_message,
)
from app.session_results import (
    SESSION_RESULT_LABELS,
    SessionCheckResult,
    render_session_result,
    render_spam_result,
    session_result_menu,
)


def test_all_supported_languages_present() -> None:
    expected_langs = {"en", "bn", "hi", "ur", "ar", "zh"}
    assert set(LANGUAGES.keys()) == expected_langs


def test_every_language_has_full_dictionaries() -> None:
    expected_langs = {"en", "bn", "hi", "ur", "ar", "zh"}
    for lang in expected_langs:
        assert lang in MENU_LABELS
        assert lang in CANCEL_LABELS
        assert lang in ANALYZE_PROMPTS
        assert lang in SESSION_CHECK_PROMPTS
        assert lang in SPAM_CHECK_PROMPTS
        assert lang in HELP_MESSAGES
        assert lang in HELP_BUTTON_LABELS
        assert lang in SUPPORT_UNAVAILABLE
        assert lang in PRIVACY_MESSAGES
        assert lang in ACCOUNT_AGE_MESSAGES
        assert lang in PLAN_MESSAGES
        assert lang in INVALID_LANGUAGE_MESSAGES
        assert lang in DOWNLOAD_ERRORS
        assert lang in ARCHIVE_ERRORS
        assert lang in SPLIT_PROMPTS
        assert lang in SPLIT_CHUNK_PROMPTS
        assert lang in SPLIT_ERRORS
        assert lang in ANALYSIS_MESSAGES
        assert lang in SPLIT_MESSAGES
        assert lang in READ_OTP_PROMPTS
        assert lang in READ_OTP_MESSAGES
        assert lang in SESSION_RESULT_LABELS


def test_session_and_spam_result_rendering_all_languages() -> None:
    res = SessionCheckResult(checked=5, active=3, frozen=1, invalid=1)
    for lang in ("en", "bn", "hi", "ur", "ar", "zh"):
        session_text = render_session_result(res, language=lang)
        assert str(res.checked) in session_text
        assert str(res.active) in session_text
        assert str(res.frozen) in session_text
        assert str(res.invalid) in session_text

        spam_text = render_spam_result(res, language=lang)
        assert str(res.checked) in spam_text
        assert str(res.active) in spam_text
        assert str(res.invalid) in spam_text

        menu = session_result_menu(res, language=lang)
        assert len(menu.inline_keyboard) == 4


def test_action_messages_all_languages() -> None:
    for lang in ("en", "bn", "hi", "ur", "ar", "zh"):
        for idx in range(4):
            msg = action_message(lang, idx)
            assert len(msg) > 0
