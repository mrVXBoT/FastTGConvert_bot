from dataclasses import dataclass

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


@dataclass(frozen=True)
class SessionCheckResult:
    checked: int
    active: int
    frozen: int  # spam-limited (temporary, appealable)
    invalid: int  # session expired / auth_key revoked
    banned: int = 0  # account permanently banned or deactivated
    inconclusive: int = 0  # could not determine (network error, 2FA, FloodWait)

    def __post_init__(self) -> None:
        total = (
            self.active + self.frozen + self.invalid + self.banned + self.inconclusive
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
        "invalid": "无效会话",
        "banned": "封禁 / 停用",
        "unknown": "未知",
        "btn_checked": "🔨 已检查",
        "btn_clean": "🟢 正常",
        "btn_spam": "🚫 垃圾",
        "btn_invalid": "❌ 无效/错误",
    },
}


def render_session_result(result: SessionCheckResult, language: str = "en") -> str:
    labels = SESSION_RESULT_LABELS.get(language, SESSION_RESULT_LABELS["en"])
    return (
        f"✅ <b>{labels['session_title']}</b>\n\n"
        f"📊 {labels['checked']}: <b>{result.checked}</b>\n"
        f"🟢 {labels['active']}: <b>{result.active}</b>\n"
        f"🟡 {labels['frozen_spam']}: <b>{result.frozen}</b>\n"
        f"❌ {labels['invalid']}: <b>{result.invalid}</b>"
    )


def render_spam_result(result: SessionCheckResult, language: str = "en") -> str:
    labels = SESSION_RESULT_LABELS.get(language, SESSION_RESULT_LABELS["en"])
    spam_count = result.frozen + result.banned
    return (
        f"🛡️ <b>{labels['spam_title']}</b> — {result.checked} {labels['checked']} |\n"
        f"🟢 {result.active} {labels['active']} |\n"
        f"🚫 {spam_count} {labels['frozen_spam']} |\n"
        f"❓ {result.inconclusive} {labels['unknown']} |\n"
        f"❌ {result.invalid} {labels['invalid']}"
    )


def session_result_menu(
    result: SessionCheckResult, language: str = "en", *, spam_mode: bool = False
) -> InlineKeyboardMarkup:
    labels = SESSION_RESULT_LABELS.get(language, SESSION_RESULT_LABELS["en"])
    if spam_mode:
        rows = (
            (labels["btn_checked"], result.checked),
            (labels["btn_clean"], result.active),
            (labels["btn_spam"], result.frozen + result.banned),
            (labels["btn_invalid"], result.invalid + result.inconclusive),
        )
    else:
        rows = (
            (f"🔨 {labels['checked']}", result.checked),
            (f"🟢 {labels['active']}", result.active),
            (f"🟡 {labels['frozen_spam']}", result.frozen),
            (f"❌ {labels['invalid']}", result.invalid),
        )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=label, callback_data="session:result:noop"),
                InlineKeyboardButton(
                    text=str(value), callback_data="session:result:noop"
                ),
            ]
            for label, value in rows
        ]
    )
