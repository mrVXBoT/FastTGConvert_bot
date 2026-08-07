"""app/contacts_results.py — Contact-check result rendering, labels and menus."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.services.contacts_checker import ContactsCheckResult
from app.ui import EmojiRegistry
from app.ui.factory import Button
from app.ui.styles import ButtonStyle

CONTACTS_RESULT_LABELS = {
    "en": {
        "title": "Contact Check Done!",
        "checked": "Checked",
        "ok": "OK",
        "limited": "Limited",
        "two_fa": "2FA Locked",
        "banned": "Banned",
        "invalid": "Invalid",
        "inconclusive": "Inconclusive",
        "btn_checked": "🔨 Checked",
        "btn_ok": "✅ OK",
        "btn_limited": "⚠️ Limited",
        "btn_two_fa": "🔑 2FA Locked",
        "btn_banned": "🚫 Banned",
        "btn_invalid": "❌ Invalid",
        "btn_inconclusive": "❓ Inconclusive",
        "btn_retry": "🔄 Run Again",
        "btn_home": "🏠 Main Menu",
    },
    "bn": {
        "title": "কন্টাক্ট পরীক্ষা সম্পন্ন!",
        "checked": "পরীক্ষিত",
        "ok": "সঠিক",
        "limited": "সীমাবদ্ধ",
        "two_fa": "2FA লকড",
        "banned": "নিষিদ্ধ",
        "invalid": "অকার্যকর",
        "inconclusive": "নিশ্চিত নয়",
        "btn_checked": "🔨 পরীক্ষিত",
        "btn_ok": "✅ সঠিক",
        "btn_limited": "⚠️ সীমাবদ্ধ",
        "btn_two_fa": "🔑 2FA লকড",
        "btn_banned": "🚫 নিষিদ্ধ",
        "btn_invalid": "❌ অকার্যকর",
        "btn_inconclusive": "❓ নিশ্চিত নয়",
        "btn_retry": "🔄 আবার চালান",
        "btn_home": "🏠 মূল মেনু",
    },
    "hi": {
        "title": "कॉन्ट्रैक्ट जाँच संपन्न!",
        "checked": "जांचा गया",
        "ok": "सही",
        "limited": "सीमित",
        "two_fa": "2FA लॉक",
        "banned": "प्रतिबंधित",
        "invalid": "अमान्य",
        "inconclusive": "अनिश्चित",
        "btn_checked": "🔨 जांचा गया",
        "btn_ok": "✅ सही",
        "btn_limited": "⚠️ सीमित",
        "btn_two_fa": "🔑 2FA लॉक",
        "btn_banned": "🚫 प्रतिबंधित",
        "btn_invalid": "❌ अमान्य",
        "btn_inconclusive": "❓ अनिश्चित",
        "btn_retry": "🔄 फिर चलाएँ",
        "btn_home": "🏠 मुख्य मेनू",
    },
    "ur": {
        "title": "رابطوں کی جانچ مکمل!",
        "checked": "چیک شدہ",
        "ok": "ٹھیک",
        "limited": "محدود",
        "two_fa": "2FA مقفل",
        "banned": "ممنوع",
        "invalid": "ناقص",
        "inconclusive": "غیر یقینی",
        "btn_checked": "🔨 چیک شدہ",
        "btn_ok": "✅ ٹھیک",
        "btn_limited": "⚠️ محدود",
        "btn_two_fa": "🔑 2FA مقفل",
        "btn_banned": "🚫 ممنوع",
        "btn_invalid": "❌ ناقص",
        "btn_inconclusive": "❓ غیر یقینی",
        "btn_retry": "🔄 دوبارہ چلائیں",
        "btn_home": "🏠 مرکزی مینو",
    },
    "ar": {
        "title": "اكتمل فحص جهات الاتصال!",
        "checked": "مفحوص",
        "ok": "ناجح",
        "limited": "مقيد",
        "two_fa": "مقفل بـ 2FA",
        "banned": "محظور",
        "invalid": "غير صالح",
        "inconclusive": "غير مؤكد",
        "btn_checked": "🔨 مفحوص",
        "btn_ok": "✅ ناجح",
        "btn_limited": "⚠️ مقيد",
        "btn_two_fa": "🔑 مقفل بـ 2FA",
        "btn_banned": "🚫 محظور",
        "btn_invalid": "❌ غير صالح",
        "btn_inconclusive": "❓ غير مؤكد",
        "btn_retry": "🔄 إعادة التشغيل",
        "btn_home": "🏠 القائمة الرئيسية",
    },
    "zh": {
        "title": "联系人检查完成！",
        "checked": "已检查",
        "ok": "正常",
        "limited": "受限",
        "two_fa": "2FA 锁定",
        "banned": "已封禁",
        "invalid": "无效",
        "inconclusive": "不确定",
        "btn_checked": "🔨 已检查",
        "btn_ok": "✅ 正常",
        "btn_limited": "⚠️ 受限",
        "btn_two_fa": "🔑 2FA 锁定",
        "btn_banned": "🚫 已封禁",
        "btn_invalid": "❌ 无效",
        "btn_inconclusive": "❓ 不确定",
        "btn_retry": "🔄 重新运行",
        "btn_home": "🏠 主菜单",
    },
}

# Caption labels for the per-status ZIP archives (mirrors the session check
# format:  "📦 OK - 3 accounts").
CONTACTS_ZIP_CAPTIONS = {
    "en": {
        "accounts": "accounts",
        "ok": "OK",
        "limited": "Limited",
        "two_fa": "2FA Locked",
        "banned": "Banned",
        "invalid": "Invalid",
        "inconclusive": "Inconclusive",
        "report": "Contacts Report",
    },
    "bn": {
        "accounts": "অ্যাকাউন্ট",
        "ok": "সঠিক",
        "limited": "সীমাবদ্ধ",
        "two_fa": "2FA লকড",
        "banned": "নিষিদ্ধ",
        "invalid": "অকার্যকর",
        "inconclusive": "নিশ্চিত নয়",
        "report": "কন্টাক্ট রিপোর্ট",
    },
    "hi": {
        "accounts": "खाते",
        "ok": "सही",
        "limited": "सीमित",
        "two_fa": "2FA लॉक",
        "banned": "प्रतिबंधित",
        "invalid": "अमान्य",
        "inconclusive": "अनिश्चित",
        "report": "कॉन्ट्रैक्ट रिपोर्ट",
    },
    "ur": {
        "accounts": "اکاؤنٹس",
        "ok": "ٹھیک",
        "limited": "محدود",
        "two_fa": "2FA مقفل",
        "banned": "ممنوع",
        "invalid": "ناقص",
        "inconclusive": "غیر یقینی",
        "report": "رابطوں کی رپورٹ",
    },
    "ar": {
        "accounts": "حسابات",
        "ok": "ناجح",
        "limited": "مقيد",
        "two_fa": "مقفل بـ 2FA",
        "banned": "محظور",
        "invalid": "غير صالح",
        "inconclusive": "غير مؤكد",
        "report": "تقرير جهات الاتصال",
    },
    "zh": {
        "accounts": "个账号",
        "ok": "正常",
        "limited": "受限",
        "two_fa": "2FA 锁定",
        "banned": "已封禁",
        "invalid": "无效",
        "inconclusive": "不确定",
        "report": "联系人报告",
    },
}

_STATUS_TO_CAPTION_KEY = {
    "ok": "ok",
    "limited": "limited",
    "2fa": "two_fa",
    "banned": "banned",
    "invalid": "invalid",
    "inconclusive": "inconclusive",
}

_RESULT_ROW_EMOJIS = ("🔨 ", "✅ ", "⚠️ ", "🔑 ", "🚫 ", "❌ ", "❓ ")


def _result_button(label: str, emoji_key: str) -> InlineKeyboardButton:
    """Inline result button with a premium custom-emoji icon when configured."""
    custom_id = EmojiRegistry.get_custom_emoji_id(emoji_key)
    if custom_id and label.startswith(_RESULT_ROW_EMOJIS):
        label = label.split(" ", 1)[1]
        return InlineKeyboardButton(
            text=label,
            callback_data="contacts_stat:noop",
            icon_custom_emoji_id=custom_id,
        )
    return InlineKeyboardButton(text=label, callback_data="contacts_stat:noop")


def render_contacts_result(result: ContactsCheckResult, language: str = "en") -> str:
    labels = CONTACTS_RESULT_LABELS.get(language, CONTACTS_RESULT_LABELS["en"])
    return (
        f"✅ <b>{labels['title']}</b>\n"
        f"{EmojiRegistry.divider_line()}\n"
        f"🔨 {labels['checked']}: <b>{result.checked}</b>\n"
        f"✅ {labels['ok']}: <b>{result.ok}</b>\n"
        f"⚠️ {labels['limited']}: <b>{result.limited}</b>\n"
        f"🔑 {labels['two_fa']}: <b>{result.two_fa}</b>\n"
        f"🚫 {labels['banned']}: <b>{result.banned}</b>\n"
        f"❌ {labels['invalid']}: <b>{result.invalid}</b>\n"
        f"❓ {labels['inconclusive']}: <b>{result.inconclusive}</b>"
    )


def contacts_result_menu(
    result: ContactsCheckResult, language: str = "en"
) -> InlineKeyboardMarkup:
    labels = CONTACTS_RESULT_LABELS.get(language, CONTACTS_RESULT_LABELS["en"])
    rows = (
        (f"🔨 {labels['checked']}", result.checked, "CONTACT_CHECKED"),
        (f"✅ {labels['ok']}", result.ok, "CONTACT_OK"),
        (f"⚠️ {labels['limited']}", result.limited, "CONTACT_LIMITED"),
        (f"🔑 {labels['two_fa']}", result.two_fa, "SECURITY"),
        (f"🚫 {labels['banned']}", result.banned, "BANNED"),
        (f"❌ {labels['invalid']}", result.invalid, "INVALID"),
        (f"❓ {labels['inconclusive']}", result.inconclusive, "INCONCLUSIVE"),
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _result_button(label, emoji_key),
                InlineKeyboardButton(
                    text=str(value), callback_data="contacts_stat:noop"
                ),
            ]
            for label, value, emoji_key in rows
        ]
        + [
            [
                Button.create(
                    text=labels["btn_retry"],
                    callback_data="contacts_stat:retry",
                    style=ButtonStyle.PRIMARY,
                    emoji_key="REFRESH",
                ),
                Button.create(
                    text=labels["btn_home"],
                    callback_data="contacts_stat:home",
                    style=ButtonStyle.PRIMARY,
                    emoji_key="CONTACTS",
                ),
            ]
        ]
    )


def contacts_status_zip_caption(status: str, count: int, language: str = "en") -> str:
    """Build the document caption for a status ZIP, e.g. ``📦 OK - 3 accounts``."""
    labels = CONTACTS_ZIP_CAPTIONS.get(language, CONTACTS_ZIP_CAPTIONS["en"])
    key = _STATUS_TO_CAPTION_KEY.get(status, "inconclusive")
    return f"📦 {labels[key]} - {count} {labels['accounts']}"


def contacts_report_caption(language: str = "en") -> str:
    """Caption for the CSV report document."""
    labels = CONTACTS_ZIP_CAPTIONS.get(language, CONTACTS_ZIP_CAPTIONS["en"])
    return f"📄 {labels['report']} (.csv)"
