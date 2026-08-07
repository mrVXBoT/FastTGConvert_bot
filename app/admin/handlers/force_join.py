"""app/admin/handlers/force_join.py — 📌 Force Join Channels management router."""

from __future__ import annotations

import contextlib
import html

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.orm import Session

from app.admin.callbacks import AdminNav, ForceJoinAction
from app.admin.keyboards import (
    build_admin_cancel_keyboard,
    build_force_join_keyboard,
)
from app.admin.states import AddForceJoinState
from app.db.repositories import (
    add_force_join_channel,
    list_force_join_channels,
    remove_force_join_channel,
    toggle_force_join_channel,
)

router = Router()


def _render_lines(channels) -> list[str]:
    lines = ["📌 <b>Force Join Channels Management</b>\n"]
    if not channels:
        lines.append("No channels configured yet.")
    else:
        for ch in channels:
            st = "🟢 Active" if ch.is_active else "🔴 Inactive"
            lines.append(f"• <b>{html.escape(ch.title)}</b> (<code>{html.escape(ch.channel_id)}</code>) — {st}")
    return lines


async def _refresh_menu(message: Message, session: Session) -> None:
    channels = list_force_join_channels(session, active_only=False)
    with contextlib.suppress(TelegramBadRequest):
        await message.edit_text(
            "\n".join(_render_lines(channels)),
            reply_markup=build_force_join_keyboard(channels),
            parse_mode="HTML",
        )


@router.callback_query(AdminNav.filter(F.action == "force_join"))
async def callback_force_join_list(query: CallbackQuery, session: Session, state: FSMContext) -> None:
    """Render Force Join channels configuration menu."""
    await state.clear()
    if isinstance(query.message, Message):
        await _refresh_menu(query.message, session)
    await query.answer()


@router.callback_query(ForceJoinAction.filter(F.action == "add"))
async def callback_add_channel_start(query: CallbackQuery, state: FSMContext) -> None:
    """Start add channel workflow with Cancel button."""
    await state.set_state(AddForceJoinState.waiting_for_channel_info)
    if isinstance(query.message, Message):
        with contextlib.suppress(TelegramBadRequest):
            await query.message.edit_text(
                "➕ <b>Add Force Join Channel</b>\n\nPlease send channel ID or username (e.g. <code>@mychannel</code> or <code>-10012345678</code>):",
                reply_markup=build_admin_cancel_keyboard("force_join"),
                parse_mode="HTML",
            )
    await query.answer()


@router.message(AddForceJoinState.waiting_for_channel_info)
async def process_add_channel_input(
    message: Message, state: FSMContext, session: Session, bot: Bot
) -> None:
    """Validate and persist a channel using the live chat info from Telegram."""
    await state.clear()
    ch_input = (message.text or "").strip()
    if not ch_input:
        await message.reply(
            "❌ Channel cannot be empty. Please send a channel ID or username "
            "(e.g. <code>@mychannel</code> or <code>-10012345678</code>):",
            reply_markup=build_admin_cancel_keyboard("force_join"),
            parse_mode="HTML",
        )
        return

    try:
        chat = await bot.get_chat(chat_id=ch_input)
    except TelegramBadRequest:
        await message.reply(
            "❌ Channel not found or the bot has no access. Make sure the bot is an "
            "administrator of the channel and try again:",
            reply_markup=build_admin_cancel_keyboard("force_join"),
            parse_mode="HTML",
        )
        return

    if getattr(chat, "type", None) == "private":
        await message.reply(
            "❌ That is a user account, not a channel. Please send a channel ID "
            "or username:",
            reply_markup=build_admin_cancel_keyboard("force_join"),
            parse_mode="HTML",
        )
        return

    channel_id = f"@{chat.username}" if chat.username else ch_input
    username = chat.username
    channel_type = "public" if username else "private"
    invite_link = getattr(chat, "invite_link", None)

    ch = add_force_join_channel(
        session,
        channel_id=channel_id,
        title=chat.title or ch_input,
        username=username,
        invite_link=invite_link,
        channel_type=channel_type,
    )
    existed = getattr(ch, "_previously_existed", False)
    if existed:
        await message.reply(
            f"✅ Channel <code>{html.escape(channel_id)}</code> already existed and was re-activated!",
            reply_markup=build_admin_cancel_keyboard("force_join"),
            parse_mode="HTML",
        )
    else:
        await message.reply(
            f"✅ Channel <code>{html.escape(channel_id)}</code> added to Force Join channels!",
            reply_markup=build_admin_cancel_keyboard("force_join"),
            parse_mode="HTML",
        )


@router.callback_query(ForceJoinAction.filter(F.action == "remove"))
async def callback_remove_channel(query: CallbackQuery, callback_data: ForceJoinAction, session: Session) -> None:
    """Remove channel from Force Join list."""
    removed = remove_force_join_channel(session, callback_data.channel_id)
    if not removed:
        await query.answer("❌ Channel not found.", show_alert=True)
        return
    await query.answer("🗑️ Channel removed.", show_alert=True)
    if isinstance(query.message, Message):
        await _refresh_menu(query.message, session)


@router.callback_query(ForceJoinAction.filter(F.action == "toggle"))
async def callback_toggle_channel(query: CallbackQuery, callback_data: ForceJoinAction, session: Session) -> None:
    """Toggle the active/inactive state of a force-join channel."""
    ok = toggle_force_join_channel(session, callback_data.channel_id)
    if not ok:
        await query.answer("❌ Channel not found.", show_alert=True)
        return
    await query.answer("🔄 Channel state toggled.", show_alert=True)
    if isinstance(query.message, Message):
        await _refresh_menu(query.message, session)
