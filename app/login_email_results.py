"""app/login_email_results.py — Login Email result rendering, labels and menus."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.services.login_email import LoginEmailBatchResult
from app.ui import EmojiRegistry
from app.ui.factory import Button
from app.ui.styles import ButtonStyle

LOGIN_EMAIL_RESULT_LABELS = {
    "en": {
        "title": "Login Email Change Results",
        "total": "Total Accounts",
        "updated": "Email Updated",
        "no_email": "No Login Email",
        "failed": "Failed / Expired",
        "btn_total": "Total",
        "btn_updated": "Updated",
        "btn_no_email": "No Email",
        "btn_failed": "Failed",
        "btn_archive_updated": "Updated",
        "btn_archive_no_email": "No Email",
        "btn_archive_failed": "Failed",
        "btn_archive_all": "Full Archive",
        "organize_hint": "Organize: download each category archive",
        "zip_updated": "Login Email Updated - {count} accounts",
        "zip_no_email": "No Login Email - {count} accounts",
        "zip_failed": "Failed / Expired - {count} accounts",
        "zip_all": "Classified Archive (report.txt included)",
        "expired": "❌ Archive expired. Please run Login Email again.",
        "btn_home": "Main Menu",
    },
    "bn": {
        "title": "লগইন ইমেল পরিবর্তনের ফলাফল",
        "total": "মোট অ্যাকাউন্ট",
        "updated": "ইমেল আপডেট হয়েছে",
        "no_email": "কোনো লগইন ইমেল নেই",
        "failed": "ব্যর্থ / মেয়াদোত্তীর্ণ",
        "btn_total": "মোট",
        "btn_updated": "আপডেট হয়েছে",
        "btn_no_email": "ইমেল নেই",
        "btn_failed": "ব্যর্থ",
        "btn_archive_updated": "আপডেট হয়েছে",
        "btn_archive_no_email": "ইমেল নেই",
        "btn_archive_failed": "ব্যর্থ",
        "btn_archive_all": "সম্পূর্ণ আর্কাইভ",
        "organize_hint": "সাজান: প্রতিটি ক্যাটাগরির আর্কাইভ ডাউনলোড করুন",
        "zip_updated": "লগইন ইমেল আপডেট - {count}টি অ্যাকাউন্ট",
        "zip_no_email": "কোনো লগইন ইমেল নেই - {count}টি অ্যাকাউন্ট",
        "zip_failed": "ব্যর্থ / মেয়াদোত্তীর্ণ - {count}টি অ্যাকাউন্ট",
        "zip_all": "শ্রেণিবদ্ধ আর্কাইভ (report.txt সহ)",
        "expired": "❌ আর্কাইভের মেয়াদ শেষ। আবার লগইন ইমেল চালান।",
        "btn_home": "মূল মেনু",
    },
    "hi": {
        "title": "लॉगिन ईमेल परिवर्तन परिणाम",
        "total": "कुल खाते",
        "updated": "ईमेल अपडेट किया गया",
        "no_email": "कोई लॉगिन ईमेल नहीं",
        "failed": "विफल / समाप्त",
        "btn_total": "कुल",
        "btn_updated": "अपडेट",
        "btn_no_email": "ईमेल नहीं",
        "btn_failed": "विफल",
        "btn_archive_updated": "अपडेट",
        "btn_archive_no_email": "ईमेल नहीं",
        "btn_archive_failed": "विफल",
        "btn_archive_all": "पूरा संग्रह",
        "organize_hint": "व्यवस्थित करें: प्रत्येक श्रेणी का संग्रह डाउनलोड करें",
        "zip_updated": "लॉगिन ईमेल अपडेट - {count} खाते",
        "zip_no_email": "कोई लॉगिन ईमेल नहीं - {count} खाते",
        "zip_failed": "विफल / समाप्त - {count} खाते",
        "zip_all": "वर्गीकृत संग्रह (report.txt शामिल)",
        "expired": "❌ संग्रह समाप्त हो गया। कृपया फिर से लॉगिन ईमेल चलाएँ।",
        "btn_home": "मुख्य मेनू",
    },
    "ur": {
        "title": "لاگ ان ای میل تبدیلی کے نتائج",
        "total": "کل اکاؤنٹس",
        "updated": "ای میل اپ ڈیٹ ہو گئی",
        "no_email": "کوئی لاگ ان ای میل نہیں",
        "failed": "ناکام / ختم شدہ",
        "btn_total": "کل",
        "btn_updated": "اپ ڈیٹ",
        "btn_no_email": "ای میل نہیں",
        "btn_failed": "ناکام",
        "btn_archive_updated": "اپ ڈیٹ",
        "btn_archive_no_email": "ای میل نہیں",
        "btn_archive_failed": "ناکام",
        "btn_archive_all": "مکمل آرکائیو",
        "organize_hint": "ترتیب دیں: ہر زمرے کا آرکائیو ڈاؤن لوڈ کریں",
        "zip_updated": "لاگ ان ای میل اپ ڈیٹ - {count} اکاؤنٹس",
        "zip_no_email": "کوئی لاگ ان ای میل نہیں - {count} اکاؤنٹس",
        "zip_failed": "ناکام / ختم شدہ - {count} اکاؤنٹس",
        "zip_all": "درجہ بند آرکائیو (report.txt شامل)",
        "expired": "❌ آرکائیو کی میعاد ختم ہو گئی۔ براہ کرم دوبارہ لاگ ان ای میل چلائیں۔",
        "btn_home": "مرکزی مینو",
    },
    "ar": {
        "title": "نتائج تغيير بريد التسجيل",
        "total": "إجمالي الحسابات",
        "updated": "تم تحديث البريد",
        "no_email": "لا يوجد بريد تسجيل",
        "failed": "فشل / منتهي الصلاحية",
        "btn_total": "الإجمالي",
        "btn_updated": "مُحدَّث",
        "btn_no_email": "لا بريد",
        "btn_failed": "فشل",
        "btn_archive_updated": "مُحدَّث",
        "btn_archive_no_email": "لا بريد",
        "btn_archive_failed": "فشل",
        "btn_archive_all": "الأرشيف الكامل",
        "organize_hint": "تنظيم: حمّل أرشيف كل فئة",
        "zip_updated": "تم تحديث بريد التسجيل - {count} حساب",
        "zip_no_email": "لا يوجد بريد تسجيل - {count} حساب",
        "zip_failed": "فشل / منتهي الصلاحية - {count} حساب",
        "zip_all": "أرشيف مصنَّف (يتضمن report.txt)",
        "expired": "❌ انتهى الأرشيف. يرجى تشغيل بريد التسجيل مجددًا.",
        "btn_home": "القائمة الرئيسية",
    },
    "zh": {
        "title": "修改登录邮箱结果",
        "total": "总账户",
        "updated": "邮箱已更新",
        "no_email": "无登录邮箱",
        "failed": "失败 / 已过期",
        "btn_total": "总计",
        "btn_updated": "已更新",
        "btn_no_email": "无邮箱",
        "btn_failed": "失败",
        "btn_archive_updated": "已更新",
        "btn_archive_no_email": "无邮箱",
        "btn_archive_failed": "失败",
        "btn_archive_all": "完整压缩包",
        "organize_hint": "整理：下载每个类别的压缩包",
        "zip_updated": "登录邮箱已更新 - {count} 个账户",
        "zip_no_email": "无登录邮箱 - {count} 个账户",
        "zip_failed": "失败 / 已过期 - {count} 个账户",
        "zip_all": "分类压缩包（含 report.txt）",
        "expired": "❌ 压缩包已过期。请重新运行登录邮箱功能。",
        "btn_home": "主菜单",
    },
}

_EMOJI_BY_ROW = {
    "total": "🔨",
    "updated": "🟢",
    "no_email": "🟡",
    "failed": "❌",
}

_EMOJI_KEY_BY_ROW = {
    "total": "TOTAL",
    "updated": "ACTIVE",
    "no_email": "INVALID",
    "failed": "FAILED",
}

_BUTTON_PREFIXES = ("🔨 ", "🟢 ", "🟡 ", "❌ ")


def _row_button(label: str, emoji_key: str) -> InlineKeyboardButton:
    custom_id = EmojiRegistry.get_custom_emoji_id(emoji_key)
    if custom_id and label.startswith(_BUTTON_PREFIXES):
        return InlineKeyboardButton(
            text=label.split(" ", 1)[1],
            callback_data="login_email:noop",
            icon_custom_emoji_id=custom_id,
        )
    return InlineKeyboardButton(text=label, callback_data="login_email:noop")


def render_login_email_result(
    result: LoginEmailBatchResult, language: str = "en"
) -> str:
    labels = LOGIN_EMAIL_RESULT_LABELS.get(language, LOGIN_EMAIL_RESULT_LABELS["en"])
    counts = {
        "total": result.total,
        "updated": result.changed_count,
        "no_email": result.no_email_count,
        "failed": result.error_count,
    }
    lines = [
        f"📧 <b>{labels['title']}</b>",
        EmojiRegistry.divider_line(),
        f"{_EMOJI_BY_ROW['total']} {labels['total']}: <b>{counts['total']}</b>",
        f"{_EMOJI_BY_ROW['updated']} {labels['updated']}: <b>{counts['updated']}</b>",
        f"{_EMOJI_BY_ROW['no_email']} {labels['no_email']}: <b>{counts['no_email']}</b>",
        f"{_EMOJI_BY_ROW['failed']} {labels['failed']}: <b>{counts['failed']}</b>",
        EmojiRegistry.divider_line(),
        f"🗂 {labels['organize_hint']}",
    ]
    return "\n".join(lines)


def login_email_result_menu(
    result: LoginEmailBatchResult, language: str = "en"
) -> InlineKeyboardMarkup:
    labels = LOGIN_EMAIL_RESULT_LABELS.get(language, LOGIN_EMAIL_RESULT_LABELS["en"])
    counts = {
        "total": result.total,
        "updated": result.changed_count,
        "no_email": result.no_email_count,
        "failed": result.error_count,
    }
    rows = [
        (f"🔨 {labels['btn_total']}", "total", "TOTAL"),
        (f"🟢 {labels['btn_updated']}", "updated", "ACTIVE"),
        (f"🟡 {labels['btn_no_email']}", "no_email", "INVALID"),
        (f"❌ {labels['btn_failed']}", "failed", "FAILED"),
    ]
    row_buttons: list[list[InlineKeyboardButton]] = [
        [
            _row_button(label, emoji_key),
            InlineKeyboardButton(
                text=str(counts[key]), callback_data="login_email:noop"
            ),
        ]
        for label, key, emoji_key in rows
    ]
    organize_buttons = [
        Button.create(
            text=labels["btn_archive_updated"],
            callback_data="login_email:organize:updated",
            style=ButtonStyle.PRIMARY,
            emoji_key="ACTIVE",
        ),
        Button.create(
            text=labels["btn_archive_no_email"],
            callback_data="login_email:organize:noemail",
            style=ButtonStyle.PRIMARY,
            emoji_key="INVALID",
        ),
        Button.create(
            text=labels["btn_archive_failed"],
            callback_data="login_email:organize:failed",
            style=ButtonStyle.PRIMARY,
            emoji_key="FAILED",
        ),
        Button.create(
            text=labels["btn_archive_all"],
            callback_data="login_email:organize:all",
            style=ButtonStyle.PRIMARY,
            emoji_key="FOLDER",
        ),
    ]
    return InlineKeyboardMarkup(
        inline_keyboard=row_buttons
        + [organize_buttons[:2], organize_buttons[2:]]
        + [
            [
                Button.create(
                    text=labels["btn_home"],
                    callback_data="menu:back",
                    style=ButtonStyle.PRIMARY,
                    emoji_key="BACK",
                ),
            ]
        ]
    )


def login_email_zip_caption(kind: str, count: int, language: str = "en") -> str:
    labels = LOGIN_EMAIL_RESULT_LABELS.get(language, LOGIN_EMAIL_RESULT_LABELS["en"])
    key = {
        "updated": "zip_updated",
        "noemail": "zip_no_email",
        "failed": "zip_failed",
        "all": "zip_all",
    }.get(kind, "zip_all")
    return labels[key].format(count=count)
