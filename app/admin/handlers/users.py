"""app/admin/handlers/users.py — 👥 User Management, Card-based Pagination, Search & Detail actions."""

from __future__ import annotations

import contextlib
import html
import math

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.orm import Session

from app.admin.callbacks import AdminNav, UserAction, UserNav
from app.admin.keyboards import (
    build_admin_cancel_keyboard,
    build_user_detail_keyboard,
    build_users_pagination_keyboard,
)
from app.admin.states import UserDirectMessageState, UserSearchState
from app.db.repositories import (
    get_user_by_telegram_id,
    get_user_usage_statistics,
    get_users_paginated,
    grant_user_vip,
    revoke_user_vip,
    set_user_ban_status,
)

router = Router()


@router.callback_query(AdminNav.filter(F.action == "users"))
@router.callback_query(UserNav.filter())
async def callback_users_list(
    query: CallbackQuery, session: Session, state: FSMContext, callback_data: UserNav | AdminNav | None = None
) -> None:
    """Render paginated card-based Users list with Inline View buttons."""
    await state.clear()
    page = callback_data.page if isinstance(callback_data, UserNav) else 1
    search = callback_data.search if isinstance(callback_data, UserNav) else ""
    page_size = 5

    users, total_count = get_users_paginated(session, page=page, page_size=page_size, search_query=search)
    total_pages = max(1, math.ceil(total_count / page_size))

    text_lines = [f"👥 <b>Users Management</b> (Total: <code>{total_count}</code>)\n"]
    if search:
        text_lines.append(f"🔍 Filter: <code>{html.escape(search)}</code>\n")

    if not users:
        text_lines.append("⚠️ No users found.")
    else:
        for idx, u in enumerate(users, start=1):
            vip_tag = "💎 VIP" if u.is_vip else "⚪ Normal"
            status_tag = " | 🚫 BANNED" if u.status == "banned" else ""
            username_str = f"@{html.escape(u.username)}" if u.username else "N/A"
            text_lines.append(
                f"💳 <b>User Card #{idx}</b>\n"
                f"👤 <b>Username:</b> {username_str}\n"
                f"🆔 <b>Telegram ID:</b> <code>{u.telegram_id}</code>\n"
                f"🌐 <b>Language:</b> <code>{u.language.upper()}</code>\n"
                f"Status: {vip_tag}{status_tag}\n"
            )

    reply_kb = build_users_pagination_keyboard(users=users, page=page, total_pages=total_pages, search=search)
    if isinstance(query.message, Message):
        with contextlib.suppress(TelegramBadRequest):
            await query.message.edit_text("\n".join(text_lines), reply_markup=reply_kb, parse_mode="HTML")
    await query.answer()


@router.callback_query(F.data == "adm_usr_search")
async def callback_user_search_start(query: CallbackQuery, state: FSMContext) -> None:
    """Start user search input state with Cancel button."""
    await state.set_state(UserSearchState.waiting_for_query)
    if isinstance(query.message, Message):
        with contextlib.suppress(TelegramBadRequest):
            await query.message.edit_text(
                "🔍 <b>Search User</b>\n\nPlease enter Telegram ID or @username to search:",
                reply_markup=build_admin_cancel_keyboard("users"),
                parse_mode="HTML",
            )
    await query.answer()


@router.message(UserSearchState.waiting_for_query)
async def process_user_search_input(message: Message, state: FSMContext, session: Session) -> None:
    """Handle text query search and render card-based results with Inline View buttons."""
    await state.clear()
    query_text = (message.text or "").strip()
    if not query_text:
        await message.reply(
            "❌ Search query cannot be empty. Please enter a Telegram ID or @username:",
            reply_markup=build_admin_cancel_keyboard("users"),
            parse_mode="HTML",
        )
        return
    users, total_count = get_users_paginated(session, page=1, page_size=5, search_query=query_text)
    total_pages = max(1, math.ceil(total_count / 5))

    text_lines = [f"🔍 <b>Search Results for:</b> <code>{html.escape(query_text)}</code> (Found: <code>{total_count}</code>)\n"]
    if not users:
        text_lines.append("❌ No users matched your search criteria.")
    else:
        for idx, u in enumerate(users, start=1):
            vip_tag = "💎 VIP" if u.is_vip else "⚪ Normal"
            status_tag = " | 🚫 BANNED" if u.status == "banned" else ""
            username_str = f"@{html.escape(u.username)}" if u.username else "N/A"
            text_lines.append(
                f"💳 <b>User Card #{idx}</b>\n"
                f"👤 <b>Username:</b> {username_str}\n"
                f"🆔 <b>Telegram ID:</b> <code>{u.telegram_id}</code>\n"
                f"🌐 <b>Language:</b> <code>{u.language.upper()}</code>\n"
                f"Status: {vip_tag}{status_tag}\n"
            )

    reply_kb = build_users_pagination_keyboard(users=users, page=1, total_pages=total_pages, search=query_text)
    await message.answer("\n".join(text_lines), reply_markup=reply_kb, parse_mode="HTML")


@router.callback_query(UserAction.filter())
async def callback_user_action(
    query: CallbackQuery, callback_data: UserAction, session: Session, state: FSMContext, admin_role: str
) -> None:
    """Execute User Detail actions (View, Give/Remove VIP, Ban/Unban, Direct Message)."""
    from app.admin.rbac import check_user_action_permission

    action = callback_data.action
    target_id = callback_data.user_id

    # Fine-grained permission check per action
    if not check_user_action_permission(admin_role, action):
        await query.answer(
            f"🚫 Your role ({admin_role}) cannot perform this action.",
            show_alert=True,
        )
        return

    if action == "give_vip":
        grant_user_vip(session, target_id, months=1)
        await query.answer("✅ 1 Month VIP granted to user!", show_alert=True)
    elif action == "remove_vip":
        revoke_user_vip(session, target_id)
        await query.answer("❌ VIP revoked from user.", show_alert=True)
    elif action == "ban":
        set_user_ban_status(session, target_id, banned=True)
        await query.answer("🚫 User banned successfully.", show_alert=True)
    elif action == "unban":
        set_user_ban_status(session, target_id, banned=False)
        await query.answer("🟢 User unbanned.", show_alert=True)
    elif action == "msg":
        await state.update_data(target_id=target_id)
        await state.set_state(UserDirectMessageState.waiting_for_message)
        if isinstance(query.message, Message):
            with contextlib.suppress(TelegramBadRequest):
                await query.message.edit_text(
                    f"📩 <b>Direct Message to User</b> <code>{target_id}</code>\n\nPlease type your message below:",
                    reply_markup=build_admin_cancel_keyboard("users"),
                    parse_mode="HTML",
                )
        await query.answer()
        return

    # Render updated detailed User Card (for view or after action)
    user = get_user_by_telegram_id(session, target_id)
    if not user:
        await query.answer("❌ User not found in database.", show_alert=True)
        return

    usage_stats = get_user_usage_statistics(session, user.id)
    vip_exp_str = user.vip_expires_at.strftime("%Y-%m-%d") if user.vip_expires_at else "N/A"
    username_str = f"@{html.escape(user.username)}" if user.username else "N/A"

    text = (
        f"👤 <b>User Detail Panel</b>\n\n"
        f"👤 <b>Username:</b> {username_str}\n"
        f"🆔 <b>Telegram ID:</b> <code>{user.telegram_id}</code>\n"
        f"🌐 <b>Language:</b> <code>{user.language.upper()}</code>\n"
        f"💎 <b>VIP Status:</b> {'💎 VIP' if user.is_vip else '⚪ Normal'}\n"
        f"⏳ <b>VIP Expiry:</b> <code>{vip_exp_str}</code>\n"
        f"🛡️ <b>Account Status:</b> <code>{user.status.upper()}</code>\n"
        f"📅 <b>Joined Date:</b> <code>{user.created_at.strftime('%Y-%m-%d')}</code>\n"
        f"🕒 <b>Last Active:</b> <code>{user.last_seen_at.strftime('%Y-%m-%d %H:%M')}</code>\n\n"
        f"📊 <b>Usage Statistics:</b>\n"
        f"• Tasks Executed: <code>{usage_stats['task_starts']}</code>\n"
        f"• Tasks Succeeded: <code>{usage_stats['task_successes']}</code>\n"
        f"• Tasks Failed: <code>{usage_stats['task_failures']}</code>"
    )

    reply_kb = build_user_detail_keyboard(user.telegram_id, is_vip=user.is_vip, is_banned=(user.status == "banned"))
    if isinstance(query.message, Message):
        with contextlib.suppress(TelegramBadRequest):
            await query.message.edit_text(text, reply_markup=reply_kb, parse_mode="HTML")
    await query.answer()


@router.message(UserDirectMessageState.waiting_for_message)
async def process_direct_message(message: Message, state: FSMContext) -> None:
    """Send direct message from admin to user."""
    data = await state.get_data()
    target_id = data.get("target_id")
    await state.clear()

    if target_id and message.bot and message.text:
        try:
            await message.bot.send_message(
                chat_id=target_id,
                text=f"📩 <b>Message from Admin Support:</b>\n\n{html.escape(message.text)}",
                parse_mode="HTML",
            )
            await message.reply(f"✅ Direct message sent to user <code>{target_id}</code>!", parse_mode="HTML")
        except Exception as exc:  # noqa: BLE001
            await message.reply(f"❌ Failed to send message: {html.escape(str(exc))}", parse_mode="HTML")
