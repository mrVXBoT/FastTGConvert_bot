from dataclasses import dataclass

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.ui import EmojiRegistry


@dataclass(frozen=True)
class SessionCheckResult:
    checked: int
    active: int
    frozen: int  # genuinely frozen / limited (ToS appeal, 2025+ freeze)
    invalid: int  # session expired / auth_key revoked
    banned: int = 0  # account permanently banned or deactivated
    inconclusive: int = 0  # could not determine (network error, 2FA, FloodWait)
    spam: int = 0  # spam-flagged (limited by mistake / reported as spam)

    def __post_init__(self) -> None:
        total = (
            self.active
            + self.spam
            + self.frozen
            + self.invalid
            + self.banned
            + self.inconclusive
        )
        if total != self.checked:
            raise ValueError(f"checked ({self.checked}) != sum of buckets ({total})")


SESSION_RESULT_LABELS = {
    "en": {
        "session_title": "Session Check Done!",
        "spam_title": "Spam Check Done!",
        "checked": "Checked",
        "active": "Active Account",
        "frozen_spam": "Freeze Account",
        "spam": "Spam Account",
        "invalid": "Invalid Account",
        "banned": "Banned / Deactivated",
        "unknown": "Inconclusive",
        "btn_checked": "🔨 Checked",
        "btn_clean": "🟢 Clean",
        "btn_spam": "🚫 Spam",
        "btn_invalid": "❌ Invalid/Error",
    },
    "bn": {
        "session_title": "সেশন পরীক্ষা সম্পন্ন!",
        "spam_title": "স্প্যাম পরীক্ষা সম্পন্ন!",
        "checked": "পরীক্ষিত",
        "active": "সক্রিয় / মুক্ত",
        "frozen_spam": "স্প্যাম সীমাবদ্ধ",
        "spam": "স্প্যাম অ্যাকাউন্ট",
        "invalid": "অকার্যকর সেশন",
        "banned": "নিষিদ্ধ / নিষ্ক্রিয়",
        "unknown": "অজানা",
        "btn_checked": "🔨 পরীক্ষিত",
        "btn_clean": "🟢 মুক্ত",
        "btn_spam": "🚫 স্প্যাম",
        "btn_invalid": "❌ অকার্যকর/ত্রুটি",
    },
    "hi": {
        "session_title": "सेशन जाँच संपन्न!",
        "spam_title": "स्पैम जाँच संपन्न!",
        "checked": "जांचा गया",
        "active": "सक्रिय / सुरक्षित",
        "frozen_spam": "स्पैम सीमित",
        "spam": "स्पैम खाता",
        "invalid": "अमान्य सेशन",
        "banned": "प्रतिबंधित / निष्क्रिय",
        "unknown": "अज्ञात",
        "btn_checked": "🔨 जांचा गया",
        "btn_clean": "🟢 सुरक्षित",
        "btn_spam": "🚫 स्पैम",
        "btn_invalid": "❌ अमान्य/त्रुटि",
    },
    "ur": {
        "session_title": "سیشن چیک مکمل!",
        "spam_title": "اسپام چیک مکمل!",
        "checked": "چیک شدہ",
        "active": "فعال / صاف",
        "frozen_spam": "اسپام محدود",
        "spam": "اسپیم اکاؤنٹ",
        "invalid": "ناقص سیشن",
        "banned": "ممنوع / غیر فعال",
        "unknown": "غیر معلوم",
        "btn_checked": "🔨 چیک شدہ",
        "btn_clean": "🟢 صاف",
        "btn_spam": "🚫 اسپام",
        "btn_invalid": "❌ ناقص/خرابی",
    },
    "ar": {
        "session_title": "اكتمل فحص الجلسة!",
        "spam_title": "اكتمل فحص السبام!",
        "checked": "مفحوص",
        "active": "نشط / سليم",
        "frozen_spam": "مقيد بالسبام",
        "spam": "حساب السبام",
        "invalid": "جلسة غير صالحة",
        "banned": "محظور / معطل",
        "unknown": "مجهول",
        "btn_checked": "🔨 مفحوص",
        "btn_clean": "🟢 سليم",
        "btn_spam": "🚫 سبام",
        "btn_invalid": "❌ غير صالح/خطأ",
    },
    "zh": {
        "session_title": "会话检查完成！",
        "spam_title": "垃圾邮件检查完成！",
        "checked": "已检查",
        "active": "活跃 / 正常",
        "frozen_spam": "垃圾邮件限制",
        "spam": "垃圾邮件账号",
        "invalid": "无效会话",
        "banned": "封禁 / 停用",
        "unknown": "未知",
        "btn_checked": "🔨 已检查",
        "btn_clean": "🟢 正常",
        "btn_spam": "🚫 垃圾",
        "btn_invalid": "❌ 无效/错误",
    },
}


# Caption labels for the per-status ZIP archives sent after a check – format
# matches the reference bot:  "📦 No Restriction - 9 accounts".
STATUS_ZIP_CAPTIONS = {
    "en": {
        "accounts": "accounts",
        "no_restriction": "No Restriction",
        "spam": "Spam",
        "frozen": "Frozen",
        "banned": "Banned",
        "invalid": "Invalid",
        "error": "Error",
    },
    "bn": {
        "accounts": "অ্যাকাউন্ট",
        "no_restriction": "কোনো সীমাবদ্ধতা নেই",
        "spam": "স্প্যাম",
        "frozen": "ফ্রোজেন",
        "banned": "নিষিদ্ধ",
        "invalid": "অকার্যকর",
        "error": "ত্রুটি",
    },
    "hi": {
        "accounts": "खाते",
        "no_restriction": "कोई प्रतिबंध नहीं",
        "spam": "स्पैम",
        "frozen": "फ्रोज़न",
        "banned": "प्रतिबंधित",
        "invalid": "अमान्य",
        "error": "त्रुटि",
    },
    "ur": {
        "accounts": "اکاؤنٹس",
        "no_restriction": "کوئی پابندی نہیں",
        "spam": "اسپام",
        "frozen": "فروزن",
        "banned": "ممنوع",
        "invalid": "ناقص",
        "error": "خرابی",
    },
    "ar": {
        "accounts": "حسابات",
        "no_restriction": "لا توجد قيود",
        "spam": "سبام",
        "frozen": "مجمدة",
        "banned": "محظور",
        "invalid": "غير صالح",
        "error": "خطأ",
    },
    "zh": {
        "accounts": "个账号",
        "no_restriction": "无限制",
        "spam": "垃圾邮件",
        "frozen": "冻结",
        "banned": "已封禁",
        "invalid": "无效",
        "error": "错误",
    },
}

_STATUS_TO_CAPTION_KEY = {
    "active": "no_restriction",
    "spam": "spam",
    "frozen": "frozen",
    "banned": "banned",
    "invalid": "invalid",
    "inconclusive": "error",
}


def status_zip_caption(status: str, count: int, language: str = "en") -> str:
    """
    Build the document caption for a status ZIP, e.g. ``📦 Spam - 1 accounts``.
    """
    labels = STATUS_ZIP_CAPTIONS.get(language, STATUS_ZIP_CAPTIONS["en"])
    key = _STATUS_TO_CAPTION_KEY.get(status, "error")
    return f"📦 {labels[key]} - {count} {labels['accounts']}"


def render_session_result(result: SessionCheckResult, language: str = "en") -> str:
    labels = SESSION_RESULT_LABELS.get(language, SESSION_RESULT_LABELS["en"])
    return (
        f"✅ <b>{labels['session_title']}</b>\n"
        f"{EmojiRegistry.divider_line()}\n"
        f"📊 {labels['checked']}: <b>{result.checked}</b>\n"
        f"🟢 {labels['active']}: <b>{result.active}</b>\n"
        f"🛡️ {labels['spam']}: <b>{result.spam}</b>\n"
        f"🟡 {labels['frozen_spam']}: <b>{result.frozen}</b>\n"
        f"❌ {labels['invalid']}: <b>{result.invalid}</b>\n"
        f"🚫 {labels['banned']}: <b>{result.banned}</b>\n"
        f"❓ {labels['unknown']}: <b>{result.inconclusive}</b>"
    )


def render_spam_result(result: SessionCheckResult, language: str = "en") -> str:
    # Spam mode mirrors the inline buttons exactly so the message text and the
    # button labels always agree (spam = frozen + banned, error = invalid +
    # inconclusive).
    labels = SESSION_RESULT_LABELS.get(language, SESSION_RESULT_LABELS["en"])
    return (
        f"🛡️ <b>{labels['spam_title']}</b>\n"
        f"{EmojiRegistry.divider_line()}\n"
        f"{labels['btn_checked']}: <b>{result.checked}</b>\n"
        f"{labels['btn_clean']}: <b>{result.active}</b>\n"
        f"{labels['btn_spam']}: <b>{result.spam + result.frozen + result.banned}</b>\n"
        f"{labels['btn_invalid']}: <b>{result.invalid + result.inconclusive}</b>"
    )


def _result_button(label: str, emoji_key: str | None) -> InlineKeyboardButton:
    """Inline result button with a premium custom-emoji icon when configured.

    When the registry has a custom_emoji_id for emoji_key, the leading unicode
    emoji is stripped from the label and the premium icon is attached instead;
    otherwise the label (with its unicode emoji) is kept unchanged.
    """
    custom_id = EmojiRegistry.get_custom_emoji_id(emoji_key) if emoji_key else None
    if custom_id and label.startswith(_RESULT_ROW_EMOJIS):
        label = label.split(" ", 1)[1]
        return InlineKeyboardButton(
            text=label,
            callback_data="session:result:noop",
            icon_custom_emoji_id=custom_id,
        )
    return InlineKeyboardButton(text=label, callback_data="session:result:noop")


_RESULT_ROW_EMOJIS = ("🔨 ", "🟢 ", "🟡 ", "🚫 ", "❌ ", "❓ ", "🛡️ ")


def session_result_menu(
    result: SessionCheckResult, language: str = "en", *, spam_mode: bool = False
) -> InlineKeyboardMarkup:
    labels = SESSION_RESULT_LABELS.get(language, SESSION_RESULT_LABELS["en"])
    rows: tuple[tuple[str, int, str | None], ...]
    if spam_mode:
        rows = (
            (labels["btn_checked"], result.checked, "CHECKED"),
            (labels["btn_clean"], result.active, "ACTIVE"),
            (labels["btn_spam"], result.spam + result.frozen + result.banned, "BANNED"),
            (labels["btn_invalid"], result.invalid + result.inconclusive, "INVALID"),
        )
    else:
        rows = (
            (f"🔨 {labels['checked']}", result.checked, "CHECKED"),
            (f"🟢 {labels['active']}", result.active, "ACTIVE"),
            (f"🛡️ {labels['spam']}", result.spam, "SPAM"),
            (f"🟡 {labels['frozen_spam']}", result.frozen, "FROZEN"),
            (f"❌ {labels['invalid']}", result.invalid, "INVALID"),
            (f"🚫 {labels['banned']}", result.banned, "BANNED"),
            (f"❓ {labels['unknown']}", result.inconclusive, "INCONCLUSIVE"),
        )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _result_button(label, emoji_key),
                InlineKeyboardButton(
                    text=str(value), callback_data="session:result:noop"
                ),
            ]
            for label, value, emoji_key in rows
        ]
    )
