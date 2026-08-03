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
from app.ui import Button, ButtonStyle


def build_admin_main_menu_keyboard(lang: str = "en", admin_role: str = "SUPPORT") -> InlineKeyboardMarkup:
    """Main Admin Panel Inline Keyboard — sections visible depend on admin_role."""
    from app.admin.rbac import has_permission

    loc = get_admin_locale(lang)
    kb: list[list[InlineKeyboardButton]] = []

    # Stats + Users (SUPPORT+)
    row1: list[InlineKeyboardButton] = []
    if has_permission(admin_role, "SUPPORT"):
        row1.append(Button.create(loc["btn_stats"], AdminNav(action="stats").pack(), style=ButtonStyle.PRIMARY, emoji_key="STATS"))
        row1.append(Button.create(loc["btn_users"], AdminNav(action="users").pack(), style=ButtonStyle.PRIMARY, emoji_key="USERS"))
    if row1:
        kb.append(row1)

    # Broadcast + Support Settings (ADMIN+)
    row2: list[InlineKeyboardButton] = []
    if has_permission(admin_role, "ADMIN"):
        row2.append(Button.create(loc["btn_broadcast"], AdminNav(action="broadcast").pack(), style=ButtonStyle.PRIMARY, emoji_key="BROADCAST"))
        row2.append(Button.create(loc["btn_support"], AdminNav(action="support").pack(), style=ButtonStyle.PRIMARY, emoji_key="SUPPORT"))
    if row2:
        kb.append(row2)

    # Force Join + VIP (SUPER_ADMIN for Force Join, ADMIN for VIP)
    row3: list[InlineKeyboardButton] = []
    if has_permission(admin_role, "SUPER_ADMIN"):
        row3.append(Button.create(loc["btn_force_join"], AdminNav(action="force_join").pack(), style=ButtonStyle.PRIMARY, emoji_key="FORCE_JOIN"))
    if has_permission(admin_role, "ADMIN"):
        row3.append(Button.create(loc["btn_vip"], AdminNav(action="vip").pack(), style=ButtonStyle.SUCCESS, emoji_key="VIP"))
    if row3:
        kb.append(row3)

    # Admins Management (SUPER_ADMIN+)
    if has_permission(admin_role, "SUPER_ADMIN"):
        kb.append([Button.create(loc["btn_admins"], AdminNav(action="admins").pack(), style=ButtonStyle.PRIMARY, emoji_key="ADMIN")])

    # Language + Close (always visible)
    kb.append([
        Button.create(loc.get("btn_language", "Language"), AdminNav(action="language").pack(), style=ButtonStyle.PRIMARY, emoji_key="SETTINGS"),
        Button.create(loc["btn_close"], AdminNav(action="close").pack(), style=ButtonStyle.DANGER, emoji_key="CANCEL"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def build_stats_keyboard() -> InlineKeyboardMarkup:
    """Statistics Period Filter Keyboard."""
    kb = [
        [
            Button.create("Today", StatsNav(period="today").pack(), style=ButtonStyle.PRIMARY, emoji_key="STATS"),
            Button.create("This Week", StatsNav(period="week").pack(), style=ButtonStyle.PRIMARY, emoji_key="STATS"),
            Button.create("This Month", StatsNav(period="month").pack(), style=ButtonStyle.PRIMARY, emoji_key="STATS"),
        ],
        [
            Button.create("Back", AdminNav(action="home").pack(), style=ButtonStyle.PRIMARY, emoji_key="BACK"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def build_users_pagination_keyboard(users: list[User], page: int, total_pages: int, search: str = "") -> InlineKeyboardMarkup:
    """Users List Cards & Pagination Keyboard with individual quick view buttons."""
    kb: list[list[InlineKeyboardButton]] = []

    # Quick View action buttons for each user card on the page
    user_row: list[InlineKeyboardButton] = []
    for u in users:
        label = f"View @{u.username}" if u.username else f"View #{u.telegram_id}"
        user_row.append(
            Button.create(
                text=label,
                callback_data=UserAction(action="view", user_id=u.telegram_id).pack(),
                style=ButtonStyle.PRIMARY,
                emoji_key="VIEW",
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
        nav_row.append(Button.create("Previous", UserNav(page=page - 1, search=search).pack(), style=ButtonStyle.PRIMARY, emoji_key="BACK"))
    nav_row.append(InlineKeyboardButton(text=f"Page {page}/{max(1, total_pages)}", callback_data="ignore"))
    if page < total_pages:
        nav_row.append(Button.create("Next", UserNav(page=page + 1, search=search).pack(), style=ButtonStyle.PRIMARY, emoji_key="BACK"))

    kb.append(nav_row)
    kb.append([Button.create("Search User", "adm_usr_search", style=ButtonStyle.PRIMARY, emoji_key="SEARCH")])
    kb.append([Button.create("Back to Admin Panel", AdminNav(action="home").pack(), style=ButtonStyle.PRIMARY, emoji_key="BACK")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def build_user_detail_keyboard(user_id: int, is_vip: bool, is_banned: bool) -> InlineKeyboardMarkup:
    """User Details Action Keyboard."""
    vip_btn = (
        Button.create("Remove VIP", UserAction(action="remove_vip", user_id=user_id).pack(), style=ButtonStyle.DANGER, emoji_key="VIP")
        if is_vip
        else Button.create("Give VIP", UserAction(action="give_vip", user_id=user_id).pack(), style=ButtonStyle.SUCCESS, emoji_key="VIP")
    )

    ban_btn = (
        Button.create("Unban User", UserAction(action="unban", user_id=user_id).pack(), style=ButtonStyle.SUCCESS, emoji_key="UNBAN")
        if is_banned
        else Button.create("Ban User", UserAction(action="ban", user_id=user_id).pack(), style=ButtonStyle.DANGER, emoji_key="BAN")
    )

    kb = [
        [vip_btn, ban_btn],
        [Button.create("Send Direct Message", UserAction(action="msg", user_id=user_id).pack(), style=ButtonStyle.PRIMARY, emoji_key="MESSAGE")],
        [Button.create("Back to Users", AdminNav(action="users").pack(), style=ButtonStyle.PRIMARY, emoji_key="BACK")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def build_vip_menu_keyboard() -> InlineKeyboardMarkup:
    """VIP Management Main Submenu Keyboard."""
    kb = [
        [
            Button.create("Feature Access Control", VIPNav(section="features").pack(), style=ButtonStyle.PRIMARY, emoji_key="SECURITY"),
        ],
        [
            Button.create("VIP Plans Management", VIPNav(section="plans").pack(), style=ButtonStyle.SUCCESS, emoji_key="VIP"),
        ],
        [
            Button.create("Payment Gateways & Wallets", VIPNav(section="payments").pack(), style=ButtonStyle.PRIMARY, emoji_key="PAYMENT"),
        ],
        [
            Button.create("Back to Admin Panel", AdminNav(action="home").pack(), style=ButtonStyle.PRIMARY, emoji_key="BACK"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def build_feature_gates_keyboard(features: list[FeatureGate]) -> InlineKeyboardMarkup:
    """Feature Gate Access Level Toggle Keyboard."""
    kb = []
    for fg in features:
        is_vip = fg.access_level == "VIP_ONLY"
        status_label = "VIP ONLY" if is_vip else "FREE FOR ALL"
        style = ButtonStyle.SUCCESS if is_vip else ButtonStyle.PRIMARY
        kb.append(
            [
                Button.create(
                    text=f"{fg.title}: {status_label}",
                    callback_data=FeatureToggle(feature_key=fg.feature_key).pack(),
                    style=style,
                    emoji_key="SECURITY",
                )
            ]
        )
    kb.append([Button.create("Back to VIP Menu", AdminNav(action="vip").pack(), style=ButtonStyle.PRIMARY, emoji_key="BACK")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def build_vip_plans_keyboard(plans: list[VIPPlan]) -> InlineKeyboardMarkup:
    """VIP Plans Management Keyboard."""
    kb = []
    for plan in plans:
        kb.append(
            [
                Button.create(
                    text=f"{plan.name} — {plan.price}$",
                    callback_data=VIPPlanAction(action="view", plan_id=plan.id).pack(),
                    style=ButtonStyle.SUCCESS,
                    emoji_key="VIP",
                ),
                Button.create(
                    text="Delete",
                    callback_data=VIPPlanAction(action="delete", plan_id=plan.id).pack(),
                    style=ButtonStyle.DANGER,
                    emoji_key="DELETE",
                ),
            ]
        )
    kb.append([Button.create("Add New VIP Plan", VIPPlanAction(action="add", plan_id=0).pack(), style=ButtonStyle.SUCCESS, emoji_key="ADD")])
    kb.append([Button.create("Back to VIP Menu", AdminNav(action="vip").pack(), style=ButtonStyle.PRIMARY, emoji_key="BACK")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def build_pending_payments_keyboard(pending_list: list[Payment]) -> InlineKeyboardMarkup:
    """Pending Manual Payment Verification Keyboard with direct Inline Action buttons."""
    kb = []
    for p in pending_list:
        kb.append(
            [
                Button.create(f"Approve #{p.id} (${p.amount})", PaymentAction(action="approve", payment_id=p.id).pack(), style=ButtonStyle.SUCCESS, emoji_key="SUCCESS"),
                Button.create(f"Reject #{p.id}", PaymentAction(action="reject", payment_id=p.id).pack(), style=ButtonStyle.DANGER, emoji_key="CANCEL"),
            ]
        )
    kb.append([Button.create("Back to VIP Menu", AdminNav(action="vip").pack(), style=ButtonStyle.PRIMARY, emoji_key="BACK")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def build_force_join_keyboard(channels: list[ForceJoinChannel]) -> InlineKeyboardMarkup:
    """Force Join Channels Keyboard."""
    kb = []
    for ch in channels:
        status = "ON" if ch.is_active else "OFF"
        kb.append(
            [
                Button.create(f"{ch.title} ({status})", ForceJoinAction(action="toggle", channel_id=ch.channel_id).pack(), style=ButtonStyle.PRIMARY, emoji_key="FORCE_JOIN"),
                Button.create("Remove", ForceJoinAction(action="remove", channel_id=ch.channel_id).pack(), style=ButtonStyle.DANGER, emoji_key="DELETE"),
            ]
        )
    kb.append([Button.create("Add Channel", ForceJoinAction(action="add", channel_id="").pack(), style=ButtonStyle.SUCCESS, emoji_key="ADD")])
    kb.append([Button.create("Back to Admin Panel", AdminNav(action="home").pack(), style=ButtonStyle.PRIMARY, emoji_key="BACK")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def build_broadcast_preview_keyboard() -> InlineKeyboardMarkup:
    """Broadcast Confirmation Preview Keyboard."""
    kb = [
        [
            Button.create("Confirm & Send Broadcast", "adm_bcast_send", style=ButtonStyle.SUCCESS, emoji_key="BROADCAST"),
            Button.create("Cancel", "adm_bcast_cancel", style=ButtonStyle.DANGER, emoji_key="CANCEL"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def build_admin_cancel_keyboard(back_target: str = "home") -> InlineKeyboardMarkup:
    """Build a standard Cancel / Back inline button keyboard to exit prompt states."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [Button.create("Cancel", AdminNav(action=back_target).pack(), style=ButtonStyle.DANGER, emoji_key="CANCEL")]
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
        label = f"View #{adm.telegram_id}"
        row.append(
            Button.create(
                text=label,
                callback_data=AdminMgmtAction(action="view", admin_id=adm.telegram_id).pack(),
                style=ButtonStyle.PRIMARY,
                emoji_key="VIEW",
            )
        )
        if len(row) == 2:
            kb.append(row)
            row = []
    if row:
        kb.append(row)
    kb.append([Button.create("Add Admin", AdminMgmtAction(action="add_start").pack(), style=ButtonStyle.SUCCESS, emoji_key="ADD")])
    kb.append([Button.create("Back to Admin Panel", AdminNav(action="home").pack(), style=ButtonStyle.PRIMARY, emoji_key="BACK")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def build_admin_detail_keyboard(admin_id: int) -> InlineKeyboardMarkup:
    """Admin detail action keyboard: Change Role, Remove, Back."""
    kb = [
        [
            Button.create("Change Role", AdminMgmtAction(action="role_menu", admin_id=admin_id).pack(), style=ButtonStyle.PRIMARY, emoji_key="EDIT"),
            Button.create("Remove", AdminMgmtAction(action="confirm_remove", admin_id=admin_id).pack(), style=ButtonStyle.DANGER, emoji_key="DELETE"),
        ],
        [Button.create("Back to Admins", AdminNav(action="admins").pack(), style=ButtonStyle.PRIMARY, emoji_key="BACK")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def build_admin_role_selector_keyboard(admin_id: int, current_role: str = "") -> InlineKeyboardMarkup:
    """Role selector keyboard with current role highlighted."""
    kb: list[list[InlineKeyboardButton]] = []
    for role in ADMIN_ROLES:
        prefix = "✅ " if role == current_role else ""
        emoji = ROLE_EMOJI.get(role, "")
        kb.append([
            Button.create(
                text=f"{prefix}{emoji} {role}",
                callback_data=AdminMgmtAction(action="set_role", admin_id=admin_id, role=role).pack(),
                style=ButtonStyle.PRIMARY,
                include_emoji=False,
            )
        ])
    kb.append([Button.create("Back", AdminMgmtAction(action="view", admin_id=admin_id).pack(), style=ButtonStyle.PRIMARY, emoji_key="BACK")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def build_admin_confirm_remove_keyboard(admin_id: int) -> InlineKeyboardMarkup:
    """Confirm removal keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            Button.create("Yes, Remove", AdminMgmtAction(action="do_remove", admin_id=admin_id).pack(), style=ButtonStyle.DANGER, emoji_key="DELETE"),
            Button.create("Cancel", AdminMgmtAction(action="view", admin_id=admin_id).pack(), style=ButtonStyle.PRIMARY, emoji_key="CANCEL"),
        ]
    ])


def build_add_admin_role_selector_keyboard() -> InlineKeyboardMarkup:
    """Role selector for adding a NEW admin (no existing admin_id yet)."""
    kb: list[list[InlineKeyboardButton]] = []
    for role in ADMIN_ROLES:
        emoji = ROLE_EMOJI.get(role, "")
        kb.append([
            Button.create(
                text=f"{emoji} {role}",
                callback_data=AdminMgmtAction(action="add_start", role=role).pack(),
                style=ButtonStyle.PRIMARY,
                include_emoji=False,
            )
        ])
    kb.append([Button.create("Cancel", AdminNav(action="admins").pack(), style=ButtonStyle.DANGER, emoji_key="CANCEL")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


ADMIN_LANGUAGES = {
    "bn": ("বাংলা", "FLAG_BN"),
    "en": ("English", "FLAG_EN"),
    "hi": ("हिन्दी", "FLAG_HI"),
    "ur": ("اردو", "FLAG_UR"),
    "ar": ("العربية", "FLAG_AR"),
    "zh": ("中文", "FLAG_ZH"),
}


def build_admin_language_keyboard(current_lang: str = "en") -> InlineKeyboardMarkup:
    """Build Admin Panel language selection keyboard."""
    from app.admin.callbacks import AdminLangAction

    kb = []
    for code, (label, emoji_key) in ADMIN_LANGUAGES.items():
        prefix = "✅ " if code == current_lang else ""
        kb.append([
            Button.create(
                f"{prefix}{label}",
                AdminLangAction(lang=code).pack(),
                style=ButtonStyle.PRIMARY,
                emoji_key=emoji_key,
            )
        ])
    kb.append([Button.create("Back", AdminNav(action="home").pack(), style=ButtonStyle.PRIMARY, emoji_key="BACK")])
    return InlineKeyboardMarkup(inline_keyboard=kb)
