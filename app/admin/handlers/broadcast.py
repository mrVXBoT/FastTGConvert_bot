"""app/admin/handlers/broadcast.py — 📢 Broadcast system using Async Worker Queue."""

from __future__ import annotations

import contextlib

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.orm import Session

from app.admin.callbacks import AdminNav
from app.admin.keyboards import (
    build_admin_cancel_keyboard,
    build_admin_main_menu_keyboard,
    build_broadcast_preview_keyboard,
)
from app.admin.states import BroadcastState
from app.services.broadcast import BROADCAST_WORKER

router = Router()


@router.callback_query(AdminNav.filter(F.action == "broadcast"))
async def callback_broadcast_menu(query: CallbackQuery, state: FSMContext, admin_role: str) -> None:
    """Prompt admin to send or forward broadcast content with Cancel button."""
    from app.admin.rbac import has_permission
    if not has_permission(admin_role, "ADMIN"):
        await query.answer("🚫 Broadcast requires ADMIN role or higher.", show_alert=True)
        return
    await state.set_state(BroadcastState.waiting_for_content)
    text = (
        "📢 <b>Broadcast System</b>\n\n"
        "Please send or forward the message you wish to broadcast to all active users:\n\n"
        "• <b>Forward Broadcast:</b> Forward any message from a channel/chat.\n"
        "• <b>Custom Broadcast:</b> Send text, photo, video, GIF, or document."
    )
    if isinstance(query.message, Message):
        with contextlib.suppress(TelegramBadRequest):
            await query.message.edit_text(
                text,
                reply_markup=build_admin_cancel_keyboard("home"),
                parse_mode="HTML",
            )
    await query.answer()


@router.message(BroadcastState.waiting_for_content)
async def process_broadcast_content(message: Message, state: FSMContext) -> None:
    """Receive broadcast message and render live preview for confirmation."""
    bcast_type = "forward" if message.forward_date else "custom"
    await state.update_data(
        bcast_type=bcast_type,
        from_chat_id=message.chat.id if message.forward_date else None,
        message_id=message.message_id,
        text=message.text or message.caption,
        photo=message.photo[-1].file_id if message.photo else None,
        video=message.video.file_id if message.video else None,
        document=message.document.file_id if message.document else None,
    )
    await state.set_state(BroadcastState.waiting_for_preview_confirm)

    await message.reply(
        "🔍 <b>Broadcast Preview Mode</b>\n\nAbove is a copy of your broadcast message. Confirm dispatch to queue worker?",
        reply_markup=build_broadcast_preview_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "adm_bcast_send", BroadcastState.waiting_for_preview_confirm)
async def callback_broadcast_confirm(query: CallbackQuery, state: FSMContext, session: Session, admin_role: str) -> None:
    """Dispatch broadcast via BroadcastQueueWorker."""
    data = await state.get_data()
    await state.clear()

    if not isinstance(query.message, Message) or not query.bot:
        return

    job = BROADCAST_WORKER.create_job(
        session=session,
        message_type=data.get("bcast_type", "custom"),
        from_chat_id=data.get("from_chat_id"),
        message_id=data.get("message_id"),
        text=data.get("text"),
        photo=data.get("photo"),
        video=data.get("video"),
        document=data.get("document"),
    )

    await query.message.edit_text(f"🚀 <b>Broadcast Job <code>{job.job_id}</code> queued!</b>\n\nProcessing active users...", parse_mode="HTML")
    await query.answer()

    result = await BROADCAST_WORKER.enqueue_and_process(
        bot=query.bot,
        session=session,
        job=job,
    )

    summary_text = (
        f"✅ <b>Broadcast Job <code>{result.job_id}</code> {result.status.upper()}!</b>\n\n"
        f"👥 <b>Total Target Users:</b> <code>{result.total_users}</code>\n"
        f"✅ <b>Successfully Sent:</b> <code>{result.sent_count}</code>\n"
        f"❌ <b>Failed / Blocked:</b> <code>{result.failed_count}</code>"
    )
    await query.message.edit_text(
        summary_text,
        reply_markup=build_admin_main_menu_keyboard(admin_role=admin_role),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "adm_bcast_cancel", BroadcastState.waiting_for_preview_confirm)
async def callback_broadcast_cancel(query: CallbackQuery, state: FSMContext, admin_role: str) -> None:
    """Cancel broadcast flow."""
    await state.clear()
    if isinstance(query.message, Message):
        with contextlib.suppress(TelegramBadRequest):
            await query.message.edit_text(
                "❌ Broadcast cancelled.",
                reply_markup=build_admin_main_menu_keyboard(admin_role=admin_role),
            )
    await query.answer()
