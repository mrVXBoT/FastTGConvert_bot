"""app/admin/handlers/admins.py — 👮 Admin & Role Management — fully Inline Keyboard driven."""

from __future__ import annotations

import contextlib
import html

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.orm import Session

from app.admin.callbacks import AdminMgmtAction, AdminNav
from app.admin.keyboards import (
    build_add_admin_role_selector_keyboard,
    build_admin_cancel_keyboard,
    build_admin_confirm_remove_keyboard,
    build_admin_detail_keyboard,
    build_admin_list_keyboard,
    build_admin_role_selector_keyboard,
)
from app.admin.states import AddAdminState
from app.config import Settings
from app.db.repositories import (
    add_admin_user,
    get_admin_user,
    list_admins,
    remove_admin_user,
    update_admin_role,
)

router = Router()


# ─── Admin List ──────────────────────────────────────────────────────────────

@router.callback_query(AdminNav.filter(F.action == "admins"))
async def callback_admins_list(
    query: CallbackQuery, session: Session, settings: Settings, state: FSMContext
) -> None:
    """Render card-based Admin list with inline View buttons."""
    await state.clear()
    admins = list_admins(session)

    lines = [
        "👮 <b>Admin Management</b>\n",
        f"👑 <b>Owner:</b> <code>{settings.admin_id}</code>\n",
        f"🛡️ <b>Active Admins:</b> <code>{len(admins)}</code>\n",
    ]
    if not admins:
        lines.append("\n⚠️ No admins configured yet. Add one below.")
    else:
        for adm in admins:
            from app.admin.keyboards import ROLE_EMOJI
            emoji = ROLE_EMOJI.get(adm.role, "🛡️")
            lines.append(f"\n{emoji} <b>ID:</b> <code>{adm.telegram_id}</code>  Role: <code>{adm.role}</code>")

    reply_kb = build_admin_list_keyboard(admins)
    if isinstance(query.message, Message):
        with contextlib.suppress(TelegramBadRequest):
            await query.message.edit_text("\n".join(lines), reply_markup=reply_kb, parse_mode="HTML")
    await query.answer()


# ─── View Admin Detail ───────────────────────────────────────────────────────

@router.callback_query(AdminMgmtAction.filter(F.action == "view"))
async def callback_admin_view(
    query: CallbackQuery, callback_data: AdminMgmtAction, session: Session, settings: Settings
) -> None:
    """Show admin detail card with action buttons."""
    admin = get_admin_user(session, callback_data.admin_id)
    if not admin:
        await query.answer("❌ Admin not found.", show_alert=True)
        return

    from app.admin.keyboards import ROLE_EMOJI
    emoji = ROLE_EMOJI.get(admin.role, "🛡️")
    text = (
        f"👮 <b>Admin Detail</b>\n\n"
        f"🆔 <b>Telegram ID:</b> <code>{admin.telegram_id}</code>\n"
        f"{emoji} <b>Role:</b> <code>{admin.role}</code>\n"
        f"📅 <b>Added:</b> <code>{admin.created_at.strftime('%Y-%m-%d %H:%M')}</code>"
    )
    if isinstance(query.message, Message):
        with contextlib.suppress(TelegramBadRequest):
            await query.message.edit_text(
                text,
                reply_markup=build_admin_detail_keyboard(admin.telegram_id),
                parse_mode="HTML",
            )
    await query.answer()


# ─── Add Admin: Step 1 — Select Role ─────────────────────────────────────────

@router.callback_query(AdminMgmtAction.filter(F.action == "add_start"))
async def callback_add_admin_start(
    query: CallbackQuery, callback_data: AdminMgmtAction, state: FSMContext
) -> None:
    """Step 1: Show role selector. If role already chosen (via same callback), move to Step 2."""
    if callback_data.role:
        # Role has been selected — move to Telegram ID input
        await state.update_data(selected_role=callback_data.role)
        await state.set_state(AddAdminState.waiting_for_user_id)
        if isinstance(query.message, Message):
            with contextlib.suppress(TelegramBadRequest):
                await query.message.edit_text(
                    f"➕ <b>Add Admin — Role: <code>{html.escape(callback_data.role)}</code></b>\n\n"
                    f"Please send the <b>Telegram ID</b> of the user to promote:",
                    reply_markup=build_admin_cancel_keyboard("admins"),
                    parse_mode="HTML",
                )
        await query.answer()
    else:
        # First step — show role picker
        await state.set_state(AddAdminState.waiting_for_role)
        if isinstance(query.message, Message):
            with contextlib.suppress(TelegramBadRequest):
                await query.message.edit_text(
                    "➕ <b>Add Admin — Step 1: Select Role</b>\n\n"
                    "Choose the access role for the new admin:",
                    reply_markup=build_add_admin_role_selector_keyboard(),
                    parse_mode="HTML",
                )
        await query.answer()


# ─── Add Admin: Step 2 — Receive Telegram ID ─────────────────────────────────

@router.message(AddAdminState.waiting_for_user_id)
async def process_add_admin_id(message: Message, state: FSMContext, session: Session) -> None:
    """Step 2: Receive Telegram ID and create admin record."""
    data = await state.get_data()
    selected_role = data.get("selected_role", "ADMIN")
    await state.clear()

    raw = (message.text or "").strip()
    try:
        new_admin_id = int(raw)
    except ValueError:
        await message.reply(
            "❌ <b>Invalid Telegram ID.</b> Please send a numeric ID (e.g. <code>123456789</code>).",
            reply_markup=build_admin_cancel_keyboard("admins"),
            parse_mode="HTML",
        )
        return

    add_admin_user(session, new_admin_id, role=selected_role)
    from app.admin.keyboards import ROLE_EMOJI
    emoji = ROLE_EMOJI.get(selected_role, "🛡️")
    await message.reply(
        f"✅ <b>Admin Added!</b>\n\n"
        f"🆔 <b>Telegram ID:</b> <code>{new_admin_id}</code>\n"
        f"{emoji} <b>Role:</b> <code>{selected_role}</code>",
        reply_markup=build_admin_cancel_keyboard("admins"),
        parse_mode="HTML",
    )


# ─── Change Role: Show Role Selector ─────────────────────────────────────────

@router.callback_query(AdminMgmtAction.filter(F.action == "role_menu"))
async def callback_admin_role_menu(
    query: CallbackQuery, callback_data: AdminMgmtAction, session: Session
) -> None:
    """Show role selector to change an existing admin's role."""
    admin = get_admin_user(session, callback_data.admin_id)
    if not admin:
        await query.answer("❌ Admin not found.", show_alert=True)
        return

    if isinstance(query.message, Message):
        with contextlib.suppress(TelegramBadRequest):
            await query.message.edit_text(
                f"✏️ <b>Change Role</b>\n\n"
                f"🆔 Admin: <code>{admin.telegram_id}</code>\n"
                f"Current Role: <code>{admin.role}</code>\n\n"
                f"Select new role:",
                reply_markup=build_admin_role_selector_keyboard(admin.telegram_id, current_role=admin.role),
                parse_mode="HTML",
            )
    await query.answer()


@router.callback_query(AdminMgmtAction.filter(F.action == "set_role"))
async def callback_admin_set_role(
    query: CallbackQuery, callback_data: AdminMgmtAction, session: Session
) -> None:
    """Apply the selected new role to an admin."""
    updated = update_admin_role(session, callback_data.admin_id, callback_data.role)
    if not updated:
        await query.answer("❌ Admin not found.", show_alert=True)
        return

    await query.answer(f"✅ Role updated to {callback_data.role}!", show_alert=True)

    # Return to admin detail view
    from app.admin.keyboards import ROLE_EMOJI
    emoji = ROLE_EMOJI.get(updated.role, "🛡️")
    text = (
        f"👮 <b>Admin Detail</b>\n\n"
        f"🆔 <b>Telegram ID:</b> <code>{updated.telegram_id}</code>\n"
        f"{emoji} <b>Role:</b> <code>{updated.role}</code>\n"
        f"📅 <b>Added:</b> <code>{updated.created_at.strftime('%Y-%m-%d %H:%M')}</code>"
    )
    if isinstance(query.message, Message):
        with contextlib.suppress(TelegramBadRequest):
            await query.message.edit_text(
                text,
                reply_markup=build_admin_detail_keyboard(updated.telegram_id),
                parse_mode="HTML",
            )


# ─── Remove Admin: Confirm ────────────────────────────────────────────────────

@router.callback_query(AdminMgmtAction.filter(F.action == "confirm_remove"))
async def callback_admin_confirm_remove(
    query: CallbackQuery, callback_data: AdminMgmtAction, session: Session
) -> None:
    """Show removal confirmation screen."""
    admin = get_admin_user(session, callback_data.admin_id)
    if not admin:
        await query.answer("❌ Admin not found.", show_alert=True)
        return

    if isinstance(query.message, Message):
        with contextlib.suppress(TelegramBadRequest):
            await query.message.edit_text(
                f"⚠️ <b>Confirm Admin Removal</b>\n\n"
                f"Are you sure you want to remove admin <code>{admin.telegram_id}</code> "
                f"(Role: <code>{admin.role}</code>)?",
                reply_markup=build_admin_confirm_remove_keyboard(admin.telegram_id),
                parse_mode="HTML",
            )
    await query.answer()


@router.callback_query(AdminMgmtAction.filter(F.action == "do_remove"))
async def callback_admin_do_remove(
    query: CallbackQuery, callback_data: AdminMgmtAction, session: Session
) -> None:
    """Execute admin removal and return to admin list."""
    ok = remove_admin_user(session, callback_data.admin_id)
    if ok:
        await query.answer(f"🗑️ Admin {callback_data.admin_id} removed.", show_alert=True)
    else:
        await query.answer("❌ Admin not found or already removed.", show_alert=True)

    # Refresh list
    admins = list_admins(session)
    lines = ["👮 <b>Admin Management</b>\n"]
    if not admins:
        lines.append("⚠️ No admins configured yet.")
    else:
        from app.admin.keyboards import ROLE_EMOJI
        for adm in admins:
            emoji = ROLE_EMOJI.get(adm.role, "🛡️")
            lines.append(f"\n{emoji} <b>ID:</b> <code>{adm.telegram_id}</code>  Role: <code>{adm.role}</code>")

    if isinstance(query.message, Message):
        with contextlib.suppress(TelegramBadRequest):
            await query.message.edit_text(
                "\n".join(lines),
                reply_markup=build_admin_list_keyboard(admins),
                parse_mode="HTML",
            )
