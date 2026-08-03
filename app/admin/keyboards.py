"""app/admin/keyboards.py — Dynamic Inline Keyboards for all Admin Panel screens."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.admin.callbacks import (
    AdminMgmtAction,
    AdminNav,
    FeatureToggle,
    ForceJoinAction,
    PaymentAction,
    StatsNav,
    UserAction,
    UserNav,
    VIPNav,
    VIPPlanAction,
)
from app.db.models import AdminUser, FeatureGate, ForceJoinChannel, Payment, VIPPlan

if TYPE_CHECKING:
    from app.db.models import User

from app.locales import get_admin_locale


def build_admin_main_menu_keyboard(lang: str = "en", admin_role: str = "SUPPORT") -> InlineKeyboardMarkup:
    """Main Admin Panel Inline Keyboard — sections visible depend on admin_role."""
    from app.admin.rbac import has_permission

    loc = get_admin_locale(lang)
    kb: list[list[InlineKeyboardButton]] = []

    # Stats + Users (SUPPORT+)
    row1: list[InlineKeyboardButton] = []
    if has_permission(admin_role, "SUPPORT"):
        row1.append(InlineKeyboardButton(text=loc["btn_stats"], callback_data=AdminNav(action="stats").pack()))
        row1.append(InlineKeyboardButton(text=loc["btn_users"], callback_data=AdminNav(action="users").pack()))
    if row1:
        kb.append(row1)

    # Broadcast + Support Settings (ADMIN+)
    row2: list[InlineKeyboardButton] = []
    if has_permission(admin_role, "ADMIN"):
        row2.append(InlineKeyboardButton(text=loc["btn_broadcast"], callback_data=AdminNav(action="broadcast").pack()))
        row2.append(InlineKeyboardButton(text=loc["btn_support"], callback_data=AdminNav(action="support").pack()))
    if row2:
        kb.append(row2)

    # Force Join + VIP (SUPER_ADMIN for Force Join, ADMIN for VIP)
    row3: list[InlineKeyboardButton] = []
    if has_permission(admin_role, "SUPER_ADMIN"):
        row3.append(InlineKeyboardButton(text=loc["btn_force_join"], callback_data=AdminNav(action="force_join").pack()))
    if has_permission(admin_role, "ADMIN"):
        row3.append(InlineKeyboardButton(text=loc["btn_vip"], callback_data=AdminNav(action="vip").pack()))
    if row3:
        kb.append(row3)

    # Admins Management (SUPER_ADMIN+)
    if has_permission(admin_role, "SUPER_ADMIN"):
        kb.append([InlineKeyboardButton(text=loc["btn_admins"], callback_data=AdminNav(action="admins").pack())])

    # Language + Close (always visible)
    kb.append([
        InlineKeyboardButton(text="🌐 Language", callback_data=AdminNav(action="language").pack()),
        InlineKeyboardButton(text=loc["btn_close"], callback_data=AdminNav(action="close").pack()),
    ])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def build_stats_keyboard() -> InlineKeyboardMarkup:
    """Statistics Period Filter Keyboard."""
    kb = [
        [
            InlineKeyboardButton(text="📅 Today", callback_data=StatsNav(period="today").pack()),
            InlineKeyboardButton(text="📆 This Week", callback_data=StatsNav(period="week").pack()),
            InlineKeyboardButton(text="📅 This Month", callback_data=StatsNav(period="month").pack()),
        ],
        [
            InlineKeyboardButton(text="⬅️ Back", callback_data=AdminNav(action="home").pack()),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def build_users_pagination_keyboard(users: list[User], page: int, total_pages: int, search: str = "") -> InlineKeyboardMarkup:
    """Users List Cards & Pagination Keyboard with individual quick view buttons."""
    kb: list[list[InlineKeyboardButton]] = []

    # Quick View action buttons for each user card on the page
    user_row: list[InlineKeyboardButton] = []
    for u in users:
        label = f"👁 View @{u.username}" if u.username else f"👁 View #{u.telegram_id}"
        user_row.append(
            InlineKeyboardButton(
                text=label,
                callback_data=UserAction(action="view", user_id=u.telegram_id).pack(),
            )
        )
        if len(user_row) == 2:
            kb.append(user_row)
            user_row = []
    if user_row:
        kb.append(user_row)

    # Pagination navigation row
    nav_row: list[InlineKeyboardButton] = []
    if page > 1:
        nav_row.append(InlineKeyboardButton(text="⬅️ Previous", callback_data=UserNav(page=page - 1, search=search).pack()))
    nav_row.append(InlineKeyboardButton(text=f"Page {page}/{max(1, total_pages)}", callback_data="ignore"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton(text="Next ➡️", callback_data=UserNav(page=page + 1, search=search).pack()))

    kb.append(nav_row)
    kb.append([InlineKeyboardButton(text="🔍 Search User", callback_data="adm_usr_search")])
    kb.append([InlineKeyboardButton(text="⬅️ Back to Admin Panel", callback_data=AdminNav(action="home").pack())])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def build_user_detail_keyboard(user_id: int, is_vip: bool, is_banned: bool) -> InlineKeyboardMarkup:
    """User Details Action Keyboard."""
    vip_btn = (
        InlineKeyboardButton(text="❌ Remove VIP", callback_data=UserAction(action="remove_vip", user_id=user_id).pack())
        if is_vip
        else InlineKeyboardButton(text="💎 Give VIP", callback_data=UserAction(action="give_vip", user_id=user_id).pack())
    )

    ban_btn = (
        InlineKeyboardButton(text="🟢 Unban User", callback_data=UserAction(action="unban", user_id=user_id).pack())
        if is_banned
        else InlineKeyboardButton(text="🚫 Ban User", callback_data=UserAction(action="ban", user_id=user_id).pack())
    )

    kb = [
        [vip_btn, ban_btn],
        [InlineKeyboardButton(text="📩 Send Direct Message", callback_data=UserAction(action="msg", user_id=user_id).pack())],
        [InlineKeyboardButton(text="⬅️ Back to Users", callback_data=AdminNav(action="users").pack())],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def build_vip_menu_keyboard() -> InlineKeyboardMarkup:
    """VIP Management Main Submenu Keyboard."""
    kb = [
        [
            InlineKeyboardButton(text="⚙️ Feature Access Control", callback_data=VIPNav(section="features").pack()),
        ],
        [
            InlineKeyboardButton(text="📦 VIP Plans Management", callback_data=VIPNav(section="plans").pack()),
        ],
        [
            InlineKeyboardButton(text="💳 Payment Gateways & Wallets", callback_data=VIPNav(section="payments").pack()),
        ],
        [
            InlineKeyboardButton(text="⬅️ Back to Admin Panel", callback_data=AdminNav(action="home").pack()),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def build_feature_gates_keyboard(features: list[FeatureGate]) -> InlineKeyboardMarkup:
    """Feature Gate Access Level Toggle Keyboard."""
    kb = []
    for fg in features:
        status_icon = "🟢 VIP ONLY" if fg.access_level == "VIP_ONLY" else "⚪ FREE FOR ALL"
        kb.append(
            [
                InlineKeyboardButton(
                    text=f"{fg.title}: {status_icon}",
                    callback_data=FeatureToggle(feature_key=fg.feature_key).pack(),
                )
            ]
        )
    kb.append([InlineKeyboardButton(text="⬅️ Back to VIP Menu", callback_data=AdminNav(action="vip").pack())])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def build_vip_plans_keyboard(plans: list[VIPPlan]) -> InlineKeyboardMarkup:
    """VIP Plans Management Keyboard."""
    kb = []
    for plan in plans:
        kb.append(
            [
                InlineKeyboardButton(
                    text=f"📅 {plan.name} — {plan.price}$",
                    callback_data=VIPPlanAction(action="view", plan_id=plan.id).pack(),
                ),
                InlineKeyboardButton(
                    text="🗑️ Delete",
                    callback_data=VIPPlanAction(action="delete", plan_id=plan.id).pack(),
                ),
            ]
        )
    kb.append([InlineKeyboardButton(text="➕ Add New VIP Plan", callback_data=VIPPlanAction(action="add", plan_id=0).pack())])
    kb.append([InlineKeyboardButton(text="⬅️ Back to VIP Menu", callback_data=AdminNav(action="vip").pack())])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def build_pending_payments_keyboard(pending_list: list[Payment]) -> InlineKeyboardMarkup:
    """Pending Manual Payment Verification Keyboard with direct Inline Action buttons."""
    kb = []
    for p in pending_list:
        kb.append(
            [
                InlineKeyboardButton(text=f"✅ Approve #{p.id} (${p.amount})", callback_data=PaymentAction(action="approve", payment_id=p.id).pack()),
                InlineKeyboardButton(text=f"❌ Reject #{p.id}", callback_data=PaymentAction(action="reject", payment_id=p.id).pack()),
            ]
        )
    kb.append([InlineKeyboardButton(text="⬅️ Back to VIP Menu", callback_data=AdminNav(action="vip").pack())])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def build_force_join_keyboard(channels: list[ForceJoinChannel]) -> InlineKeyboardMarkup:
    """Force Join Channels Keyboard."""
    kb = []
    for ch in channels:
        status = "🟢 ON" if ch.is_active else "🔴 OFF"
        kb.append(
            [
                InlineKeyboardButton(text=f"{ch.title} ({status})", callback_data=ForceJoinAction(action="toggle", channel_id=ch.channel_id).pack()),
                InlineKeyboardButton(text="🗑️ Remove", callback_data=ForceJoinAction(action="remove", channel_id=ch.channel_id).pack()),
            ]
        )
    kb.append([InlineKeyboardButton(text="➕ Add Channel", callback_data=ForceJoinAction(action="add", channel_id="").pack())])
    kb.append([InlineKeyboardButton(text="⬅️ Back to Admin Panel", callback_data=AdminNav(action="home").pack())])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def build_broadcast_preview_keyboard() -> InlineKeyboardMarkup:
    """Broadcast Confirmation Preview Keyboard."""
    kb = [
        [
            InlineKeyboardButton(text="🚀 Confirm & Send Broadcast", callback_data="adm_bcast_send"),
            InlineKeyboardButton(text="❌ Cancel", callback_data="adm_bcast_cancel"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def build_admin_cancel_keyboard(back_target: str = "home") -> InlineKeyboardMarkup:
    """Build a standard Cancel / Back inline button keyboard to exit prompt states."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Cancel", callback_data=AdminNav(action=back_target).pack())]
        ]
    )


ADMIN_ROLES = ["SUPER_ADMIN", "ADMIN", "SUPPORT"]

ROLE_EMOJI = {
    "SUPER_ADMIN": "🔱",
    "ADMIN": "🛡️",
    "SUPPORT": "🎧",
    "OWNER": "👑",
}


def build_admin_list_keyboard(admins: list[AdminUser]) -> InlineKeyboardMarkup:
    """Admin list keyboard: one View button per admin, plus Add Admin and Back."""
    kb: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for adm in admins:
        label = f"👁 View #{adm.telegram_id}"
        row.append(
            InlineKeyboardButton(
                text=label,
                callback_data=AdminMgmtAction(action="view", admin_id=adm.telegram_id).pack(),
            )
        )
        if len(row) == 2:
            kb.append(row)
            row = []
    if row:
        kb.append(row)
    kb.append([InlineKeyboardButton(text="➕ Add Admin", callback_data=AdminMgmtAction(action="add_start").pack())])
    kb.append([InlineKeyboardButton(text="⬅️ Back to Admin Panel", callback_data=AdminNav(action="home").pack())])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def build_admin_detail_keyboard(admin_id: int) -> InlineKeyboardMarkup:
    """Admin detail action keyboard: Change Role, Remove, Back."""
    kb = [
        [
            InlineKeyboardButton(text="✏️ Change Role", callback_data=AdminMgmtAction(action="role_menu", admin_id=admin_id).pack()),
            InlineKeyboardButton(text="❌ Remove", callback_data=AdminMgmtAction(action="confirm_remove", admin_id=admin_id).pack()),
        ],
        [InlineKeyboardButton(text="⬅️ Back to Admins", callback_data=AdminNav(action="admins").pack())],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def build_admin_role_selector_keyboard(admin_id: int, current_role: str = "") -> InlineKeyboardMarkup:
    """Role selector keyboard with current role highlighted."""
    kb: list[list[InlineKeyboardButton]] = []
    for role in ADMIN_ROLES:
        prefix = "✅ " if role == current_role else ""
        emoji = ROLE_EMOJI.get(role, "")
        kb.append([
            InlineKeyboardButton(
                text=f"{prefix}{emoji} {role}",
                callback_data=AdminMgmtAction(action="set_role", admin_id=admin_id, role=role).pack(),
            )
        ])
    kb.append([InlineKeyboardButton(text="⬅️ Back", callback_data=AdminMgmtAction(action="view", admin_id=admin_id).pack())])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def build_admin_confirm_remove_keyboard(admin_id: int) -> InlineKeyboardMarkup:
    """Confirm removal keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🗑️ Yes, Remove", callback_data=AdminMgmtAction(action="do_remove", admin_id=admin_id).pack()),
            InlineKeyboardButton(text="❌ Cancel", callback_data=AdminMgmtAction(action="view", admin_id=admin_id).pack()),
        ]
    ])


def build_add_admin_role_selector_keyboard() -> InlineKeyboardMarkup:
    """Role selector for adding a NEW admin (no existing admin_id yet)."""
    kb: list[list[InlineKeyboardButton]] = []
    for role in ADMIN_ROLES:
        emoji = ROLE_EMOJI.get(role, "")
        kb.append([
            InlineKeyboardButton(
                text=f"{emoji} {role}",
                callback_data=AdminMgmtAction(action="add_start", role=role).pack(),
            )
        ])
    kb.append([InlineKeyboardButton(text="❌ Cancel", callback_data=AdminNav(action="admins").pack())])
    return InlineKeyboardMarkup(inline_keyboard=kb)


ADMIN_LANGUAGES = {
    "en": "🇬🇧 English",
    "bn": "🇧🇩 বাংলা",
    "hi": "🇮🇳 हिन्दी",
    "ur": "🇵🇰 اردو",
    "ar": "🇸🇦 العربية",
    "zh": "🇨🇳 中文",
}


def build_admin_language_keyboard(current_lang: str = "en") -> InlineKeyboardMarkup:
    """Build Admin Panel language selection keyboard."""
    from app.admin.callbacks import AdminLangAction

    kb = []
    for code, label in ADMIN_LANGUAGES.items():
        prefix = "✅ " if code == current_lang else ""
        kb.append([InlineKeyboardButton(text=f"{prefix}{label}", callback_data=AdminLangAction(lang=code).pack())])
    kb.append([InlineKeyboardButton(text="⬅️ Back", callback_data=AdminNav(action="home").pack())])
    return InlineKeyboardMarkup(inline_keyboard=kb)
