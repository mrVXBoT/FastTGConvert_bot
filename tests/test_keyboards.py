from unittest.mock import AsyncMock

import pytest
from aiogram.types import CallbackQuery

from app.handlers.files import handle_contacts_stat_noop
from app.keyboards import language_menu, main_menu, membership_menu
from app.locales import SESSION_CHECK_PROMPTS, action_message
from app.ui import EmojiRegistry


def test_language_menu_matches_reference_order() -> None:
    menu = language_menu()
    assert [btn.text for row in menu.inline_keyboard for btn in row] == [
        "🇧🇩 বাংলা",
        "🇬🇧 English",
        "🇮🇳 हिन्दी",
        "🇵🇰 اردو",
        "🇸🇦 العربية",
        "🇨🇳 中文",
    ]


def test_language_is_applied_directly_without_start_button() -> None:
    initial = language_menu()
    selected = language_menu("ar")
    assert not any(
        btn.callback_data.startswith("language:start")
        for row in initial.inline_keyboard
        for btn in row
    )
    ar_btn = next(
        btn
        for row in selected.inline_keyboard
        for btn in row
        if btn.callback_data == "language:ar"
    )
    assert "✅" in ar_btn.text
    assert ar_btn.style == "success"
    assert selected.inline_keyboard[-1][0].callback_data == "menu:back"


def test_english_membership_menu_has_join_and_verify_buttons() -> None:
    menu = membership_menu(("@FastTGConvert",), "en")
    row = menu.inline_keyboard[0]
    assert row[0].text == "📌 Join Channel"
    assert row[0].url == "https://t.me/FastTGConvert"
    assert row[1].text == "✅ I Joined"
    assert row[1].callback_data == "membership:check:en"


def test_main_menu_is_rendered_in_selected_language() -> None:
    english = main_menu("en")
    arabic = main_menu("ar")
    chinese = main_menu("zh")
    assert english.inline_keyboard[0][0].text == "🔍 ━━ CHECK ━━"
    assert arabic.inline_keyboard[0][0].text == "🔍 ━━ فحص ━━"
    assert chinese.inline_keyboard[0][0].text == "🔍 ━━ 检查 ━━"
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


@pytest.mark.asyncio
async def test_setup_bot_commands_registers_required_commands() -> None:
    from unittest.mock import MagicMock

    from app.__main__ import setup_bot_commands

    mock_bot = MagicMock()
    mock_bot.set_my_commands = AsyncMock()

    await setup_bot_commands(mock_bot)

    mock_bot.set_my_commands.assert_called_once()
    cmds = mock_bot.set_my_commands.call_args.kwargs["commands"]
    cmd_dict = {c.command: c.description for c in cmds}
    assert cmd_dict == {
        "start": "restart 🚀",
        "referral": "your referral link 🔗",
        "proxy": "Set your proxy 🎯",
        "language": "Change your language 🌍",
    }


def test_main_menu_vip_badge_rendering(monkeypatch: pytest.MonkeyPatch) -> None:
    free_menu = main_menu("en", vip_features=set())
    session_btn = free_menu.inline_keyboard[1][0]
    assert "💎" not in session_btn.text
    assert session_btn.icon_custom_emoji_id is None

    vip_menu = main_menu("en", vip_features={"session_check", "read_otp"})
    vip_session_btn = vip_menu.inline_keyboard[1][0]
    assert "💎" not in vip_session_btn.text
    assert vip_session_btn.icon_custom_emoji_id == "5413351005779672594"

    vip_otp_btn = vip_menu.inline_keyboard[2][0]
    assert "💎" not in vip_otp_btn.text
    assert vip_otp_btn.icon_custom_emoji_id == "5413351005779672594"

    spam_btn = vip_menu.inline_keyboard[1][1]
    assert "💎" not in spam_btn.text
    assert spam_btn.icon_custom_emoji_id is None

    monkeypatch.setattr(
        EmojiRegistry, "get_custom_emoji_id", lambda key: None, raising=False
    )
    fallback_menu = main_menu("en", vip_features={"session_check"})
    fb_btn = fallback_menu.inline_keyboard[1][0]
    assert "💎" in fb_btn.text
    assert fb_btn.icon_custom_emoji_id is None


def test_vip_checkout_menu_has_back_and_cancel_buttons() -> None:
    from app.keyboards import vip_checkout_menu

    kb = vip_checkout_menu("en")
    assert len(kb.inline_keyboard[0]) == 2
    assert kb.inline_keyboard[0][0].callback_data == "menu:plan"
    assert kb.inline_keyboard[0][1].callback_data == "action:cancel"
