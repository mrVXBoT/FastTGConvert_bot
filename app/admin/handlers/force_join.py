"""app/admin/handlers/force_join.py — 📌 Force Join Channels management router."""

from __future__ import annotations

import contextlib
import html

from aiogram import F, Router
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
)

router = Router()


@router.callback_query(AdminNav.filter(F.action == "force_join"))
async def callback_force_join_list(query: CallbackQuery, session: Session, state: FSMContext) -> None:
    """Render Force Join channels configuration menu."""
    await state.clear()
    channels = list_force_join_channels(session, active_only=False)

    lines = ["📌 <b>Force Join Channels Management</b>\n"]
    if not channels:
        lines.append("No channels configured yet.")
    else:
        for ch in channels:
            st = "🟢 Active" if ch.is_active else "🔴 Inactive"
            lines.append(f"• <b>{html.escape(ch.title)}</b> (<code>{html.escape(ch.channel_id)}</code>) — {st}")

    reply_kb = build_force_join_keyboard(channels)
    if isinstance(query.message, Message):
        with contextlib.suppress(TelegramBadRequest):
            await query.message.edit_text("\n".join(lines), reply_markup=reply_kb, parse_mode="HTML")
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
async def process_add_channel_input(message: Message, state: FSMContext, session: Session) -> None:
    """Process channel username or ID."""
    await state.clear()
    ch_input = (message.text or "").strip()
    username = ch_input.replace("@", "") if ch_input.startswith("@") else None
    ch_id = ch_input if not username else f"@{username}"

    add_force_join_channel(session, channel_id=ch_id, title=ch_input, username=username)
    await message.reply(
        f"✅ Channel <code>{html.escape(ch_id)}</code> added to Force Join channels!",
        reply_markup=build_admin_cancel_keyboard("force_join"),
        parse_mode="HTML",
    )


@router.callback_query(ForceJoinAction.filter(F.action == "remove"))
async def callback_remove_channel(query: CallbackQuery, callback_data: ForceJoinAction, session: Session) -> None:
    """Remove channel from Force Join list."""
    remove_force_join_channel(session, callback_data.channel_id)
    await query.answer("🗑️ Channel removed.", show_alert=True)
    channels = list_force_join_channels(session, active_only=False)
    if isinstance(query.message, Message):
        with contextlib.suppress(TelegramBadRequest):
            await query.message.edit_reply_markup(reply_markup=build_force_join_keyboard(channels))
