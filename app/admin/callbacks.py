"""app/admin/callbacks.py — Strongly-typed CallbackData definitions for Admin Panel navigation."""

from aiogram.filters.callback_data import CallbackData


class AdminNav(CallbackData, prefix="adm_nav"):
    action: str  # home, stats, users, broadcast, admins, force_join, support, vip, language, close


class StatsNav(CallbackData, prefix="adm_stats"):
    period: str  # today, week, month


class UserNav(CallbackData, prefix="adm_usr"):
    page: int
    search: str = ""


class UserAction(CallbackData, prefix="adm_usr_act"):
    action: str  # view, give_vip, remove_vip, ban, unban, msg
    user_id: int


class VIPNav(CallbackData, prefix="adm_vip"):
    section: str  # features, plans, payments


class FeatureToggle(CallbackData, prefix="adm_feat"):
    feature_key: str


class VIPPlanAction(CallbackData, prefix="adm_plan"):
    action: str  # view, add, delete
    plan_id: int = 0


class PaymentAction(CallbackData, prefix="adm_pay"):
    action: str  # approve, reject, toggle_manual, toggle_auto
    payment_id: int = 0


class PaymentWalletAction(CallbackData, prefix="adm_wal"):
    action: str  # edit | clear | clear_confirm | clear_cancel
    field: str = ""  # binance_id|trc20_address|bep20_address|auto_trc20_address|auto_bep20_address


class AdminMgmtAction(CallbackData, prefix="adm_mgmt"):
    action: str  # list, add_start, confirm_remove, do_remove, role_menu, set_role
    admin_id: int = 0
    role: str = ""  # used for set_role


class ForceJoinAction(CallbackData, prefix="adm_fj"):
    action: str  # list, add, remove, toggle
    channel_id: str = ""


class AdminLangAction(CallbackData, prefix="adm_lang"):
    lang: str


class ReferralNav(CallbackData, prefix="adm_ref"):
    section: str = "menu"  # menu, tiers, referrals, rewards
    page: int = 1
    referrer_id: int = 0


class ReferralTierAction(CallbackData, prefix="adm_ref_tier"):
    action: str  # toggle, delete
    tier_id: int = 0
