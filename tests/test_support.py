from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.config import Settings
from app.handlers.start import back_to_main_menu, help_menu
from app.keyboards import help_support_menu, resolve_support_contact


def test_support_contact_accepts_username_url_and_numeric_id() -> None:
    assert resolve_support_contact("@A_d_m_i_n_1_0") == (
        "@A_d_m_i_n_1_0",
        "https://t.me/A_d_m_i_n_1_0",
    )
    assert resolve_support_contact("https://t.me/example_admin") == (
        "@example_admin",
        "https://t.me/example_admin",
    )
    assert resolve_support_contact("123456789") == (
        "ID: 123456789",
        "tg://user?id=123456789",
    )
    assert resolve_support_contact("") is None
    assert resolve_support_contact("invalid id") is None


def test_support_keyboard_has_contact_link_and_back_button() -> None:
    keyboard = help_support_menu("@A_d_m_i_n_1_0", "en")

    assert len(keyboard.inline_keyboard) == 2
    assert keyboard.inline_keyboard[0][0].url == "https://t.me/A_d_m_i_n_1_0"
    assert "Contact Support" in keyboard.inline_keyboard[0][0].text
    assert keyboard.inline_keyboard[1][0].callback_data == "menu:back"


def test_unconfigured_support_keyboard_only_has_back_button() -> None:
    keyboard = help_support_menu("", "en")

    assert len(keyboard.inline_keyboard) == 1
    assert keyboard.inline_keyboard[0][0].callback_data == "menu:back"


@pytest.mark.asyncio
async def test_help_edits_current_message_with_configured_support() -> None:
    callback = MagicMock(spec=CallbackQuery)
    callback.answer = AsyncMock()
    callback.from_user = MagicMock(id=123)
    callback.message = MagicMock(spec=Message)
    callback.message.edit_text = AsyncMock()
    state = AsyncMock(spec=FSMContext)
    state.get_data.return_value = {}
    settings = Settings(bot_token="x" * 20, support_id="@A_d_m_i_n_1_0")

    with patch("app.handlers.start.user_language", return_value="en"):
        await help_menu(callback, state, settings, MagicMock())

    callback.message.edit_text.assert_awaited_once()
    text = callback.message.edit_text.await_args.args[0]
    keyboard = callback.message.edit_text.await_args.kwargs["reply_markup"]
    assert "Help &amp; Support" not in text
    assert "Help & Support" in text
    assert "@A_d_m_i_n_1_0" in text
    assert keyboard.inline_keyboard[0][0].url == "https://t.me/A_d_m_i_n_1_0"
    callback.message.answer.assert_not_called()
    state.clear.assert_awaited_once()


@pytest.mark.asyncio
async def test_back_button_edits_help_message_into_main_menu() -> None:
    callback = MagicMock(spec=CallbackQuery)
    callback.answer = AsyncMock()
    callback.from_user = MagicMock(id=123)
    callback.message = MagicMock(spec=Message)
    callback.message.edit_text = AsyncMock()
    state = AsyncMock(spec=FSMContext)
    state.get_data.return_value = {}

    with patch("app.handlers.start.user_language", return_value="en"):
        await back_to_main_menu(callback, state, MagicMock())

    callback.message.edit_text.assert_awaited_once()
    text = callback.message.edit_text.await_args.args[0]
    assert "Telegram Account Checker Bot" in text
    assert "Choose an option" in text
    callback.message.answer.assert_not_called()
