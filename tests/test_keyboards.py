from unittest.mock import AsyncMock

import pytest
from aiogram.types import CallbackQuery

from app.handlers.files import handle_contacts_stat_noop
from app.keyboards import language_menu, main_menu, membership_menu
from app.locales import SESSION_CHECK_PROMPTS, action_message


def test_language_menu_matches_reference_order() -> None:
    menu = language_menu()
    assert [row[0].text for row in menu.inline_keyboard] == [
        "🇧🇩 বাংলা",
        "🇬🇧 English",
        "🇮🇳 हिन्दी",
        "🇵🇰 اردو",
        "🇸🇦 العربية",
        "🇨🇳 中文",
        "🚀 /start",
    ]


def test_language_is_only_confirmed_by_start_button() -> None:
    initial = language_menu()
    selected = language_menu("ar")
    assert initial.inline_keyboard[-1][0].callback_data == "language:start"
    assert selected.inline_keyboard[-1][0].callback_data == "language:start:ar"


def test_english_membership_menu_has_join_and_verify_buttons() -> None:
    menu = membership_menu(("@FastTGConvert",), "en")
    row = menu.inline_keyboard[0]
    assert row[0].text == "✅ Join Channel"
    assert row[0].url == "https://t.me/FastTGConvert"
    assert row[1].text == "🔄 I Joined"
    assert row[1].callback_data == "membership:check:en"


def test_main_menu_is_rendered_in_selected_language() -> None:
    english = main_menu("en")
    arabic = main_menu("ar")
    chinese = main_menu("zh")
    assert english.inline_keyboard[0][0].text == "━━ 🔍 CHECK ━━"
    assert arabic.inline_keyboard[0][0].text == "━━ 🔍 فحص ━━"
    assert chinese.inline_keyboard[0][0].text == "━━ 🔍 检查 ━━"
    assert arabic.inline_keyboard[-1][1].text == "🇸🇦 العربية"


def test_check_response_uses_selected_language() -> None:
    assert "sensitive account access" in action_message("en", 2)
    assert "وصولاً حساساً" in action_message("ar", 2)
    assert "账户访问权限" in action_message("zh", 2)


def test_session_check_opens_upload_flow_without_command_cancel() -> None:
    menu = main_menu("en")
    assert menu.inline_keyboard[1][0].callback_data == "tool:session_check"
    assert menu.inline_keyboard[1][1].callback_data == "tool:spam_check"
    assert ".session" in SESSION_CHECK_PROMPTS["en"]
    assert ".zip" in SESSION_CHECK_PROMPTS["en"]
    assert "/cancel" not in SESSION_CHECK_PROMPTS["en"]


@pytest.mark.asyncio
async def test_contacts_stat_noop_callback_handler_answers_query() -> None:
    cb = AsyncMock(spec=CallbackQuery)
    cb.data = "contacts_stat:noop"
    cb.answer = AsyncMock()

    await handle_contacts_stat_noop(cb)
    cb.answer.assert_called_once()
