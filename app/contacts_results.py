"""app/contacts_results.py — Contact-check result rendering, labels and menus."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.services.contacts_checker import ContactsCheckResult
from app.ui import EmojiRegistry
from app.ui.factory import Button
from app.ui.styles import ButtonStyle

CONTACTS_RESULT_LABELS = {
    "en": {
        "title": "Check Contact Permissions",
        "checked": "Checked",
        "healthy": "Healthy account",
        "restricted": "Restricted account",
        "invalid": "Invalid account",
        "error": "Error account",
        "retry_note": "Retry: unable to connect to the Telegram server, it is recommended that you check the file again",
        "btn_checked": "Checked",
        "btn_healthy": "Healthy",
        "btn_restricted": "Restricted",
        "btn_invalid": "Invalid",
        "btn_error": "Error",
        "btn_retry": "🔄 Run Again",
        "btn_home": "🏠 Main Menu",
    },
    "bn": {
        "title": "কন্টাক্ট পরীক্ষা সম্পন্ন!",
        "checked": "পরীক্ষিত",
        "healthy": "সুস্থ অ্যাকাউন্ট",
        "restricted": "সীমাবদ্ধ অ্যাকাউন্ট",
        "invalid": "অকার্যকর অ্যাকাউন্ট",
        "error": "ত্রুটিপূর্ণ অ্যাকাউন্ট",
        "retry_note": "রিট্রাই: টেলিগ্রাম সার্ভারে সংযোগ করা যায়নি, ফাইলটি আবার চেক করার পরামর্শ দেওয়া হচ্ছে",
        "btn_checked": "পরীক্ষিত",
        "btn_healthy": "সুস্থ",
        "btn_restricted": "সীমাবদ্ধ",
        "btn_invalid": "অকার্যকর",
        "btn_error": "ত্রুটি",
        "btn_retry": "🔄 আবার চালান",
        "btn_home": "🏠 মূল মেনু",
    },
    "hi": {
        "title": "कॉन्ट्रैक्ट जाँच संपन्न!",
        "checked": "जांचा गया",
        "healthy": "स्वस्थ अकाउंट",
        "restricted": "सीमित अकाउंट",
        "invalid": "अमान्य अकाउंट",
        "error": "त्रुटि अकाउंट",
        "retry_note": "रीट्राय: टेलीग्राम सर्वर से कनेक्ट नहीं हो सका, फ़ाइल दोबारा जाँचने की सलाह दी जाती है",
        "btn_checked": "जांचा गया",
        "btn_healthy": "🟢 स्वस्थ",
        "btn_restricted": "🟡 सीमित",
        "btn_invalid": "❌ अमान्य",
        "btn_error": "☑️ त्रुटि",
        "btn_retry": "🔄 फिर चलाएँ",
        "btn_home": "🏠 मुख्य मेनू",
    },
    "ur": {
        "title": "رابطوں کی جانچ مکمل!",
        "checked": "چیک شدہ",
        "healthy": "صحت مند اکاؤنٹ",
        "restricted": "محدود اکاؤنٹ",
        "invalid": "ناقص اکاؤنٹ",
        "error": "خراب اکاؤنٹ",
        "retry_note": "دوبارہ کوشش: ٹیلیگرام سرور سے کنیکٹ نہیں ہو سکا، فائل دوبارہ چیک کرنے کی سفارش کی جاتی ہے",
        "btn_checked": "چیک شدہ",
        "btn_healthy": "صحت مند",
        "btn_restricted": "محدود",
        "btn_invalid": "ناقص",
        "btn_error": "خراب",
        "btn_retry": "🔄 دوبارہ چلائیں",
        "btn_home": "🏠 مرکزی مینو",
    },
    "ar": {
        "title": "فحص جهات الاتصال",
        "checked": "مفحوص",
        "healthy": "حساب سليم",
        "restricted": "حساب مقيد",
        "invalid": "حساب غير صالح",
        "error": "حساب به خطأ",
        "retry_note": "إعادة المحاولة: تعذر الاتصال بخادم تيليجرام، يُنصح بالتحقق من الملف مرة أخرى",
        "btn_checked": "مفحوص",
        "btn_healthy": "سليم",
        "btn_restricted": "مقيد",
        "btn_invalid": "غير صالح",
        "btn_error": "خطأ",
        "btn_retry": "🔄 إعادة التشغيل",
        "btn_home": "🏠 القائمة الرئيسية",
    },
    "zh": {
        "title": "联系人检查完成！",
        "checked": "已检查",
        "healthy": "健康账号",
        "restricted": "受限账号",
        "invalid": "无效账号",
        "error": "异常账号",
        "retry_note": "重试：无法连接到 Telegram 服务器，建议重新检查文件",
        "btn_checked": "已检查",
        "btn_healthy": "健康",
        "btn_restricted": "受限",
        "btn_invalid": "无效",
        "btn_error": "异常",
        "btn_retry": "🔄 重新运行",
        "btn_home": "🏠 主菜单",
    },
}

# Caption labels for the per-bucket ZIP archives.
CONTACTS_ZIP_CAPTIONS = {
    "en": {
        "accounts": "accounts",
        "healthy": "Healthy",
        "restricted": "Restricted",
        "invalid": "Invalid",
        "error": "Error",
        "report": "Contacts Report",
    },
    "bn": {
        "accounts": "অ্যাকাউন্ট",
        "healthy": "সুস্থ",
        "restricted": "সীমাবদ্ধ",
        "invalid": "অকার্যকর",
        "error": "ত্রুটি",
        "report": "কন্টাক্ট রিপোর্ট",
    },
    "hi": {
        "accounts": "खाते",
        "healthy": "स्वस्थ",
        "restricted": "सीमित",
        "invalid": "अमान्य",
        "error": "त्रुटि",
        "report": "कॉन्ट्रैक्ट रिपोर्ट",
    },
    "ur": {
        "accounts": "اکاؤنٹس",
        "healthy": "صحت مند",
        "restricted": "محدود",
        "invalid": "ناقص",
        "error": "خراب",
        "report": "رابطوں کی رپورٹ",
    },
    "ar": {
        "accounts": "حسابات",
        "healthy": "سليم",
        "restricted": "مقيد",
        "invalid": "غير صالح",
        "error": "خطأ",
        "report": "تقرير جهات الاتصال",
    },
    "zh": {
        "accounts": "个账号",
        "healthy": "健康",
        "restricted": "受限",
        "invalid": "无效",
        "error": "异常",
        "report": "联系人报告",
    },
}

_STATUS_TO_CAPTION_KEY = {
    "ok": "healthy",
    "limited": "restricted",
    "2fa": "invalid",
    "banned": "invalid",
    "invalid": "invalid",
    "inconclusive": "error",
}

_EMOJI_BY_BUCKET = {
    "healthy": "🟢",
    "restricted": "🟡",
    "invalid": "❌",
    "error": "☑️",
}

_RESULT_ROW_EMOJIS = ("🔨 ", "🟢 ", "🟡 ", "❌ ", "☑️ ")


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


def _bucket_counts(result: ContactsCheckResult) -> dict[str, int]:
    """Collapse the 6 internal statuses into the 4 user-facing buckets."""
    return {
        "healthy": result.ok,
        "restricted": result.limited,
        "invalid": result.two_fa + result.banned + result.invalid,
        "error": result.inconclusive,
    }


def render_contacts_result(result: ContactsCheckResult, language: str = "en") -> str:
    labels = CONTACTS_RESULT_LABELS.get(language, CONTACTS_RESULT_LABELS["en"])
    counts = _bucket_counts(result)
    lines = [
        f"🎛 <b>{labels['title']}</b>",
        EmojiRegistry.divider_line(),
        f"🔨 {labels['checked']}: <b>{result.checked}</b>",
    ]
    for bucket, emoji in _EMOJI_BY_BUCKET.items():
        lines.append(f"{emoji} {labels[bucket]}: <b>{counts[bucket]}</b>")
    if counts["error"] > 0:
        lines.append(EmojiRegistry.divider_line())
        lines.append(f"♻️ {labels['retry_note']}")
    return "\n".join(lines)


def contacts_result_menu(
    result: ContactsCheckResult, language: str = "en"
) -> InlineKeyboardMarkup:
    labels = CONTACTS_RESULT_LABELS.get(language, CONTACTS_RESULT_LABELS["en"])
    counts = _bucket_counts(result)
    rows = (
        (f"🔨 {labels['checked']}", result.checked, "CONTACT_CHECKED"),
        (f"🟢 {labels['btn_healthy']}", counts["healthy"], "CONTACT_OK"),
        (f"🟡 {labels['btn_restricted']}", counts["restricted"], "INVALID"),
        (f"❌ {labels['btn_invalid']}", counts["invalid"], "CANCEL"),
        (f"☑️ {labels['btn_error']}", counts["error"], "CHECKBOX"),
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
    """Build the document caption for a bucket ZIP, e.g. ``📦 Restricted - 2 accounts``."""
    labels = CONTACTS_ZIP_CAPTIONS.get(language, CONTACTS_ZIP_CAPTIONS["en"])
    key = _STATUS_TO_CAPTION_KEY.get(status, "error")
    emoji = _EMOJI_BY_BUCKET.get(key, "📦")
    return f"{emoji} {labels[key]} - {count} {labels['accounts']}"


def contacts_report_caption(language: str = "en") -> str:
    """Caption for the CSV report document."""
    labels = CONTACTS_ZIP_CAPTIONS.get(language, CONTACTS_ZIP_CAPTIONS["en"])
    return f"📄 {labels['report']} (.csv)"