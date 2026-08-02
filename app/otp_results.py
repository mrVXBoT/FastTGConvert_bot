from dataclasses import dataclass

from aiogram import html


@dataclass(frozen=True)
class OTPCode:
    code: str
    age: str
    source: str = "Telegram"


@dataclass(frozen=True)
class OTPAccountResult:
    current: int
    total: int
    user: str
    phone: str
    username: str
    codes: tuple[OTPCode, ...]
    since_last_check: bool = False


_OTP_LABELS = {
    "en": {
        "account": "Account",
        "user": "User",
        "number": "Number",
        "username": "Username",
        "header_2h": "🧩 <b>OTP Codes (Last 2 Hours):</b>",
        "header_since": "🔄 <b>New OTP Codes (since last check):</b>",
        "no_codes_2h": "<i>No OTP codes found in the last 2 hours.</i>",
        "no_codes_since": "<i>No new OTP codes found since last check.</i>",
    },
    "bn": {
        "account": "অ্যাকাউন্ট",
        "user": "ব্যবহারকারী",
        "number": "নম্বর",
        "username": "ইউজারনেম",
        "header_2h": "🧩 <b>OTP কোড (গত ২ ঘন্টা):</b>",
        "header_since": "🔄 <b>নতুন OTP কোড (সর্বশেষ পরীক্ষার পর থেকে):</b>",
        "no_codes_2h": "<i>গত ২ ঘণ্টায় কোনো OTP কোড পাওয়া যায়নি।</i>",
        "no_codes_since": "<i>সর্বশেষ পরীক্ষার পর থেকে কোনো جدید OTP কোড পাওয়া যায়নি।</i>",
    },
    "hi": {
        "account": "अकाउंट",
        "user": "उपयोगकर्ता",
        "number": "नंबर",
        "username": "यूज़रनेम",
        "header_2h": "🧩 <b>OTP कोड (पिछले 2 घंटे):</b>",
        "header_since": "🔄 <b>नए OTP कोड (पिछली जाँच के बाद से):</b>",
        "no_codes_2h": "<i>पिछले 2 घंटों में कोई OTP कोड नहीं मिला।</i>",
        "no_codes_since": "<i>पिछली जाँच के बाद से कोई नया OTP कोड नहीं मिला।</i>",
    },
    "ur": {
        "account": "اکاؤنٹ",
        "user": "صارف",
        "number": "نمبر",
        "username": "یوزر نیم",
        "header_2h": "🧩 <b>OTP کوڈز (گزشتہ 2 گھنٹے):</b>",
        "header_since": "🔄 <b>نئے OTP کوڈز (آخری چیک کے بعد سے):</b>",
        "no_codes_2h": "<i>گزشتہ 2 گھنٹوں میں کوئی OTP کوڈ نہیں ملا۔</i>",
        "no_codes_since": "<i>آخری چیک کے بعد سے کوئی نیا OTP کوڈ نہیں ملا۔</i>",
    },
    "ar": {
        "account": "الحساب",
        "user": "المستخدم",
        "number": "الرقم",
        "username": "اسم المستخدم",
        "header_2h": "🧩 <b>رموز OTP (خلال الساعتين الماضيتين):</b>",
        "header_since": "🔄 <b>رموز OTP الجديدة (منذ آخر فحص):</b>",
        "no_codes_2h": "<i>لم يتم العثور على رموز OTP في الساعتين الماضيتين.</i>",
        "no_codes_since": "<i>لم يتم العثور على رموز OTP جديدة منذ آخر فحص.</i>",
    },
    "zh": {
        "account": "账户",
        "user": "用户",
        "number": "手机号",
        "username": "用户名",
        "header_2h": "🧩 <b>OTP 验证码 (最近 2 小时):</b>",
        "header_since": "🔄 <b>新 OTP 验证码 (自上次检查以来):</b>",
        "no_codes_2h": "<i>过去 2 小时内未找到 OTP 验证码。</i>",
        "no_codes_since": "<i>自上次检查以来未找到新的 OTP 验证码。</i>",
    },
}


def render_otp_account(result: OTPAccountResult, language: str = "en") -> str:
    labels = _OTP_LABELS.get(language, _OTP_LABELS["en"])
    heading = labels["header_since"] if result.since_last_check else labels["header_2h"]

    if result.codes:
        code_lines = "\n".join(
            f"{index}. 🔑 <code>{html.quote(item.code)}</code>  "
            f"⏱ {html.quote(item.age)}  📨 {html.quote(item.source)}"
            for index, item in enumerate(result.codes, start=1)
        )
    else:
        code_lines = (
            labels["no_codes_since"]
            if result.since_last_check
            else labels["no_codes_2h"]
        )

    return (
        f"👤 <b>{labels['account']} {result.current}/{result.total}</b>\n\n"
        f"👤 {labels['user']}: <b>{html.quote(result.user)}</b>\n"
        f"📱 {labels['number']}: <code>{html.quote(result.phone)}</code>\n"
        f"🔖 {labels['username']}: <b>{html.quote(result.username)}</b>\n\n"
        f"{heading}\n{code_lines}"
    )
