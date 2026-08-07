from dataclasses import dataclass
from typing import Any


@dataclass
class Locale:
    language_name: str = ""
    join_required: str = ""
    join_channel: str = ""
    i_joined: str = ""
    welcome: str = ""
    choose_option: str = ""
    joined: str = ""
    membership_incomplete: str = ""
    membership_verified: str = ""


LANGUAGES = {
    "bn": Locale(
        language_name="🇧🇩 বাংলা",
        join_required="🔒 এই বট ব্যবহার করতে প্রথমে আমাদের চ্যানেলে যোগ দিন:",
        join_channel="চ্যানেলে যোগ দিন",
        joined="আমি যোগ দিয়েছি",
        membership_incomplete="সদস্যতা এখনো সম্পূর্ণ হয়নি।",
        membership_verified="সদস্যতা নিশ্চিত হয়েছে।",
        welcome="👋 <b>Telegram Account Checker Bot</b>",
        choose_option="একটি অপশন বেছে নিন:",
    ),
    "en": Locale(
        language_name="🇬🇧 English",
        join_required="🔒 To use this bot, you must join our channel first:",
        join_channel="Join Channel",
        joined="I Joined",
        membership_incomplete="Your membership is not complete yet.",
        membership_verified="Membership verified.",
        welcome="👋 <b>Telegram Account Checker Bot</b>",
        choose_option="Choose an option:",
    ),
    "hi": Locale(
        language_name="🇮🇳 हिन्दी",
        join_required="🔒 इस बॉट का उपयोग करने के लिए पहले हमारे चैनल से जुड़ें:",
        join_channel="चैनल से जुड़ें",
        joined="मैं जुड़ गया",
        membership_incomplete="सदस्यता अभी पूरी नहीं हुई है।",
        membership_verified="सदस्यता सत्यापित हो गई।",
        welcome="👋 <b>Telegram Account Checker Bot</b>",
        choose_option="कोई विकल्प चुनें:",
    ),
    "ur": Locale(
        language_name="🇵🇰 اردو",
        join_required="🔒 اس بوٹ کو استعمال کرنے کے لیے پہلے ہمارے چینل میں شامل ہوں:",
        join_channel="چینل جوائن کریں",
        joined="میں شامل ہو گیا",
        membership_incomplete="رکنیت ابھی مکمل نہیں ہوئی۔",
        membership_verified="رکنیت کی تصدیق ہو گئی۔",
        welcome="👋 <b>Telegram Account Checker Bot</b>",
        choose_option="ایک آپشن منتخب کریں:",
    ),
    "ar": Locale(
        language_name="🇸🇦 العربية",
        join_required="🔒 لاستخدام هذا البوت، انضم إلى قناتنا أولاً:",
        join_channel="انضم إلى القناة",
        joined="لقد انضممت",
        membership_incomplete="لم يكتمل الاشتراك بعد.",
        membership_verified="تم التحقق من الاشتراك.",
        welcome="👋 <b>Telegram Account Checker Bot</b>",
        choose_option="اختر أحد الخيارات:",
    ),
    "zh": Locale(
        language_name="🇨🇳 中文",
        join_required="🔒 要使用此机器人，请先加入我们的频道：",
        join_channel="加入频道",
        joined="我已加入",
        membership_incomplete="您尚未完成频道订阅。",
        membership_verified="频道订阅已验证。",
        welcome="👋 <b>Telegram Account Checker Bot</b>",
        choose_option="请选择一个选项：",
    ),
}

ADMIN_LOCALES: dict[str, dict[str, str]] = {
    "en": {
        "title": "👑 <b>Admin Control Panel</b>",
        "btn_stats": "Statistics",
        "btn_users": "Users",
        "btn_broadcast": "Broadcast",
        "btn_admins": "Admins",
        "btn_force_join": "Force Join",
        "btn_support": "Support",
        "btn_vip": "VIP Management",
        "btn_referral": "Referral System",
        "btn_language": "Language",
        "btn_close": "Close Panel",
        "btn_back": "Back",
        "access_denied": "Access Denied: Admin privileges required.",
    },
    "bn": {
        "title": "👑 <b>এডমিন কন্ট্রোল প্যানেল</b>",
        "btn_stats": "পরিসংখ্যান",
        "btn_users": "ইউজার পরিচালনা",
        "btn_broadcast": "সার্বজনীন বার্তা",
        "btn_admins": "এডমিন তালিকা",
        "btn_force_join": "বাধ্যতামূলক জয়েন",
        "btn_support": "সাপোর্ট সেটিংস",
        "btn_vip": "VIP ব্যবস্থাপনা",
        "btn_referral": "রেফারেল সিস্টেম",
        "btn_language": "ভাষা",
        "btn_close": "প্যানেল বন্ধ",
        "btn_back": "ফিরে যান",
        "access_denied": "প্রবেশাধিকার অস্বীকৃত: এডমিন ক্ষমতা আবশ্যক।",
    },
    "hi": {
        "title": "👑 <b>एडमिन कंट्रोल पैनल</b>",
        "btn_stats": "आंकड़े",
        "btn_users": "उपयोगकर्ता",
        "btn_broadcast": "ब्रॉडकास्ट",
        "btn_admins": "एडमिन",
        "btn_force_join": "अनिवार्य जॉइन",
        "btn_support": "सपोर्ट",
        "btn_vip": "VIP प्रबंधन",
        "btn_referral": "रेफ़रल सिस्टम",
        "btn_language": "भाषा",
        "btn_close": "पैनल बंद करें",
        "btn_back": "वापस",
        "access_denied": "पहुंच अस्वीकृत: एडमिन अनुमतियां आवश्यक।",
    },
    "ur": {
        "title": "👑 <b>ایڈمن کنٹرول پینل</b>",
        "btn_stats": "اعداد و شمار",
        "btn_users": "صارفین",
        "btn_broadcast": "نشریات",
        "btn_admins": "ایڈمنز",
        "btn_force_join": "لازمی شمولیت",
        "btn_support": "سپورٹ",
        "btn_vip": "VIP مینجمنٹ",
        "btn_referral": "ریفرل سسٹم",
        "btn_language": "زبان",
        "btn_close": "پینل بند کریں",
        "btn_back": "واپس",
        "access_denied": "رسائی مسترد: ایڈمن کے اختیارات درکار ہیں۔",
    },
    "ar": {
        "title": "👑 <b>لوحة تحكم المشرف</b>",
        "btn_stats": "الإحصائيات",
        "btn_users": "إدارة المستخدمين",
        "btn_broadcast": "الإذاعة الجماعية",
        "btn_admins": "المشرفين",
        "btn_force_join": "الاشتراك الإجباري",
        "btn_support": "إعدادات الدعم",
        "btn_vip": "إدارة VIP والخطط",
        "btn_referral": "نظام الإحالة",
        "btn_language": "اللغة",
        "btn_close": "إغلاق اللوحة",
        "btn_back": "عودة",
        "access_denied": "تم رفض الوصول: يتطلب صلاحيات المشرف.",
    },
    "zh": {
        "title": "👑 <b>管理员控制面板</b>",
        "btn_stats": "数据统计",
        "btn_users": "用户管理",
        "btn_broadcast": "广播群发",
        "btn_admins": "管理员列表",
        "btn_force_join": "强制关注频道",
        "btn_support": "客服支持设置",
        "btn_vip": "VIP 与方案管理",
        "btn_referral": "推荐系统",
        "btn_language": "语言",
        "btn_close": "关闭面板",
        "btn_back": "返回",
        "access_denied": "拒绝访问：需要管理员权限。",
    },
}


def get_admin_locale(lang: str = "en") -> dict[str, str]:
    return ADMIN_LOCALES.get(lang, ADMIN_LOCALES["en"])

LANGUAGE_PROMPT = "🌐 <b>Choose Language</b>\n\nPick your preferred language below:"

LANGUAGE_PROMPTS = {
    "bn": "🌐 <b>ভাষা নির্বাচন করুন</b>\n\nনিচে আপনার পছন্দের ভাষা বেছে নিন:",
    "en": "🌐 <b>Choose Language</b>\n\nPick your preferred language below:",
    "hi": "🌐 <b>भाषा चुनें</b>\n\nनीचे अपनी पसंदीदा भाषा चुनें:",
    "ur": "🌐 <b>زبان منتخب کریں</b>\n\nنیچے اپنی پسندیدہ زبان منتخب کریں:",
    "ar": "🌐 <b>اختر اللغة</b>\n\nاختر لغتك المفضلة أدناه:",
    "zh": "🌐 <b>选择语言</b>\n\n请在下方选择您的首选语言：",
}

REFERRAL_MESSAGES: dict[str, str] = {
    "en": (
        "🔗 <b>Your Referral Link</b>\n\n"
        "<code>{ref_link}</code>\n\n"
        "📊 <b>Your Stats</b>\n"
        "  👥 Referred: <b>{referred}</b> users\n"
        "  🎁 VIP days earned: <b>{earned_days}</b>\n"
        "{next_tier}"
        "🥇 <b>Reward Tiers</b>\n"
        "{tiers}"
        "Share your link! Every new user who joins via your link counts. 🔗"
    ),
    "bn": (
        "🔗 <b>আপনার রেফারেল লিংক</b>\n\n"
        "<code>{ref_link}</code>\n\n"
        "📊 <b>আপনার পরিসংখ্যান</b>\n"
        "  👥 রেফারেল: <b>{referred}</b> জন\n"
        "  🎁 অর্জিত VIP দিন: <b>{earned_days}</b>\n"
        "{next_tier}"
        "🥇 <b>পুরস্কার স্তর</b>\n"
        "{tiers}"
        "আপনার লিংক শেয়ার করুন! আপনার লিংকের মাধ্যমে আসা প্রতিটি নতুন ইউজার যুক্ত হবে। 🔗"
    ),
    "hi": (
        "🔗 <b>आपका रेफ़रल लिंक</b>\n\n"
        "<code>{ref_link}</code>\n\n"
        "📊 <b>आपके आंकड़े</b>\n"
        "  👥 आमंत्रित: <b>{referred}</b> उपयोगकर्ता\n"
        "  🎁 अर्जित VIP दिन: <b>{earned_days}</b>\n"
        "{next_tier}"
        "🥇 <b>पुरस्कार स्तर</b>\n"
        "{tiers}"
        "अपना लिंक साझा करें! आपके लिंक के माध्यम से जुड़ने वाला प्रत्येक नया उपयोगकर्ता गिना जाता है। 🔗"
    ),
    "ur": (
        "🔗 <b>آپ کا ریفرل لنک</b>\n\n"
        "<code>{ref_link}</code>\n\n"
        "📊 <b>آپ کے اعداد و شمار</b>\n"
        "  👥 شامل کیے گئے: <b>{referred}</b> صارفین\n"
        "  🎁 حاصل شدہ VIP ایام: <b>{earned_days}</b>\n"
        "{next_tier}"
        "🥇 <b>انعامی درجات</b>\n"
        "{tiers}"
        "اپنا لنک شیئر کریں! آپ کے لنک سے شامل ہونے والا ہر نیا صارف شمار ہوگا۔ 🔗"
    ),
    "ar": (
        "🔗 <b>رابط الإحالة الخاص بك</b>\n\n"
        "<code>{ref_link}</code>\n\n"
        "📊 <b>إحصائياتك</b>\n"
        "  👥 تمت إحالتهم: <b>{referred}</b> مستخدمين\n"
        "  🎁 أيام VIP المكتسبة: <b>{earned_days}</b>\n"
        "{next_tier}"
        "🥇 <b>مستويات المكافآت</b>\n"
        "{tiers}"
        "شارك رابطك! كل مستخدم جديد ينضم عبر رابطك يمنحك نقاطاً. 🔗"
    ),
    "zh": (
        "🔗 <b>您的推荐链接</b>\n\n"
        "<code>{ref_link}</code>\n\n"
        "📊 <b>您的统计数据</b>\n"
        "  👥 已推荐: <b>{referred}</b> 用户\n"
        "  🎁 已获得 VIP 天数: <b>{earned_days}</b>\n"
        "{next_tier}"
        "🥇 <b>奖励阶梯</b>\n"
        "{tiers}"
        "分享您的链接！通过您的链接加入的每一位新用户都算数。 🔗"
    ),
}

REFERRAL_TIER_LABELS: dict[str, str] = {
    "en": "  🏆 <b>{refs} refs</b> → <b>{days} days</b> FREE VIP",
    "bn": "  🏆 <b>{refs} রেফার</b> → <b>{days} দিন</b> ফ্রি VIP",
    "hi": "  🏆 <b>{refs} रेफ़रल</b> → <b>{days} दिन</b> मुफ़्त VIP",
    "ur": "  🏆 <b>{refs} ریفرل</b> → <b>{days} دن</b> مفت VIP",
    "ar": "  🏆 <b>{refs} إحالة</b> → <b>{days} يوم</b> VIP مجاناً",
    "zh": "  🏆 <b>{refs} 人推荐</b> → <b>{days} 天</b>免费 VIP",
}

REFERRAL_NEXT_TIER_LABELS: dict[str, str] = {
    "en": "  🎯 Next reward: <b>{refs} refs</b> → <b>{days} days</b> VIP (<code>{remaining} left</code>)",
    "bn": "  🎯 পরবর্তী পুরস্কার: <b>{refs} রেফার</b> → <b>{days} দিন</b> VIP (<code>{remaining} বাকি</code>)",
    "hi": "  🎯 अगला पुरस्कार: <b>{refs} रेफ़रल</b> → <b>{days} दिन</b> VIP (<code>{remaining} बाकी</code>)",
    "ur": "  🎯 اگلا انعام: <b>{refs} ریفرل</b> → <b>{days} دن</b> VIP (<code>{remaining} باقی</code>)",
    "ar": "  🎯 المكافأة التالية: <b>{refs} إحالة</b> → <b>{days} يوم</b> VIP (<code>متبقي {remaining}</code>)",
    "zh": "  🎯 下一个奖励: <b>{refs} 人推荐</b> → <b>{days} 天</b> VIP（还差 <code>{remaining}</code>）",
}

REFERRAL_NOTIFY_MESSAGES: dict[str, str] = {
    "en": "🎁 <b>New Referral!</b>\n\n👤 A new user joined via your referral link.\n📊 Total referrals: <b>{count}</b>\n{reward}",
    "bn": "🎁 <b>নতুন রেফারেল!</b>\n\n👤 আপনার রেফারেল লিংকের মাধ্যমে একজন নতুন ইউজার যোগ দিয়েছে।\n📊 মোট রেফারেল: <b>{count}</b>\n{reward}",
    "hi": "🎁 <b>नया रेफ़रल!</b>\n\n👤 आपके रेफ़रल लिंक के माध्यम से एक नया उपयोगकर्ता जुड़ा।\n📊 कुल रेफ़रल: <b>{count}</b>\n{reward}",
    "ur": "🎁 <b>نیا ریفرل!</b>\n\n👤 آپ کے ریفرل لنک کے ذریعے ایک نیا صارف شامل ہوا۔\n📊 کل ریفرلز: <b>{count}</b>\n{reward}",
    "ar": "🎁 <b>إحالة جديدة!</b>\n\n👤 انضم مستخدم جديد عبر رابط الإحالة الخاص بك.\n📊 إجمالي الإحالات: <b>{count}</b>\n{reward}",
    "zh": "🎁 <b>新推荐!</b>\n\n👤 一名新用户通过您的推荐链接加入。\n📊 总推荐人数: <b>{count}</b>\n{reward}",
}

REFERRAL_REWARD_LABELS: dict[str, str] = {
    "en": "🎉 +{days} VIP days granted to your account!",
    "bn": "🎉 আপনার অ্যাকাউন্টে +{days} VIP দিন যুক্ত হয়েছে!",
    "hi": "🎉 आपके खाते में +{days} VIP दिन जुड़ गए!",
    "ur": "🎉 آپ کے اکاؤنٹ میں +{days} VIP دن شامل ہو گئے!",
    "ar": "🎉 تمت إضافة +{days} يوم VIP إلى حسابك!",
    "zh": "🎉 您的账户已获得 +{days} 天 VIP!",
}

PROXY_MESSAGES: dict[str, str] = {
    "en": (
        "🌐 <b>Your Proxy Setup</b>\n\n"
        "Send your proxy in one of these formats:\n\n"
        "<code>socks5://host:port</code>\n"
        "<code>socks5://user:pass@host:port</code>\n"
        "<code>http://host:port</code>\n\n"
        "Examples:\n"
        "<code>socks5://103.1.2.3:1080</code>\n"
        "<code>socks5://myuser:mypass@45.6.7.8:1080</code>"
    ),
    "bn": (
        "🌐 <b>আপনার প্রক্সি সেটআপ</b>\n\n"
        "নিচের যেকোনো একটি ফরম্যাটে প্রক্সি পাঠান:\n\n"
        "<code>socks5://host:port</code>\n"
        "<code>socks5://user:pass@host:port</code>\n"
        "<code>http://host:port</code>\n\n"
        "উদাহরণ:\n"
        "<code>socks5://103.1.2.3:1080</code>\n"
        "<code>socks5://myuser:mypass@45.6.7.8:1080</code>"
    ),
    "hi": (
        "🌐 <b>आपका प्रॉक्सी सेटअप</b>\n\n"
        "इनमें से किसी एक प्रारूप में अपना प्रॉक्सी भेजें:\n\n"
        "<code>socks5://host:port</code>\n"
        "<code>socks5://user:pass@host:port</code>\n"
        "<code>http://host:port</code>\n\n"
        "उदाहरण:\n"
        "<code>socks5://103.1.2.3:1080</code>\n"
        "<code>socks5://myuser:mypass@45.6.7.8:1080</code>"
    ),
    "ur": (
        "🌐 <b>آپ کا پروکسی سیٹ اپ</b>\n\n"
        "درج ذیل میں سے کسی ایک فارمیٹ میں اپنا پروکسی بھیجیں:\n\n"
        "<code>socks5://host:port</code>\n"
        "<code>socks5://user:pass@host:port</code>\n"
        "<code>http://host:port</code>\n\n"
        "مثالیں:\n"
        "<code>socks5://103.1.2.3:1080</code>\n"
        "<code>socks5://myuser:mypass@45.6.7.8:1080</code>"
    ),
    "ar": (
        "🌐 <b>إعداد البروكسي الخاص بك</b>\n\n"
        "أرسل البروكسي بأحد التنسيقات التالية:\n\n"
        "<code>socks5://host:port</code>\n"
        "<code>socks5://user:pass@host:port</code>\n"
        "<code>http://host:port</code>\n\n"
        "أمثلة:\n"
        "<code>socks5://103.1.2.3:1080</code>\n"
        "<code>socks5://myuser:mypass@45.6.7.8:1080</code>"
    ),
    "zh": (
        "🌐 <b>您的代理设置</b>\n\n"
        "请以以下格式之一发送您的代理：\n\n"
        "<code>socks5://host:port</code>\n"
        "<code>socks5://user:pass@host:port</code>\n"
        "<code>http://host:port</code>\n\n"
        "示例：\n"
        "<code>socks5://103.1.2.3:1080</code>\n"
        "<code>socks5://myuser:mypass@45.6.7.8:1080</code>"
    ),
}


def proxy_status_text(proxy: str | None, language: str = "en") -> str:
    texts = {
        "en": {
            "title": "🌐 <b>Your Proxy Setup</b>",
            "none": "❌ <b>No Proxy set.</b>\n\nYour files use the default proxy.",
            "set": "✅ <b>Current Proxy:</b> <code>{proxy}</code>\n\nYour files will use your custom proxy.",
        },
        "bn": {
            "title": "🌐 <b>আপনার প্রক্সি সেটআপ</b>",
            "none": "❌ <b>কোন প্রক্সি সেট করা নেই।</b>\n\nআপনার ফাইল ডিফোল্ট প্রক্সি ব্যবহার করছে।",
            "set": "✅ <b>বর্তমান প্রক্সি:</b> <code>{proxy}</code>\n\nআপনার ফাইল কাস্টম প্রক্সি ব্যবহার করবে।",
        },
        "hi": {
            "title": "🌐 <b>आपका प्रॉक्सी सेटअप</b>",
            "none": "❌ <b>कोई प्रॉक्सी सेट नहीं है।</b>\n\nआपकी फ़ाइलें डिफ़ॉल्ट प्रॉक्सी का उपयोग करती हैं।",
            "set": "✅ <b>वर्तमान प्रॉक्सी:</b> <code>{proxy}</code>\n\nआपकी फ़ाइलें आपके कस्टम प्रॉक्सी का उपयोग करेंगी।",
        },
        "ur": {
            "title": "🌐 <b>آپ کا پروکسی سیٹ اپ</b>",
            "none": "❌ <b>کوئی پروکسی سیٹ نہیں ہے۔</b>\n\nآپ کی فائلیں ڈیفالٹ پروکسی استعمال کرتی ہیں۔",
            "set": "✅ <b>موجودہ پروکسی:</b> <code>{proxy}</code>\n\nآپ کی فائلیں آپ کا کسٹم پروکسی استعمال کریں گی۔",
        },
        "ar": {
            "title": "🌐 <b>إعداد البروكسي الخاص بك</b>",
            "none": "❌ <b>لم يتم ضبط أي بروكسي.</b>\n\nملفاتك تستخدم البروكسي الافتراضي.",
            "set": "✅ <b>البروكسي الحالي:</b> <code>{proxy}</code>\n\nملفاتك ستستخدم البروكسي المخصص.",
        },
        "zh": {
            "title": "🌐 <b>您的代理设置</b>",
            "none": "❌ <b>未设置代理。</b>\n\n您的文件将使用默认代理。",
            "set": "✅ <b>当前代理:</b> <code>{proxy}</code>\n\n您的文件将使用您的自定义代理。",
        },
    }
    t = texts.get(language, texts["en"])
    status = t["set"].format(proxy=proxy) if proxy else t["none"]
    return f"{t['title']}\n\n{status}"


PROXY_SUCCESS_MESSAGES: dict[str, str] = {
    "en": "✅ <b>Proxy set successfully!</b>\nYour proxy: <code>{proxy}</code>",
    "bn": "✅ <b>প্রক্সি সফলভাবে সেট করা হয়েছে!</b>\nআপনার প্রক্সি: <code>{proxy}</code>",
    "hi": "✅ <b>प्रॉक्सी सफलतापूर्वक सेट हो गया!</b>\nआपका प्रॉक्सी: <code>{proxy}</code>",
    "ur": "✅ <b>پروکسی کامیابی کے ساتھ سیٹ ہو گیا!</b>\nآپ کا پروکسی: <code>{proxy}</code>",
    "ar": "✅ <b>تم ضبط البروكسي بنجاح!</b>\nالبروكسي الخاص بك: <code>{proxy}</code>",
    "zh": "✅ <b>代理设置成功！</b>\n您的代理: <code>{proxy}</code>",
}

PROXY_REMOVED_MESSAGES: dict[str, str] = {
    "en": "🗑️ Proxy removed. Default system proxy restored.",
    "bn": "🗑️ প্রক্সি রিমুভ করা হয়েছে। ডিফোল্ট সিস্টেম প্রক্সি রিসেট হয়েছে।",
    "hi": "🗑️ प्रॉक्सी हटा दिया गया। डिफ़ॉल्ट सिस्टम प्रॉक्सी रीस्टोर किया गया।",
    "ur": "🗑️ پروکسی ختم کر دیا گیا۔ ڈیفالٹ سسٹم پروکسی بحال کر دیا گیا۔",
    "ar": "🗑️ تم إزالة البروكسي. تم استعادة البروكسي الافتراضي.",
    "zh": "🗑️ 代理已删除。已恢复默认系统代理。",
}

PROXY_INVALID_MESSAGES: dict[str, str] = {
    "en": "❌ Invalid proxy format. Please use format like <code>socks5://host:port</code> or <code>socks5://user:pass@host:port</code>",
    "bn": "❌ প্রক্সি ফরম্যাট সঠিক নয়। অনুগ্রহ করে <code>socks5://host:port</code> ফরম্যাট ব্যবহার করুন",
    "hi": "❌ अमान्य प्रॉक्सी प्रारूप। कृपया <code>socks5://host:port</code> प्रारूप का उपयोग करें",
    "ur": "❌ غیر درست پروکسی فارمیٹ۔ براہ کرم <code>socks5://host:port</code> فارمیٹ استعمال کریں",
    "ar": "❌ تنسيق البروكسي غير صالح. يرجى استخدام التنسيق <code>socks5://host:port</code>",
    "zh": "❌ 代理格式无效。请使用如 <code>socks5://host:port</code> 的格式",
}

PROXY_TESTING_MESSAGES: dict[str, str] = {
    "en": "🔄 Testing proxy connection to Telegram servers...",
    "bn": "🔄 টেলিগ্রাম সার্ভারে প্রক্সি সংযোগ পরীক্ষা করা হচ্ছে...",
    "hi": "🔄 टेलीग्राम सर्वर से प्रॉक्सी कनेक्शन का परीक्षण किया जा रहा है...",
    "ur": "🔄 ٹیلی گرام سرورز پر پروکسی کنکشن کا ٹیسٹ جاری ہے...",
    "ar": "🔄 جاري اختبار اتصال البروكسي بخوادم تليجرام...",
    "zh": "🔄 正在测试到 Telegram 服务器的代理连接...",
}

PROXY_FAIL_MESSAGES: dict[str, str] = {
    "en": "❌ Proxy connection failed ({detail}). Please enter a working proxy.",
    "bn": "❌ প্রক্সি সংযোগ ব্যর্থ হয়েছে ({detail})। অনুগ্রহ করে একটি সচল প্রক্সি দিন।",
    "hi": "❌ प्रॉक्सी कनेक्शन विफल ({detail})। कृपया एक कार्यशील प्रॉक्सी दर्ज करें।",
    "ur": "❌ پروکسی کنکشن ناکام ہوگیا ({detail})۔ براہ کرم کام کرنے والا پروکسی درج کریں۔",
    "ar": "❌ فشل اتصال البروكسي ({detail}). يرجى إدخال بروكسي يعمل.",
    "zh": "❌ 代理连接失败（{detail}）。请输入有效的代理。",
}

MENU_LABELS = {
    "en": (
        "CHECK",
        "Session Check",
        "Spam Check",
        "Read OTP",
        "Check Contacts",
        "CONVERT",
        "Session → Tdata",
        "Tdata → Session",
        "Session → Json",
        "Account → Txt",
        "FILE TOOLS",
        "File Split",
        "File Merge",
        "2FA",
        "2FA Change",
        "2FA Disable",
        "Reset 2FA",
        "CHANNEL",
        "Channel Join",
        "Leave Channel",
        "ACCOUNT",
        "Clean Chat",
        "Clear Contact",
        "Delete Contact",
        "Profile Setup",
        "Account Age",
        "ADVANCED",
        "Mass Message",
        "Kill Session",
        "Fresh Session",
        "List Checker",
        "PRIVACY",
        "Privacy Settings",
        "VIP",
        "Buy VIP",
        "SETTINGS",
        "Help & Support",
    ),
    "bn": (
        "পরীক্ষা",
        "সেশন পরীক্ষা",
        "স্প্যাম পরীক্ষা",
        "OTP পড়ুন",
        "কনট্যাক্ট পরীক্ষা",
        "রূপান্তর",
        "সেশন → Tdata",
        "Tdata → সেশন",
        "সেশন → Json",
        "অ্যাকাউন্ট → Txt",
        "ফাইল টুলস",
        "ফাইল ভাগ",
        "ফাইল একত্র",
        "2FA",
        "2FA পরিবর্তন",
        "2FA বন্ধ",
        "2FA রিসেট",
        "চ্যানেল",
        "চ্যানেলে যোগ",
        "চ্যানেল ছাড়ুন",
        "অ্যাকাউন্ট",
        "চ্যাট পরিষ্কার",
        "কনট্যাক্ট পরিষ্কার",
        "কনট্যাক্ট মুছুন",
        "প্রোফাইল সেটআপ",
        "অ্যাকাউন্টের বয়স",
        "উন্নত",
        "গণ বার্তা",
        "সেশন বন্ধ",
        "নতুন সেশন",
        "লিস্ট চেকার",
        "গোপনীয়তা",
        "গোপনীয়তা সেটিংস",
        "VIP",
        "VIP কিনুন",
        "সেটিংস",
        "সহায়তা ও সাপোর্ট",
    ),
    "hi": (
        "जाँच",
        "सेशन जाँच",
        "स्पैम जाँच",
        "OTP पढ़ें",
        "संपर्क जाँचें",
        "कन्वर्ट",
        "सेशन → Tdata",
        "Tdata → सेशन",
        "सेशन → Json",
        "अकाउंट → Txt",
        "फ़ाइल टूल्स",
        "फ़ाइल बाँटें",
        "फ़ाइल जोड़ें",
        "2FA",
        "2FA बदलें",
        "2FA बंद करें",
        "2FA रीसेट",
        "चैनल",
        "चैनल जुड़ें",
        "चैनल छोड़ें",
        "अकाउंट",
        "चैट साफ़ करें",
        "संपर्क साफ़ करें",
        "संपर्क हटाएँ",
        "प्रोफ़ाइल सेटअप",
        "अकाउंट आयु",
        "उन्नत",
        "सामूहिक संदेश",
        "सेशन बंद करें",
        "नया सेशन",
        "लिस्ट चेकर",
        "गोपनीयता",
        "गोपनीयता सेटिंग्स",
        "VIP",
        "VIP खरीदें",
        "सेटिंग्स",
        "सहायता",
    ),
    "ur": (
        "چیک",
        "سیشن چیک",
        "اسپیم چیک",
        "OTP پڑھیں",
        "رابطے چیک کریں",
        "تبدیل",
        "سیشن → Tdata",
        "Tdata → سیشن",
        "سیشن → Json",
        "اکاؤنٹ → Txt",
        "فائل ٹولز",
        "فائل تقسیم",
        "فائل ضم",
        "2FA",
        "2FA تبدیل",
        "2FA بند",
        "2FA ری سیٹ",
        "چینل",
        "چینل جوائن",
        "چینل چھوڑیں",
        "اکاؤنٹ",
        "چیٹ صاف",
        "رابطے صاف",
        "رابطہ حذف",
        "پروفائل سیٹ اپ",
        "اکاؤنٹ عمر",
        "ایڈوانسڈ",
        "اجتماعی پیغام",
        "سیشن ختم",
        "نیا سیشن",
        "لسٹ چیکر",
        "رازداری",
        "رازداری ترتیبات",
        "VIP",
        "VIP خریدیں",
        "ترتیبات",
        "مدد و معاونت",
    ),
    "ar": (
        "فحص",
        "فحص الجلسة",
        "فحص السبام",
        "قراءة OTP",
        "فحص جهات الاتصال",
        "تحويل",
        "الجلسة → Tdata",
        "Tdata → الجلسة",
        "الجلسة → Json",
        "الحساب → Txt",
        "أدوات الملفات",
        "تقسيم ملف",
        "دمج ملف",
        "2FA",
        "تغيير 2FA",
        "تعطيل 2FA",
        "إعادة 2FA",
        "القناة",
        "انضمام للقناة",
        "مغادرة القناة",
        "الحساب",
        "تنظيف المحادثة",
        "مسح جهات الاتصال",
        "حذف جهة اتصال",
        "إعداد الملف",
        "عمر الحساب",
        "متقدم",
        "رسالة جماعية",
        "إنهاء الجلسة",
        "جلسة جديدة",
        "فاحص القائمة",
        "الخصوصية",
        "إعدادات الخصوصية",
        "VIP",
        "شراء VIP",
        "الإعدادات",
        "المساعدة والدعم",
    ),
    "zh": (
        "检查",
        "会话检查",
        "垃圾信息检查",
        "读取 OTP",
        "检查联系人",
        "转换",
        "会话 → Tdata",
        "Tdata → 会话",
        "会话 → Json",
        "账户 → Txt",
        "文件工具",
        "拆分文件",
        "合并文件",
        "2FA",
        "更改 2FA",
        "关闭 2FA",
        "重置 2FA",
        "频道",
        "加入频道",
        "离开频道",
        "账户",
        "清理聊天",
        "清除联系人",
        "删除联系人",
        "设置资料",
        "账户年龄",
        "高级",
        "群发消息",
        "终止会话",
        "新会话",
        "列表检查器",
        "隐私",
        "隐私设置",
        "VIP",
        "购买 VIP",
        "设置",
        "帮助与支持",
    ),
}

CANCEL_LABELS = {
    "bn": "বাতিল",
    "en": "Cancel",
    "hi": "रद्द करें",
    "ur": "منسوخ",
    "ar": "إلغاء",
    "zh": "取消",
}

ACTION_MESSAGES = {
    "en": (
        "Choose one of the tools in this section.",
        "This feature will be added in a future version.",
        "This option requires sensitive account access and is unavailable in the safe version.",
        "Operation cancelled.",
    ),
    "bn": (
        "এই বিভাগের একটি টুল নির্বাচন করুন।",
        "এই সুবিধাটি ভবিষ্যৎ সংস্করণে যোগ করা হবে।",
        "এই অপশনে সংবেদনশীল অ্যাকাউন্ট অ্যাক্সেস প্রয়োজন এবং নিরাপদ সংস্করণে এটি নেই।",
        "অপারেশন বাতিল হয়েছে।",
    ),
    "hi": (
        "इस अनुभाग का कोई टूल चुनें।",
        "यह सुविधा भविष्य के संस्करण में जोड़ी जाएगी।",
        "इस विकल्प को संवेदनशील अकाउंट एक्सेस चाहिए और यह सुरक्षित संस्करण में उपलब्ध नहीं है।",
        "कार्य रद्द कर दिया गया।",
    ),
    "ur": (
        "اس حصے میں سے کوئی ٹول منتخب کریں۔",
        "یہ فیچر آئندہ ورژن میں شامل کیا جائے گا۔",
        "اس آپشن کو حساس اکاؤنٹ رسائی درکار ہے اور یہ محفوظ ورژن میں دستیاب نہیں۔",
        "آپریشن منسوخ کر دیا گیا۔",
    ),
    "ar": (
        "اختر إحدى أدوات هذا القسم.",
        "ستُضاف هذه الميزة في إصدار قادم.",
        "يتطلب هذا الخيار وصولاً حساساً إلى الحساب، لذلك لا يتوفر في الإصدار الآمن.",
        "تم إلغاء العملية.",
    ),
    "zh": (
        "请选择本区中的一个工具。",
        "此功能将在后续版本中添加。",
        "此选项需要敏感的账户访问权限，因此安全版本不提供该功能。",
        "操作已取消。",
    ),
}

ANALYZE_PROMPTS = {
    "en": "📊 <b>File Analysis</b>\n\nSend any file as a document to analyze.",
    "bn": "📊 <b>ফাইল বিশ্লেষণ</b>\n\nবিশ্লেষণ করতে যেকোনো ফাইল ডকুমেন্ট হিসেবে পাঠান।",
    "hi": "📊 <b>फ़ाइल विश्लेषण</b>\n\nविश्लेषण के लिए कोई भी फ़ाइल दस्तावेज़ के रूप में भेजें।",
    "ur": "📊 <b>فائل کا تجزیہ</b>\n\nتجزیہ کے لیے کوئی بھی فائل ڈاکیومنٹ کے طور پر بھیجیں۔",
    "ar": "📊 <b>تحليل الملفات</b>\n\nأرسل أي ملف كمستند لتحليله।",
    "zh": "📊 <b>文件分析</b>\n\n请发送要分析的文件。",
}

SESSION_CHECK_PROMPTS = {
    "en": "🔍 <b>Session Check</b>\n\nSend a <code>.session</code> file or <code>.zip</code>.",
    "bn": "🔍 <b>সেশন পরীক্ষা</b>\n\nএকটি <code>.session</code> ফাইল অথবা <code>.zip</code> পাঠান।",
    "hi": "🔍 <b>सेशन जाँच</b>\n\nएक <code>.session</code> फ़ाइल या <code>.zip</code> भेजें।",
    "ur": "🔍 <b>سیشن چیک</b>\n\nایک <code>.session</code> فائل یا <code>.zip</code> بھیجیں۔",
    "ar": "🔍 <b>فحص الجلسة</b>\n\nأرسل ملف <code>.session</code> أو <code>.zip</code>.",
    "zh": "🔍 <b>会话检查</b>\n\n请发送 <code>.session</code> 文件或 <code>.zip</code>。",
}

SPAM_CHECK_PROMPTS = {
    "en": "🛡️ <b>Spam Check</b>\n\nSend a <code>.session</code> file or <code>.zip</code>.",
    "bn": "🛡️ <b>স্প্যাম পরীক্ষা</b>\n\nএকটি <code>.session</code> ফাইল অথবা <code>.zip</code> পাঠান।",
    "hi": "🛡️ <b>स्पैम जाँच</b>\n\nएक <code>.session</code> फ़ाइल या <code>.zip</code> भेजें।",
    "ur": "🛡️ <b>اسپام چیک</b>\n\nایک <code>.session</code> فائل یا <code>.zip</code> بھیجیں۔",
    "ar": "🛡️ <b>فحص السبام</b>\n\nأرسل ملف <code>.session</code> أو <code>.zip</code>.",
    "zh": "🛡️ <b>垃圾邮件检查</b>\n\n请发送 <code>.session</code> 文件或 <code>.zip</code>。",
}

HELP_MESSAGES = {
    "en": "❓ <b>Help & Support</b>\n\nClick the button below to contact the admin/support:\n\n👤 <code>{support_id}</code>",
    "bn": "❓ <b>সাহায্য ও সহায়তা</b>\n\nঅ্যাডমিন/সাপোর্টের সাথে যোগাযোগ করতে নিচের বোতামটি চাপুন:\n\n👤 <code>{support_id}</code>",
    "hi": "❓ <b>सहायता और समर्थन</b>\n\nएडमिन/सपोर्ट से संपर्क करने के लिए नीचे दिए बटन को दबाएँ:\n\n👤 <code>{support_id}</code>",
    "ur": "❓ <b>مدد اور سپورٹ</b>\n\nایڈمن/سپورٹ سے رابطے کے لیے نیچے دیا گیا بٹن دبائیں:\n\n👤 <code>{support_id}</code>",
    "ar": "❓ <b>المساعدة والدعم</b>\n\nاضغط الزر أدناه للتواصل مع المسؤول/الدعم:\n\n👤 <code>{support_id}</code>",
    "zh": "❓ <b>帮助与支持</b>\n\n点击下方按钮联系管理员/客服：\n\n👤 <code>{support_id}</code>",
}

HELP_BUTTON_LABELS = {
    "en": "Contact Support",
    "bn": "সাপোর্টে যোগাযোগ করুন",
    "hi": "सपोर्ट से संपर्क करें",
    "ur": "سپورٹ سے رابطہ کریں",
    "ar": "تواصل مع الدعم",
    "zh": "联系支持",
}

BACK_LABELS = {
    "en": "Back",
    "bn": "ফিরে যান",
    "hi": "वापस",
    "ur": "واپس",
    "ar": "رجوع",
    "zh": "返回",
}

SUPPORT_UNAVAILABLE = {
    "en": "Support contact is not configured yet.",
    "bn": "সাপোর্ট যোগাযোগ এখনো কনফিগার করা হয়নি।",
    "hi": "सपोर्ट संपर्क अभी कॉन्फ़िगर नहीं किया गया है।",
    "ur": "سپورٹ رابطہ ابھی ترتیب نہیں دیا گیا۔",
    "ar": "لم يتم إعداد جهة اتصال الدعم بعد.",
    "zh": "尚未配置支持联系方式。",
}

PRIVACY_MESSAGES = {
    "en": "🔐 <b>Privacy</b>\n\nUploaded files are stored temporarily during processing and immediately removed. Passwords, OTPs, and login credentials are never stored.",
    "bn": "🔐 <b>গোপনীয়তা</b>\n\nআপলোড করা ফাইল প্রসেসিংয়ের জন্য সাময়িকভাবে সংরক্ষিত হয় এবং পরে মুছে ফেলা হয়। পাসওয়ার্ড বা ওটিপি সংরক্ষণ করা হয় না।",
    "hi": "🔐 <b>गोपनीयता</b>\n\nअपलोड की गई फाइलें केवल प्रोसेसिंग के दौरान अस्थायी रूप से रखी जाती हैं। पासवर्ड और ओटीपी कभी संग्रहीत नहीं होते।",
    "ur": "🔐 <b>راز داری</b>\n\nاپ لوڈ کردہ فائلیں صرف پروسیسنگ کے لیے عارضی طور پر رکھی جاتی ہیں۔ پاس ورڈ اور او ٹی پی محفوظ نہیں کیے جاتے۔",
    "ar": "🔐 <b>الخصوصية</b>\n\nتُحفظ الملفات المرفوعة مؤقتاً أثناء المعالجة وتُحذف فوراً. لا يتم تخزين كلمات السر أو OTP.",
    "zh": "🔐 <b>隐私</b>\n\n上传的文件仅在处理期间临时存储并立即删除。密码、OTP 和登录凭据绝不存储。",
}

ENTER_ACCOUNT_AGE_PROMPT = {
    "en": "📅 <b>Account Age Check</b>\n\n📂 Send your Telegram session file (.session) or ZIP archive to check account creation dates and estimated age:",
    "bn": "📅 <b>অ্যাকাউন্ট বয়স চেক</b>\n\n📂 আপনার টেলিগ্রাম সেশন ফাইল (.session) বা ZIP আর্কাইভ পাঠান:",
    "hi": "📅 <b>खाता आयु जाँच</b>\n\n📂 खाता निर्माण तिथि और अनुमानित आयु जाँचने के लिए अपनी फ़ाइल (.session या ZIP) भेजें:",
    "ur": "📅 <b>اکاؤنٹ کی عمر چیک کریں</b>\n\n📂 اکاؤنٹ بنانے کی تاریخ اور تخمینہ شدہ عمر چیک کرنے کے لیے سیشن یا ZIP فائل بھیجیں:",
    "ar": "📅 <b>فحص عمر الحساب</b>\n\n📂 أرسل ملف الجلسة (.session) أو أرشيف ZIP لفحص تاريخ إنشاء الحساب والعمر التقديري:",
    "zh": "📅 <b>账号注册年份查询</b>\n\n📂 请发送您的 Telegram 会话文件 (.session) 或 ZIP 压缩包以查询账号注册时间：",
}

ACCOUNT_AGE_MESSAGES = {
    "en": {
        "fetching": "⏳ Estimating account age & fetching account details...",
        "no_sessions": "❌ No valid sessions found.",
        "request_failed": "❌ An error occurred during request processing.",
        "report_title": "Account Information & Age Report",
        "btn_total": "Total",
        "btn_checked": "Checked",
        "btn_failed": "Failed",
        "btn_back": "⬅️ Back to Menu",
        "btn_next": "Next ▶️",
        "btn_prev": "◀️ Prev",
        "label_name": "Name",
        "label_user_id": "User ID",
        "label_username": "Username",
        "label_premium": "Premium",
        "label_dc": "Data Center",
        "label_est_creation": "Est. Creation",
        "label_earliest_activity": "Earliest Activity",
        "label_yes": "Yes",
        "label_no": "No",
    },
    "bn": {
        "fetching": "⏳ অ্যাকাউন্টের তথ্য এবং নিবন্ধনের তারিখ সংগ্রহ করা হচ্ছে...",
        "no_sessions": "❌ কোনো বৈধ সেশন পাওয়া যায়নি।",
        "request_failed": "❌ অনুরোধ প্রসেসিংকালে ত্রুটি ঘটেছে।",
        "report_title": "অ্যাকাউন্টের তথ্য এবং বয়সের রিপোর্ট",
        "btn_total": "মোট",
        "btn_checked": "পরীক্ষিত",
        "btn_failed": "ব্যর্থ",
        "btn_back": "⬅️ মেনুতে ফিরুন",
        "btn_next": "পরের ▶️",
        "btn_prev": "◀️ আগের",
        "label_name": "নাম",
        "label_user_id": "ইউজার আইডি",
        "label_username": "ইউজারনেম",
        "label_premium": "প্রিমিয়াম",
        "label_dc": "ডাটা সেন্টার",
        "label_est_creation": "আনুমানিক নিবন্ধন",
        "label_earliest_activity": "প্রথম কার্যক্রম",
        "label_yes": "হ্যাঁ",
        "label_no": "না",
    },
    "hi": {
        "fetching": "⏳ खाते की जानकारी और पंजीकरण तिथि प्राप्त की जा रही है...",
        "no_sessions": "❌ कोई वैध सेशन नहीं मिला।",
        "request_failed": "❌ अनुरोध प्रक्रिया के दौरान त्रुटि हुई।",
        "report_title": "खाता जानकारी और आयु रिपोर्ट",
        "btn_total": "कुल",
        "btn_checked": "जांचा गया",
        "btn_failed": "विफल",
        "btn_back": "⬅️ मेनू पर वापस",
        "btn_next": "अगला ▶️",
        "btn_prev": "◀️ पिछला",
        "label_name": "नाम",
        "label_user_id": "यूजर आईडी",
        "label_username": "यूजरनेम",
        "label_premium": "प्रीमियम",
        "label_dc": "डेटा सेंटर",
        "label_est_creation": "अनुमानित निर्माण",
        "label_earliest_activity": "प्रथम गतिविधि",
        "label_yes": "हाँ",
        "label_no": "नहीं",
    },
    "ur": {
        "fetching": "⏳ اکاؤنٹ کی تفصیلات اور رجسٹریشن کی تاریخ کا تخمینہ لگایا جا رہا ہے...",
        "no_sessions": "❌ کوئی بھی درست سیشن نہیں ملا۔",
        "request_failed": "❌ درخواست کے عمل کے دوران ایک خرابی پیش آئی۔",
        "report_title": "اکاؤنٹ کی معلومات اور عمر کی رپورٹ",
        "btn_total": "کل",
        "btn_checked": "چیک شدہ",
        "btn_failed": "ناکام",
        "btn_back": "⬅️ مینو پر واپس جائیں",
        "btn_next": "اگلا ▶️",
        "btn_prev": "◀️ پچھلا",
        "label_name": "نام",
        "label_user_id": "یوزر آئی ڈی",
        "label_username": "یوزر نیم",
        "label_premium": "پریمیم",
        "label_dc": "ڈیٹا سینٹر",
        "label_est_creation": "تخمینہ شدہ تاریخ",
        "label_earliest_activity": "پہلی سرگرمی",
        "label_yes": "ہاں",
        "label_no": "نہیں",
    },
    "ar": {
        "fetching": "⏳ جاري جلب تفاصيل الحساب وتقدير عمر الحساب...",
        "no_sessions": "❌ لم يتم العثور على جلسات صالحة.",
        "request_failed": "❌ حدث خطأ أثناء معالجة الطلب.",
        "report_title": "تقرير معلومات وعمر الحساب",
        "btn_total": "الإجمالي",
        "btn_checked": "تم الفحص",
        "btn_failed": "فشل",
        "btn_back": "⬅️ العودة إلى القائمة",
        "btn_next": "التالي ▶️",
        "btn_prev": "◀️ السابق",
        "label_name": "الاسم",
        "label_user_id": "معرف المستخدم",
        "label_username": "اسم المستخدم",
        "label_premium": "بريميوم",
        "label_dc": "مركز البيانات",
        "label_est_creation": "تاريخ الإنشاء التقديري",
        "label_earliest_activity": "أول نشاط",
        "label_yes": "نعم",
        "label_no": "لا",
    },
    "zh": {
        "fetching": "⏳ 正在获取账号详细信息和估算注册年份...",
        "no_sessions": "❌ 未找到有效会话。",
        "request_failed": "❌ 处理请求时出错。",
        "report_title": "账号详细信息与注册年份报告",
        "btn_total": "总计",
        "btn_checked": "已检测",
        "btn_failed": "失败",
        "btn_back": "⬅️ 返回菜单",
        "btn_next": "下一页 ▶️",
        "btn_prev": "◀️ 上一页",
        "label_name": "姓名",
        "label_user_id": "用户 ID",
        "label_username": "用户名",
        "label_premium": "Premium 会员",
        "label_dc": "数据中心 (DC)",
        "label_est_creation": "预估注册时间",
        "label_earliest_activity": "最早活动时间",
        "label_yes": "是",
        "label_no": "否",
    },
}

PLAN_MESSAGES = {
    "en": "Current plan: Free\nMax upload size: {max_mb} MB",
    "bn": "বর্তমান প্ল্যান: বিনামূল্যে\nসর্বোচ্চ ফাইল সাইজ: {max_mb} MB",
    "hi": "वर्तमान प्लान: नि:शुल्क\nअधिकतम फ़ाइल आकार: {max_mb} MB",
    "ur": "موجودہ پلان: مفت\nزیادہ سے زیادہ فائل سائز: {max_mb} MB",
    "ar": "الخطة الحالية: مجانية\nالحجم الأقصى للملف: {max_mb} ميجابايت",
    "zh": "当前方案：免费\n最大上传大小：{max_mb} MB",
}

INVALID_LANGUAGE_MESSAGES = {
    "en": "Invalid language selected.",
    "bn": "অবৈধ ভাষা নির্বাচিত হয়েছে।",
    "hi": "अमान्य भाषा चुनी गई।",
    "ur": "ناقابل قبول زبان کا انتخاب۔",
    "ar": "اللغة المحددة غير صالحة.",
    "zh": "所选语言无效。",
}

DOWNLOAD_ERRORS = {
    "en": {
        "document_required": "Please send the file as a Document.",
        "file_too_large": "Maximum allowed size is {max_mb} MB.",
    },
    "bn": {
        "document_required": "দয়া করে ফাইলটি একটি ডকুমেন্টস হিসেবে পাঠান।",
        "file_too_large": "সর্বোচ্চ অনুমতিপ্রাপ্ত সাইজ {max_mb} MB।",
    },
    "hi": {
        "document_required": "कृपया फ़ाइल दस्तावेज़ (Document) के रूप में भेजें।",
        "file_too_large": "अधिकतम अनुमति योग्य आकार {max_mb} MB है।",
    },
    "ur": {
        "document_required": "برائے مہربانی فائل کو ڈاکیومنٹ کے طور پر بھیجیں۔",
        "file_too_large": "زیادہ سے زیادہ اجازت شدہ سائز {max_mb} MB ہے۔",
    },
    "ar": {
        "document_required": "يرجى إرسال الملف كمستند (Document).",
        "file_too_large": "الحد الأقصى المسموح به هو {max_mb} ميجابايت.",
    },
    "zh": {
        "document_required": "请将文件作为文档发送。",
        "file_too_large": "最大允许大小为 {max_mb} MB。",
    },
}

ARCHIVE_ERRORS = {
    "en": {
        "zip_too_many_members": "ZIP contains too many files.",
        "zip_unsafe_path": "ZIP contains an unsafe file path.",
        "zip_uncompressed_limit": (
            "ZIP uncompressed size exceeds maximum allowed limit."
        ),
        "zip_suspicious_ratio": "ZIP compression ratio is suspicious.",
        "zip_bomb_detected": "ZIP appears to be a Zip Bomb.",
        "zip_no_sessions": "The ZIP contains no .session files.",
        "chunk_size_invalid": "Chunk size must be greater than zero.",
        "bad_zip_file": "The uploaded file is not a valid ZIP archive.",
        "storage_error": "Not enough free disk space to save the output.",
        "opentele_not_installed": (
            "The <code>opentele</code> dependency is not installed on the server. "
            "Please contact the administrator."
        ),
    },
    "bn": {
        "zip_too_many_members": ("ZIP এর ভেতর ফাইলের সংখ্যা অননুমোদিত মাত্রায় বেশি।"),
        "zip_unsafe_path": "ZIP এ একটি অনিরাপদ ফাইল পাথ রয়েছে।",
        "zip_uncompressed_limit": ("ZIP আনকম্প্রেসড সাইজ সর্বোচ্চ সীমা অতিক্রম করেছে।"),
        "zip_suspicious_ratio": "ZIP এর কম্প্রেশন রেশিও সন্দেহজনক।",
        "zip_bomb_detected": "ZIP টি Zip Bomb হতে পারে।",
        "zip_no_sessions": "ZIP এ কোনো .session ফাইল নেই।",
        "chunk_size_invalid": "টুকরোর সাইজ শুন্যের চেয়ে বেশি হতে হবে।",
        "bad_zip_file": "আপলোড করা ফাইলটি সঠিক ZIP আর্কাইভ নয়।",
        "storage_error": "আউটপুট সংরক্ষণ করতে পর্যাপ্ত ডিস্ক স্পেস নেই।",
        "opentele_not_installed": (
            "সার্ভারে <code>opentele</code> ডিপেন্ডেন্সি ইনস্টল নেই। অ্যাডমিনের সাথে যোগাযোগ করুন।"
        ),
    },
    "hi": {
        "zip_too_many_members": "ZIP में फाइलों की संख्या बहुत अधिक है।",
        "zip_unsafe_path": "ZIP में एक असुरक्षित फ़ाइल पथ है।",
        "zip_uncompressed_limit": ("ZIP अनकंप्रेस्ड आकार अधिकतम सीमा से अधिक है।"),
        "zip_suspicious_ratio": "ZIP संपीड़न अनुपात संदिग्ध है।",
        "zip_bomb_detected": "ZIP एक Zip Bomb प्रतीत होता है।",
        "zip_no_sessions": "ZIP में कोई .session फ़ाइल नहीं है।",
        "chunk_size_invalid": "भाग का आकार शून्य से अधिक होना चाहिए।",
        "bad_zip_file": "अपलोड की गई फ़ाइल एक मान्य ZIP आर्काइव नहीं है।",
        "storage_error": "आउटपुट सहेजने के लिए पर्याप्त डिस्क स्थान नहीं है।",
        "opentele_not_installed": (
            "सर्वर पर <code>opentele</code> निर्भरता स्थापित नहीं है। कृपया प्रशासक से संपर्क करें।"
        ),
    },
    "ur": {
        "zip_too_many_members": "ZIP میں فائلوں کی تعداد بہت زیادہ ہے۔",
        "zip_unsafe_path": "ZIP میں غیر محفوظ فائل پاتھ ہے۔",
        "zip_uncompressed_limit": "ZIP سائز حد سے زیادہ ہے۔",
        "zip_suspicious_ratio": "ZIP کمپریشن ریشو مشکوک ہے۔",
        "zip_bomb_detected": "ZIP بظاہر Zip Bomb معلوم ہوتا ہے۔",
        "zip_no_sessions": "ZIP میں کوئی .session فائل نہیں ہے۔",
        "chunk_size_invalid": "ٹکڑے کا سائز صفر سے بڑا ہونا چاہیے۔",
        "bad_zip_file": "اپ لوڈ کردہ فائل درست ZIP آرکائیو نہیں ہے۔",
        "storage_error": "آؤٹ پٹ محفوظ کرنے کے لیے کافی ڈسک جگہ نہیں ہے۔",
        "opentele_not_installed": (
            "سرور پر <code>opentele</code> ڈیپنڈنسی انسٹال نہیں ہے۔ براہ کرم ایڈمن سے رابطہ کریں۔"
        ),
    },
    "ar": {
        "zip_too_many_members": ("يحتوي ملف ZIP على عدد كبير جداً من الملفات."),
        "zip_unsafe_path": "يحتوي ZIP على مسار ملف غير آمن.",
        "zip_uncompressed_limit": (
            "يتجاوز حجم ZIP غير المضغوط الحد الأقصى المسموح به."
        ),
        "zip_suspicious_ratio": "نسبة ضغط ZIP مشبوهة.",
        "zip_bomb_detected": ("يبدو ملف ZIP كأنه قنبلة ضغط (Zip Bomb)."),
        "zip_no_sessions": "لا يحتوي ملف ZIP على أي ملفات .session.",
        "chunk_size_invalid": "يجب أن يكون حجم الجزء أكبر من الصفر.",
        "bad_zip_file": "الملف المرفوع ليس أرشيف ZIP صالحاً.",
        "storage_error": "لا توجد مساحة كافية على القرص لحفظ الناتج.",
        "opentele_not_installed": (
            "الاعتماد <code>opentele</code> غير مثبت على الخادم. يرجى التواصل مع المسؤول."
        ),
    },
    "zh": {
        "zip_too_many_members": "ZIP 包含的文件数量过多。",
        "zip_unsafe_path": "ZIP 包含不安全的文件路径。",
        "zip_uncompressed_limit": ("ZIP 解压后的大小超过允许的最大限制。"),
        "zip_suspicious_ratio": "ZIP 压缩率可疑。",
        "zip_bomb_detected": "ZIP 似乎是 Zip 炸弹。",
        "zip_no_sessions": "ZIP 中不包含 .session 文件。",
        "chunk_size_invalid": "分块大小必须大于零。",
        "bad_zip_file": "上传的文件不是有效的 ZIP 压缩包。",
        "storage_error": "磁盘空间不足，无法保存输出。",
        "opentele_not_installed": (
            "服务器上未安装 <code>opentele</code> 依赖。请联系管理员。"
        ),
    },
}

SPLIT_PROMPTS = {
    "en": (
        "✂️ <b>File Split</b>\n\nSend a <code>.session</code> file or <code>.zip</code>."
    ),
    "bn": (
        "✂️ <b>ফাইল বিভাজন</b>\n\nএকটি <code>.session</code> ফাইল বা <code>.zip</code> পাঠান।"
    ),
    "hi": (
        "✂️ <b>फ़ाइल विभाजन</b>\n\nएक <code>.session</code> फ़ाइल یا <code>.zip</code> भेजें।"
    ),
    "ur": (
        "✂️ <b>فائل کی تقسیم</b>\n\n"
        "ایک <code>.session</code> فائل یا <code>.zip</code> بھیجیں۔"
    ),
    "ar": (
        "✂️ <b>تقسيم الملف</b>\n\nأرسل ملف <code>.session</code> أو <code>.zip</code>."
    ),
    "zh": (
        "✂️ <b>文件分割</b>\n\n发送 <code>.session</code> 文件或 <code>.zip</code>。"
    ),
}

DIRECT_FILE_PROMPTS = {
    "en": (
        "📎 <b>File received:</b> <code>{filename}</code>\n\n"
        "⏰ Choose action within 15 seconds, or send the file again:"
    ),
    "bn": (
        "📎 <b>ফাইল পাওয়া গেছে:</b> <code>{filename}</code>\n\n"
        "⏰ ১৫ সেকেন্ডের মধ্যে কাজ বেছে নিন, অথবা ফাইলটি আবার পাঠান:"
    ),
    "hi": (
        "📎 <b>फ़ाइल प्राप्त हुई:</b> <code>{filename}</code>\n\n"
        "⏰ 15 सेकंड के भीतर कार्रवाई चुनें, या फ़ाइल फिर से भेजें:"
    ),
    "ur": (
        "📎 <b>فائل موصول ہوئی:</b> <code>{filename}</code>\n\n"
        "⏰ 15 سیکنڈ کے اندر کارروائی منتخب کریں، یا فائل دوبارہ بھیجیں:"
    ),
    "ar": (
        "📎 <b>تم استلام الملف:</b> <code>{filename}</code>\n\n"
        "⏰ اختر الإجراء خلال 15 ثانية، أو أرسل الملف مرة أخرى:"
    ),
    "zh": (
        "📎 <b>已收到文件：</b> <code>{filename}</code>\n\n"
        "⏰ 请在 15 秒内选择操作，或重新发送文件："
    ),
}

CHANGE_2FA_PROMPTS = {
    "en": (
        "🔐 <b>2FA Change</b>\n\n"
        "Send a <code>.session</code> file or <code>.zip</code>."
    ),
    "bn": (
        "🔐 <b>২FA পরিবর্তন</b>\n\n"
        "একটি <code>.session</code> ফাইল বা <code>.zip</code> পাঠান।"
    ),
    "hi": (
        "🔐 <b>2FA बदलाव</b>\n\nएक <code>.session</code> फ़ाइल या <code>.zip</code> भेजें।"
    ),
    "ur": (
        "🔐 <b>2FA تبدیلی</b>\n\n"
        "ایک <code>.session</code> فائل یا <code>.zip</code> بھیجیں۔"
    ),
    "ar": (
        "🔐 <b>تغيير 2FA</b>\n\nأرسل ملف <code>.session</code> أو <code>.zip</code>."
    ),
    "zh": (
        "🔐 <b>修改 2FA</b>\n\n发送 <code>.session</code> 文件或 <code>.zip</code>。"
    ),
}

DISABLE_2FA_PROMPTS = {
    "en": (
        "🔐 <b>2FA Disable</b>\n\n"
        "Send a <code>.session</code> file or <code>.zip</code>."
    ),
    "bn": (
        "🔐 <b>২FA বন্ধ</b>\n\nএকটি <code>.session</code> ফাইল বা <code>.zip</code> পাঠান।"
    ),
    "hi": (
        "🔐 <b>2FA बंद</b>\n\nएक <code>.session</code> फ़ाइल या <code>.zip</code> भेजें।"
    ),
    "ur": (
        "🔐 <b>2FA بند</b>\n\n"
        "ایک <code>.session</code> فائل یا <code>.zip</code> بھیجیں۔"
    ),
    "ar": (
        "🔐 <b>إلغاء 2FA</b>\n\nأرسل ملف <code>.session</code> أو <code>.zip</code>."
    ),
    "zh": (
        "🔐 <b>禁用 2FA</b>\n\n发送 <code>.session</code> 文件或 <code>.zip</code>。"
    ),
}

RESET_2FA_PROMPTS = {
    "en": (
        "🔄 <b>Reset 2FA</b>\n\nSend a <code>.session</code> file or <code>.zip</code>."
    ),
    "bn": (
        "🔄 <b>২FA রিসেট</b>\n\nএকটি <code>.session</code> ফাইল বা <code>.zip</code> পাঠান।"
    ),
    "hi": (
        "🔄 <b>2FA रीसेट</b>\n\nएक <code>.session</code> फ़ाइल या <code>.zip</code> भेजें।"
    ),
    "ur": (
        "🔄 <b>2FA ری سیٹ</b>\n\n"
        "ایک <code>.session</code> فائل یا <code>.zip</code> بھیجیں۔"
    ),
    "ar": (
        "🔄 <b>إعادة ضبط 2FA</b>\n\n"
        "أرسل ملف <code>.session</code> أو <code>.zip</code>."
    ),
    "zh": (
        "🔄 <b>重置 2FA</b>\n\n发送 <code>.session</code> 文件或 <code>.zip</code>。"
    ),
}

CHANNEL_JOIN_PROMPTS = {
    "en": (
        "📢 <b>Join Channel</b>\n\n"
        "Send a <code>.session</code> file or <code>.zip</code>."
    ),
    "bn": (
        "📢 <b>চ্যানেলে যোগ</b>\n\n"
        "একটি <code>.session</code> ফাইল বা <code>.zip</code> পাঠান।"
    ),
    "hi": (
        "📢 <b>चैनल में जुड़ें</b>\n\nएक <code>.session</code> फ़ाइल या <code>.zip</code> भेजें।"
    ),
    "ur": (
        "📢 <b>چینل میں شامل ہوں</b>\n\n"
        "ایک <code>.session</code> فائل یا <code>.zip</code> بھیجیں۔"
    ),
    "ar": (
        "📢 <b>الانضمام إلى القناة</b>\n\n"
        "أرسل ملف <code>.session</code> أو <code>.zip</code>."
    ),
    "zh": (
        "📢 <b>加入频道</b>\n\n发送 <code>.session</code> 文件或 <code>.zip</code>。"
    ),
}

CHANNEL_LEAVE_PROMPTS = {
    "en": (
        "🚪 <b>Leave Channel</b>\n\n"
        "Send a <code>.session</code> file or <code>.zip</code>."
    ),
    "bn": (
        "🚪 <b>চ্যানেল ছাড়ুন</b>\n\nএকটি <code>.session</code> ফাইল বা <code>.zip</code> পাঠান।"
    ),
    "hi": (
        "🚪 <b>चैनल छोड़ें</b>\n\nएक <code>.session</code> फ़ाइल या <code>.zip</code> भेजें।"
    ),
    "ur": (
        "🚪 <b>چینل چھوڑیں</b>\n\n"
        "ایک <code>.session</code> فائل یا <code>.zip</code> بھیجیں۔"
    ),
    "ar": (
        "🚪 <b>مغادرة القناة</b>\n\n"
        "أرسل ملف <code>.session</code> أو <code>.zip</code>."
    ),
    "zh": (
        "🚪 <b>离开频道</b>\n\n发送 <code>.session</code> 文件或 <code>.zip</code>。"
    ),
}

ENTER_CHANNEL_JOIN_TARGET_PROMPT = {
    "en": (
        "📢 <b>Channel Join</b>\n\n"
        "📦 Found <b>{count}</b> session(s)\n\n"
        "🔗 Send channel username or link (e.g. <code>@channel</code> or <code>https://t.me/+link</code>):"
    ),
    "bn": (
        "📢 <b>চ্যানেলে যোগ</b>\n\n"
        "📦 <b>{count}</b>টি সেশন পাওয়া গেছে\n\n"
        "🔗 চ্যানেলের ইউজারনেম বা লিংক পাঠান (যেমন <code>@channel</code> বা <code>https://t.me/+link</code>):"
    ),
    "hi": (
        "📢 <b>चैनल में जुड़ें</b>\n\n"
        "📦 <b>{count}</b> सेशन मिले\n\n"
        "🔗 चैनल यूज़रनेम या लिंक भेजें (जैसे <code>@channel</code> या <code>https://t.me/+link</code>):"
    ),
    "ur": (
        "📢 <b>چینل میں شامل ہوں</b>\n\n"
        "📦 <b>{count}</b> سیشنز ملے\n\n"
        "🔗 چینل صارف نام یا لنک بھیجیں (مثال: <code>@channel</code> یا <code>https://t.me/+link</code>):"
    ),
    "ar": (
        "📢 <b>الانضمام إلى القناة</b>\n\n"
        "📦 تم العثور على <b>{count}</b> جلسة\n\n"
        "🔗 أرسل اسم مستخدم القناة أو الرابط (مثال: <code>@channel</code> أو <code>https://t.me/+link</code>):"
    ),
    "zh": (
        "📢 <b>加入频道</b>\n\n"
        "📦 找到 <b>{count}</b> 个会话\n\n"
        "🔗 发送频道用户名或链接（例如 <code>@channel</code> 或 <code>https://t.me/+link</code>）："
    ),
}

ENTER_CHANNEL_LEAVE_TARGET_PROMPT = {
    "en": (
        "🚪 <b>Leave Channel</b>\n\n"
        "📦 Found <b>{count}</b> session(s)\n\n"
        "🔗 Send channel username/link OR type <code>all</code> to leave all channels:"
    ),
    "bn": (
        "🚪 <b>চ্যানেল ছাড়ুন</b>\n\n"
        "📦 <b>{count}</b>টি সেশন পাওয়া গেছে\n\n"
        "🔗 চ্যানেলের ইউজারনেম/লিংক পাঠান অথবা সব চ্যানেল ছাড়তে <code>all</code> লিখুন:"
    ),
    "hi": (
        "🚪 <b>चैनल छोड़ें</b>\n\n"
        "📦 <b>{count}</b> सेशन मिले\n\n"
        "🔗 चैनल यूज़रनेम/लिंक भेजें या सभी चैनल छोड़ने के लिए <code>all</code> लिखें:"
    ),
    "ur": (
        "🚪 <b>چینل چھوڑیں</b>\n\n"
        "📦 <b>{count}</b> سیشنز ملے\n\n"
        "🔗 چینل صارف نام/لنک بھیجیں یا تمام چینلز چھوڑنے کے لیے <code>all</code> لکھیں:"
    ),
    "ar": (
        "🚪 <b>مغادرة القناة</b>\n\n"
        "📦 تم العثور على <b>{count}</b> جلسة\n\n"
        "🔗 أرسل اسم مستخدم/رابط القناة أو اكتب <code>all</code> لمغادرة جميع القنوات:"
    ),
    "zh": (
        "🚪 <b>离开频道</b>\n\n"
        "📦 找到 <b>{count}</b> 个会话\n\n"
        "🔗 发送频道用户名/链接，或输入 <code>all</code> 退出所有频道："
    ),
}

CHANNEL_MESSAGES = {
    "en": {
        "processing": "⏳ Processing channel request...",
        "no_sessions": "❌ No valid sessions found.",
        "request_failed": "❌ An error occurred during request processing.",
        "done": "✅ Done — {success} success | ❌ {failed} failed",
        "failed_report": "❌ All attempts failed — {failed} failed",
        "invalid_target": "❌ Invalid target. Send a channel username or link (e.g. <code>@channel</code> or <code>https://t.me/+link</code>). Joining with <code>all</code> is not supported.",
        "btn_total": "Total",
        "btn_success": "Success",
        "btn_failed": "Failed",
    },
    "bn": {
        "processing": "⏳ চ্যানেলের অনুরোধ প্রসেসিং হচ্ছে...",
        "no_sessions": "❌ কোনো বৈধ সেশন পাওয়া যায়নি।",
        "request_failed": "❌ অনুরোধ প্রসেসিংকালে ত্রুটি ঘটেছে।",
        "done": "✅ সম্পন্ন — {success}টি সফল | ❌ {failed}টি ব্যর্থ",
        "failed_report": "❌ সব প্রচেষ্টা ব্যর্থ — {failed}টি ব্যর্থ",
        "invalid_target": "❌ ভুল টার্গেট। চ্যানেলের ইউজারনেম বা লিংক পাঠান (যেমন <code>@channel</code> বা <code>https://t.me/+link</code>)। <code>all</code> দিয়ে জয়েন করা সমর্থিত নয়।",
        "btn_total": "মোট",
        "btn_success": "সফল",
        "btn_failed": "ব্যর্থ",
    },
    "hi": {
        "processing": "⏳ चैनल प्रक्रिया जारी है...",
        "no_sessions": "❌ कोई वैध सेशन नहीं मिला।",
        "request_failed": "❌ अनुरोध प्रक्रिया के दौरान त्रुटि हुई।",
        "done": "✅ पूर्ण — {success} सफल | ❌ {failed} विफल",
        "failed_report": "❌ सभी प्रयास विफल — {failed} विफल",
        "invalid_target": "❌ अमान्य लक्ष्य। चैनल का यूज़रनेम या लिंक भेजें (जैसे <code>@channel</code> या <code>https://t.me/+link</code>)। <code>all</code> के साथ जॉइन करना समर्थित नहीं है।",
        "btn_total": "कुल",
        "btn_success": "सफल",
        "btn_failed": "विफल",
    },
    "ur": {
        "processing": "⏳ چینل عمل جاری ہے...",
        "no_sessions": "❌ کوئی بھی درست سیشن نہیں ملا۔",
        "request_failed": "❌ درخواست کے عمل کے دوران ایک خرابی پیش آئی۔",
        "done": "✅ مکمل — {success} کامیاب | ❌ {failed} ناکام",
        "failed_report": "❌ تمام کوششیں ناکام — {failed} ناکام",
        "invalid_target": "❌ غلط ہدف۔ چینل کا صارف نام یا لنک بھیجیں (مثال: <code>@channel</code> یا <code>https://t.me/+link</code>)۔ <code>all</code> کے ساتھ جوائن کرنا معاون نہیں ہے۔",
        "btn_total": "کل",
        "btn_success": "کامیاب",
        "btn_failed": "ناکام",
    },
    "ar": {
        "processing": "⏳ جاري معالجة طلب القناة...",
        "no_sessions": "❌ لم يتم العثور على جلسات صالحة.",
        "request_failed": "❌ حدث خطأ أثناء معالجة الطلب.",
        "done": "✅ اكتمل — {success} نجاح | ❌ {failed} فشل",
        "failed_report": "❌ فشلت جميع المحاولات — {failed} فشل",
        "invalid_target": "❌ هدف غير صالح. أرسل اسم مستخدم القناة أو الرابط (مثال: <code>@channel</code> أو <code>https://t.me/+link</code>). الانضمام عبر <code>all</code> غير مدعوم.",
        "btn_total": "الإجمالي",
        "btn_success": "الناجحة",
        "btn_failed": "الفاشلة",
    },
    "zh": {
        "processing": "⏳ 正在处理频道请求...",
        "no_sessions": "❌ 未找到有效会话。",
        "request_failed": "❌ 处理请求时出错。",
        "done": "✅ 完成 — {success} 成功 | ❌ {failed} 失败",
        "failed_report": "❌ 所有尝试均失败 — {failed} 失败",
        "invalid_target": "❌ 无效目标。请发送频道用户名或链接（例如 <code>@channel</code> 或 <code>https://t.me/+link</code>）。不支持使用 <code>all</code> 加入。",
        "btn_total": "总计",
        "btn_success": "成功",
        "btn_failed": "失败",
    },
}

ENTER_CLEAR_CONTACTS_PROMPT = {
    "en": "📂 Please send your Telegram session file (.session) or ZIP archive to clear contacts:",
    "bn": "📂 পরিচিতি পরিষ্কার করতে দয়া করে আপনার টেলিগ্রাম সেশন ফাইল (.session) বা ZIP আর্কাইভ পাঠান:",
    "hi": "📂 संपर्क साफ़ करने के लिए कृपया अपनी टेलीग्राम सेशन फ़ाइल (.session) या ZIP संग्रह भेजें:",
    "ur": "📂 روابط صاف کرنے کے لیے براہ کرم اپنی ٹیلیگرام سیشن فائل (.session) یا ZIP آرکائیو بھیجیں:",
    "ar": "📂 يرجى إرسال ملف جلسة تليجرام (.session) أو أرشيف ZIP لمسح جهات الاتصال:",
    "zh": "📂 请发送您的 Telegram 会话文件 (.session) 或 ZIP 压缩包以清除联系人：",
}

CLEAR_CONTACTS_MESSAGES = {
    "en": {
        "processing": "⏳ Clearing contacts from sessions...",
        "no_sessions": "❌ No valid sessions found.",
        "request_failed": "❌ An error occurred during request processing.",
        "done": "✅ Contacts Cleared — {success} success | ❌ {failed} failed",
        "failed_report": "❌ All attempts failed — {failed} failed",
        "btn_total": "Total",
        "btn_success": "Cleared",
        "btn_failed": "Failed",
    },
    "bn": {
        "processing": "⏳ সেশন থেকে পরিচিতি পরিষ্কার করা হচ্ছে...",
        "no_sessions": "❌ কোনো বৈধ সেশন পাওয়া যায়নি।",
        "request_failed": "❌ অনুরোধ প্রসেসিংকালে ত্রুটি ঘটেছে।",
        "done": "✅ পরিচিতি পরিষ্কার সম্পন্ন — {success}টি সফল | ❌ {failed}টি ব্যর্থ",
        "failed_report": "❌ সব প্রচেষ্টা ব্যর্থ — {failed}টি ব্যর্থ",
        "btn_total": "মোট",
        "btn_success": "পরিষ্কারকৃত",
        "btn_failed": "ব্যর্থ",
    },
    "hi": {
        "processing": "⏳ सेशन से संपर्क साफ़ किए जा रहे हैं...",
        "no_sessions": "❌ कोई वैध सेशन नहीं मिला।",
        "request_failed": "❌ अनुरोध प्रक्रिया के दौरान त्रुटि हुई।",
        "done": "✅ संपर्क साफ़ पूर्ण — {success} सफल | ❌ {failed} विफल",
        "failed_report": "❌ सभी प्रयास विफल — {failed} विफल",
        "btn_total": "कुल",
        "btn_success": "साफ़",
        "btn_failed": "विफल",
    },
    "ur": {
        "processing": "⏳ سیشنز سے روابط صاف کیے جا رہے ہیں...",
        "no_sessions": "❌ کوئی بھی درست سیشن نہیں ملا۔",
        "request_failed": "❌ درخواست کے عمل کے دوران ایک خرابی پیش آئی۔",
        "done": "✅ روابط صاف مکمل — {success} کامیاب | ❌ {failed} ناکام",
        "failed_report": "❌ تمام کوششیں ناکام — {failed} ناکام",
        "btn_total": "کل",
        "btn_success": "صاف کردہ",
        "btn_failed": "ناکام",
    },
    "ar": {
        "processing": "⏳ جاري مسح جهات الاتصال من الجلسات...",
        "no_sessions": "❌ لم يتم العثور على جلسات صالحة.",
        "request_failed": "❌ حدث خطأ أثناء معالجة الطلب.",
        "done": "✅ اكتمل مسح جهات الاتصال — {success} نجاح | ❌ {failed} فشل",
        "failed_report": "❌ فشلت جميع المحاولات — {failed} فشل",
        "btn_total": "الإجمالي",
        "btn_success": "تم المسح",
        "btn_failed": "الفاشلة",
    },
    "zh": {
        "processing": "⏳ 正在从会话中清除联系人...",
        "no_sessions": "❌ 未找到有效会话。",
        "request_failed": "❌ 处理请求时出错。",
        "done": "✅ 联系人已清除 — {success} 成功 | ❌ {failed} 失败",
        "failed_report": "❌ 所有尝试均失败 — {failed} 失败",
        "btn_total": "总计",
        "btn_success": "已清除",
        "btn_failed": "失败",
    },
}

ENTER_KILL_SESSIONS_PROMPT = {
    "en": "☠️ Please send your Telegram session file (.session) or ZIP archive to terminate all other active sessions:",
    "bn": "☠️ অন্যান্য সমস্ত সক্রিয় সেশন বন্ধ করতে আপনার টেলিগ্রাম সেশন ফাইল (.session) বা ZIP পাঠ্য পাঠান:",
    "hi": "☠️ अन्य सभी सक्रिय सेशन समाप्त करने के लिए कृपया अपनी टेलीग्राम सेशन फ़ाइल (.session) या ZIP भेजें:",
    "ur": "☠️ دیگر تمام فعال سیشنز کو ختم کرنے کے لیے اپنی ٹیلیگرام سیشن فائل (.session) یا ZIP بھیجیں:",
    "ar": "☠️ يرجى إرسال ملف جلسة تليجرام (.session) أو أرشيف ZIP لإنهاء جميع الجلسات النشطة الأخرى:",
    "zh": "☠️ 请发送您的 Telegram 会话文件 (.session) 或 ZIP 压缩包以终止所有其他活动会话：",
}

KILL_SESSIONS_CONFIRM_PROMPT = {
    "en": "⚠️ <b>Confirmation Warning</b>\n\nAre you sure you want to log out all other devices for these account(s)?\nThis will terminate active sessions on phones, desktops, and web clients.",
    "bn": "⚠️ <b>নিশ্চিতকরণ সতর্কবার্তা</b>\n\nআপনি কি নিশ্চিত যে আপনি এই অ্যাকাউন্টের অন্যান্য সমস্ত ডিভাইস থেকে লগ আউট করতে চান?",
    "hi": "⚠️ <b>पुष्टि चेतावनी</b>\n\nक्या आप निश्चित हैं कि आप इस खाते के अन्य सभी उपकरणों को लॉग आउट करना चाहते हैं?",
    "ur": "⚠️ <b>تصدیق کی تنبیہ</b>\n\nکیا آپ کو یقین ہے کہ آپ اس اکاؤنٹ کے دیگر تمام آلات کو لاگ آؤٹ کرنا چاہتے ہیں؟",
    "ar": "⚠️ <b>تحذير التأكيد</b>\n\nهل أنت تأكد من أنك تريد تسجيل الخروج من جميع الأجهزة الأخرى لهذا الحساب؟",
    "zh": "⚠️ <b>确认警告</b>\n\n您确定要注销此帐户的所有其他设备吗？",
}

KILL_SESSIONS_MESSAGES = {
    "en": {
        "processing": "⏳ Terminating other active sessions...",
        "no_sessions": "❌ No valid sessions found.",
        "request_failed": "❌ An error occurred while terminating sessions.",
        "confirm_btn": "☠️ Yes, Terminate All Other Sessions",
        "done": "☠️ <b>Session Termination Summary</b>\n\n✅ Successfully Terminated: {killed}\n⏳ Skipped (&lt;24h Fresh): {fresh_forbidden}\n❌ Failed/Revoked: {failed}",
        "btn_total": "Total",
        "btn_killed": "Terminated",
        "btn_fresh": "Skipped (&lt;24h)",
        "btn_failed": "Failed",
    },
    "bn": {
        "processing": "⏳ অন্যান্য সমস্ত সক্রিয় সেশন বন্ধ করা হচ্ছে...",
        "no_sessions": "❌ কোনো বৈধ সেশন পাওয়া যায়নি।",
        "request_failed": "❌ সেশন বন্ধ করার সময় ত্রুটি ঘটেছে।",
        "confirm_btn": "☠️ হ্যাঁ, অন্যান্য সমস্ত সেশন বন্ধ করুন",
        "done": "☠️ <b>সেশন বন্ধের সারাংশ</b>\n\n✅ সফলভাবে বন্ধ করা হয়েছে: {killed}\n⏳ এড়িয়ে যাওয়া হয়েছে (&lt;24h ফ্রেশ): {fresh_forbidden}\n❌ ব্যর্থ/বাতিল: {failed}",
        "btn_total": "মোট",
        "btn_killed": "বন্ধ করা হয়েছে",
        "btn_fresh": "এড়িয়ে যাওয়া (&lt;24h)",
        "btn_failed": "ব্যর্থ",
    },
    "hi": {
        "processing": "⏳ अन्य सभी सक्रिय सेशन समाप्त किए जा रहे हैं...",
        "no_sessions": "❌ कोई वैध सेशन नहीं मिला।",
        "request_failed": "❌ सेशन समाप्त करते समय त्रुटि हुई।",
        "confirm_btn": "☠️ हाँ, अन्य सभी सेशन समाप्त करें",
        "done": "☠️ <b>सेशन समाप्ति का सारांश</b>\n\n✅ सफलतापूर्वक समाप्त: {killed}\n⏳ छोड़े गए (&lt;24h ताज़ा): {fresh_forbidden}\n❌ विफल/रद्द: {failed}",
        "btn_total": "कुल",
        "btn_killed": "समाप्त",
        "btn_fresh": "छोड़े गए (&lt;24h)",
        "btn_failed": "विफल",
    },
    "ur": {
        "processing": "⏳ دیگر تمام فعال سیشنز کو ختم کیا جا رہا ہے...",
        "no_sessions": "❌ کوئی بھی درست سیشن نہیں ملا۔",
        "request_failed": "❌ سیشنز ختم کرتے وقت خرابی پیش آئی۔",
        "confirm_btn": "☠️ ہاں، دیگر تمام سیشنز ختم کریں",
        "done": "☠️ <b>سیشن ختم کرنے کا خلاصہ</b>\n\n✅ کامیابی سے ختم کیے گئے: {killed}\n⏳ چھوڑے گئے (&lt;24h تازہ): {fresh_forbidden}\n❌ ناکام/منسوخ: {failed}",
        "btn_total": "کل",
        "btn_killed": "ختم کیے گئے",
        "btn_fresh": "چھوڑے گئے (&lt;24h)",
        "btn_failed": "ناکام",
    },
    "ar": {
        "processing": "⏳ جاري إنهاء جميع الجلسات النشطة الأخرى...",
        "no_sessions": "❌ لم يتم العثور على جلسات صالحة.",
        "request_failed": "❌ حدث خطأ أثناء إنهاء الجلسات.",
        "confirm_btn": "☠️ نعم، إنهاء جميع الجلسات الأخرى",
        "done": "☠️ <b>ملخص إنهاء الجلسات</b>\n\n✅ تم الإنهاء بنجاح: {killed}\n⏳ تم التجاهل (جديدة &lt;24 ساعة): {fresh_forbidden}\n❌ فاشلة/ملغاة: {failed}",
        "btn_total": "الإجمالي",
        "btn_killed": "تم الإنهاء",
        "btn_fresh": "تجاهل (<24ساعة)",
        "btn_failed": "الفاشلة",
    },
    "zh": {
        "processing": "⏳ 正在终止所有其他活动会话...",
        "no_sessions": "❌ 未找到有效会话。",
        "request_failed": "❌ 终止会话时出错。",
        "confirm_btn": "☠️ 是的，终止所有其他会话",
        "done": "☠️ <b>会话终止摘要</b>\n\n✅ 成功终止：{killed}\n⏳ 已跳过 (&lt;24h 新会话)：{fresh_forbidden}\n❌ 失败/已被撤销：{failed}",
        "btn_total": "总计",
        "btn_killed": "已终止",
        "btn_fresh": "已跳过 (&lt;24h)",
        "btn_failed": "失败",
    },
}

ENTER_FRESH_SESSION_PROMPT = {
    "en": "🔄 Send your Telegram session file (.session) or ZIP archive to create fresh new sessions:",
    "bn": "🔄 নতুন ফ্রেশ সেশন তৈরি করতে আপনার টেলিগ্রাম সেশন ফাইল (.session) বা ZIP পাঠান:",
    "hi": "🔄 नया फ्रेश सेशन बनाने के लिए अपनी टेलीग्राम सेशन फ़ाइल (.session) या ZIP भेजें:",
    "ur": "🔄 نئی فریش سیشن بنانے کے لیے اپنی ٹیلیگرام سیشن فائل (.session) یا ZIP بھیجیں:",
    "ar": "🔄 أرسل ملف جلسة تليجرام (.session) أو أرشيف ZIP لإنشاء جلسات جديدة منتعشة:",
    "zh": "🔄 发送您的 Telegram 会话文件 (.session) 或 ZIP 压缩包以创建全新会话：",
}

FRESH_SESSION_2FA_PROMPT = {
    "en": "🔐 Some sessions may require a 2FA password.\n\nPlease send your 2FA password now, or tap Skip if accounts have no 2FA:",
    "bn": "🔐 কিছু সেশনে 2FA পাসওয়ার্ড প্রয়োজন হতে পারে।\n\nএখন আপনার 2FA পাসওয়ার্ড পাঠান অথবা স্কিপ করুন:",
    "hi": "🔐 कुछ सेशन को 2FA पासवर्ड की आवश्यकता हो सकती है।\n\nअभी अपना 2FA पासवर्ड भेजें या छोड़ें:",
    "ur": "🔐 کچھ سیشنز میں 2FA پاسورڈ درکار ہو سکتا ہے۔\n\nاپنا 2FA پاسورڈ ابھی بھیجیں یا چھوڑ دیں:",
    "ar": "🔐 قد تحتاج بعض الجلسات إلى كلمة مرور 2FA.\n\nأرسل كلمة مرور 2FA الآن أو تخطَّ:",
    "zh": "🔐 部分会话可能需要双重验证 (2FA) 密码。\n\n请立即发送 2FA 密码，或点击跳过：",
}

FRESH_SESSION_CONFIRM_PROMPT = {
    "en": "⚠️ <b>Fresh Session Warning</b>\n\nThis will:\n• Send a login OTP via your existing session\n• Create a new session file for each account\n• The old session remains unchanged\n\nAre you sure you want to proceed?",
    "bn": "⚠️ <b>ফ্রেশ সেশন সতর্কতা</b>\n\nএটি:\n• বিদ্যমান সেশনে OTP পাঠাবে\n• প্রতিটি অ্যাকাউন্টের জন্য নতুন সেশন তৈরি করবে\n• পুরানো সেশন অপরিবর্তিত থাকবে\n\nআপনি কি এগিয়ে যেতে চান?",
    "hi": "⚠️ <b>फ्रेश सेशन चेतावनी</b>\n\nयह:\n• मौजूदा सेशन के माध्यम से OTP भेजेगा\n• प्रत्येक खाते के लिए नया सेशन बनाएगा\n• पुराना सेशन अपरिवर्तित रहेगा\n\nक्या आप आगे बढ़ना चाहते हैं?",
    "ur": "⚠️ <b>فریش سیشن انتباہ</b>\n\nیہ:\n• موجودہ سیشن سے OTP بھیجے گا\n• ہر اکاؤنٹ کے لیے نئی سیشن بنائے گا\n• پرانی سیشن غیر تبدیل رہے گی\n\nکیا آپ آگے بڑھنا چاہتے ہیں؟",
    "ar": "⚠️ <b>تحذير الجلسة الجديدة</b>\n\nسيتم:\n• إرسال OTP عبر الجلسة الحالية\n• إنشاء ملف جلسة جديد لكل حساب\n• الجلسة القديمة تبقى دون تغيير\n\nهل تريد المتابعة؟",
    "zh": "⚠️ <b>新会话警告</b>\n\n此操作将：\n• 通过现有会话发送 OTP\n• 为每个账户创建新的会话文件\n• 旧会话保持不变\n\n确认继续？",
}

FRESH_SESSION_MESSAGES = {
    "en": {
        "processing": "⏳ Creating fresh sessions... This may take a while (OTP wait per account).",
        "no_sessions": "❌ No valid sessions found in the file.",
        "request_failed": "❌ An error occurred while processing sessions.",
        "confirm_btn": "🔄 Yes, Create Fresh Sessions",
        "skip_2fa": "⏭ Skip (No 2FA)",
        "done": "🔄 <b>Fresh Session Summary</b>\n\n✅ Successfully Migrated: {succeeded}\n❌ Failed: {failed}\n\n{details}\nNew sessions ZIP is attached above.",
        "no_new": "🔄 <b>Fresh Session Summary</b>\n\n✅ Migrated: {succeeded}\n❌ Failed: {failed}\n\n{details}",
        "btn_total": "Total",
        "btn_ok": "Migrated",
        "btn_failed": "Failed",
        "new_zip_caption": "🔄 Fresh Sessions ({succeeded} accounts)",
        "fail_zip_caption": "❌ Failed Sessions ({failed} accounts)",
    },
    "bn": {
        "processing": "⏳ ফ্রেশ সেশন তৈরি হচ্ছে... (প্রতিটি অ্যাকাউন্টের জন্য OTP অপেক্ষা)",
        "no_sessions": "❌ ফাইলে কোনো বৈধ সেশন পাওয়া যায়নি।",
        "request_failed": "❌ সেশন প্রক্রিয়া করার সময় ত্রুটি হয়েছে।",
        "confirm_btn": "🔄 হ্যাঁ, ফ্রেশ সেশন তৈরি করুন",
        "skip_2fa": "⏭ এড়িয়ে যান (2FA নেই)",
        "done": "🔄 <b>ফ্রেশ সেশন সারাংশ</b>\n\n✅ সফল: {succeeded}\n❌ ব্যর্থ: {failed}\n\n{details}\nনতুন সেশন ZIP উপরে যুক্ত হয়েছে।",
        "no_new": "🔄 <b>ফ্রেশ সেশন সারাংশ</b>\n\n✅ সফল: {succeeded}\n❌ ব্যর্থ: {failed}\n\n{details}",
        "btn_total": "মোট",
        "btn_ok": "সফল",
        "btn_failed": "ব্যর্থ",
        "new_zip_caption": "🔄 ফ্রেশ সেশন ({succeeded} অ্যাকাউন্ট)",
        "fail_zip_caption": "❌ ব্যর্থ সেশন ({failed} অ্যাকাউন্ট)",
    },
    "hi": {
        "processing": "⏳ फ्रेश सेशन बनाए जा रहे हैं... (प्रत्येक खाते के लिए OTP प्रतीक्षा)",
        "no_sessions": "❌ फ़ाइल में कोई मान्य सेशन नहीं मिला।",
        "request_failed": "❌ सेशन प्रोसेस करते समय त्रुटि हुई।",
        "confirm_btn": "🔄 हाँ, फ्रेश सेशन बनाएं",
        "skip_2fa": "⏭ छोड़ें (2FA नहीं)",
        "done": "🔄 <b>फ्रेश सेशन सारांश</b>\n\n✅ सफल: {succeeded}\n❌ विफल: {failed}\n\n{details}\nनई सेशन ZIP ऊपर संलग्न है।",
        "no_new": "🔄 <b>फ्रेश सेशन सारांश</b>\n\n✅ सफल: {succeeded}\n❌ विफल: {failed}\n\n{details}",
        "btn_total": "कुल",
        "btn_ok": "सफल",
        "btn_failed": "विफल",
        "new_zip_caption": "🔄 फ्रेश सेशन ({succeeded} खाते)",
        "fail_zip_caption": "❌ विफल सेशन ({failed} खाते)",
    },
    "ur": {
        "processing": "⏳ فریش سیشنز بنائی جا رہی ہیں... (ہر اکاؤنٹ کے لیے OTP انتظار)",
        "no_sessions": "❌ فائل میں کوئی درست سیشن نہیں ملی۔",
        "request_failed": "❌ سیشنز پروسیس کرتے وقت خرابی پیش آئی۔",
        "confirm_btn": "🔄 ہاں، فریش سیشنز بنائیں",
        "skip_2fa": "⏭ چھوڑیں (2FA نہیں)",
        "done": "🔄 <b>فریش سیشن خلاصہ</b>\n\n✅ کامیاب: {succeeded}\n❌ ناکام: {failed}\n\n{details}\nنئی سیشن ZIP اوپر منسلک ہے۔",
        "no_new": "🔄 <b>فریش سیشن خلاصہ</b>\n\n✅ کامیاب: {succeeded}\n❌ ناکام: {failed}\n\n{details}",
        "btn_total": "کل",
        "btn_ok": "کامیاب",
        "btn_failed": "ناکام",
        "new_zip_caption": "🔄 فریش سیشنز ({succeeded} اکاؤنٹس)",
        "fail_zip_caption": "❌ ناکام سیشنز ({failed} اکاؤنٹس)",
    },
    "ar": {
        "processing": "⏳ جاري إنشاء جلسات جديدة... (انتظار OTP لكل حساب)",
        "no_sessions": "❌ لم يتم العثور على جلسات صالحة في الملف.",
        "request_failed": "❌ حدث خطأ أثناء معالجة الجلسات.",
        "confirm_btn": "🔄 نعم، أنشئ جلسات جديدة",
        "skip_2fa": "⏭ تخطَّ (لا يوجد 2FA)",
        "done": "🔄 <b>ملخص الجلسات الجديدة</b>\n\n✅ ناجح: {succeeded}\n❌ فاشل: {failed}\n\n{details}\nملف ZIP للجلسات الجديدة مرفق أعلاه.",
        "no_new": "🔄 <b>ملخص الجلسات الجديدة</b>\n\n✅ ناجح: {succeeded}\n❌ فاشل: {failed}\n\n{details}",
        "btn_total": "الإجمالي",
        "btn_ok": "ناجح",
        "btn_failed": "فاشل",
        "new_zip_caption": "🔄 جلسات جديدة ({succeeded} حساب)",
        "fail_zip_caption": "❌ جلسات فاشلة ({failed} حساب)",
    },
    "zh": {
        "processing": "⏳ 正在创建新会话... (每个账户等待 OTP)",
        "no_sessions": "❌ 文件中未找到有效会话。",
        "request_failed": "❌ 处理会话时出错。",
        "confirm_btn": "🔄 是的，创建新会话",
        "skip_2fa": "⏭ 跳过 (无 2FA)",
        "done": "🔄 <b>新会话摘要</b>\n\n✅ 成功：{succeeded}\n❌ 失败：{failed}\n\n{details}\n新会话 ZIP 已附在上方。",
        "no_new": "🔄 <b>新会话摘要</b>\n\n✅ 成功：{succeeded}\n❌ 失败：{failed}\n\n{details}",
        "btn_total": "总计",
        "btn_ok": "成功",
        "btn_failed": "失败",
        "new_zip_caption": "🔄 新会话 ({succeeded} 个账户)",
        "fail_zip_caption": "❌ 失败会话 ({failed} 个账户)",
    },
}

LIST_CHECKER_MESSAGES = {
    "en": {
        "file1_prompt": "📦 <b>List Checker — Step 1/2</b>\n\nSend the <b>first</b> ZIP archive:",
        "file2_prompt": "📦 <b>List Checker — Step 2/2</b>\n\n✅ File 1 received: <code>{name}</code>\n\nNow send the <b>second</b> ZIP archive:",
        "processing": "⚙️ Comparing archives... please wait.",
        "no_match": "😕 <b>No common items found.</b>\n\nThe two archives share no matching Tdata folders, .session or .json files.",
        "done": (
            "✅ <b>Matched Result</b>\n\n"
            "📁 Tdata folders : <b>{tdata}</b>\n"
            "🔑 Session files : <b>{session}</b>\n"
            "📄 JSON files    : <b>{json}</b>\n"
            "━━━━━━━━━━━━━━\n"
            "✅ Total         : <b>{total} common items</b>"
        ),
        "invalid_format": "❌ Only <b>.zip</b> archives are supported.",
        "download_failed": "❌ Failed to download the archive. Please try again.",
        "result_caption": "📦 matched_files.zip — {total} items",
    },
    "bn": {
        "file1_prompt": "📦 <b>লিস্ট চেকার — ধাপ 1/2</b>\n\n<b>প্রথম</b> ZIP আর্কাইভ পাঠান:",
        "file2_prompt": "📦 <b>লিস্ট চেকার — ধাপ 2/2</b>\n\n✅ ফাইল 1 পাওয়া গেছে: <code>{name}</code>\n\nএখন <b>দ্বিতীয়</b> ZIP আর্কাইভ পাঠান:",
        "processing": "⚙️ আর্কাইভ তুলনা করা হচ্ছে... অপেক্ষা করুন।",
        "no_match": "😕 <b>কোনো সাধারণ আইটেম পাওয়া যায়নি।</b>\n\nদুটি আর্কাইভে কোনো মিলের Tdata ফোল্ডার, .session বা .json ফাইল নেই।",
        "done": (
            "✅ <b>মিলের ফলাফল</b>\n\n"
            "📁 Tdata ফোল্ডার : <b>{tdata}</b>\n"
            "🔑 সেশন ফাইল   : <b>{session}</b>\n"
            "📄 JSON ফাইল   : <b>{json}</b>\n"
            "━━━━━━━━━━━━━━\n"
            "✅ মোট          : <b>{total}টি সাধারণ আইটেম</b>"
        ),
        "invalid_format": "❌ শুধুমাত্র <b>.zip</b> আর্কাইভ সমর্থিত।",
        "download_failed": "❌ আর্কাইভ ডাউনলোড ব্যর্থ হয়েছে। আবার চেষ্টা করুন।",
        "result_caption": "📦 matched_files.zip — {total}টি আইটেম",
    },
    "hi": {
        "file1_prompt": "📦 <b>लिस्ट चेकर — चरण 1/2</b>\n\n<b>पहली</b> ZIP संग्रह भेजें:",
        "file2_prompt": "📦 <b>लिस्ट चेकर — चरण 2/2</b>\n\n✅ फ़ाइल 1 प्राप्त: <code>{name}</code>\n\nअब <b>दूसरी</b> ZIP संग्रह भेजें:",
        "processing": "⚙️ संग्रह की तुलना हो रही है... कृपया प्रतीक्षा करें।",
        "no_match": "😕 <b>कोई समान आइटम नहीं मिला।</b>\n\nदोनों संग्रहों में कोई समान Tdata फ़ोल्डर, .session या .json फ़ाइल नहीं है।",
        "done": (
            "✅ <b>मिलान परिणाम</b>\n\n"
            "📁 Tdata फ़ोल्डर : <b>{tdata}</b>\n"
            "🔑 सेशन फ़ाइलें : <b>{session}</b>\n"
            "📄 JSON फ़ाइलें : <b>{json}</b>\n"
            "━━━━━━━━━━━━━━\n"
            "✅ कुल           : <b>{total} समान आइटम</b>"
        ),
        "invalid_format": "❌ केवल <b>.zip</b> संग्रह समर्थित हैं।",
        "download_failed": "❌ संग्रह डाउनलोड विफल रहा। कृपया पुनः प्रयास करें।",
        "result_caption": "📦 matched_files.zip — {total} आइटम",
    },
    "ur": {
        "file1_prompt": "📦 <b>لسٹ چیکر — مرحلہ 1/2</b>\n\n<b>پہلی</b> ZIP فائل بھیجیں:",
        "file2_prompt": "📦 <b>لسٹ چیکر — مرحلہ 2/2</b>\n\n✅ فائل 1 موصول: <code>{name}</code>\n\nاب <b>دوسری</b> ZIP فائل بھیجیں:",
        "processing": "⚙️ آرکائیوز کا موازنہ ہو رہا ہے... انتظار کریں۔",
        "no_match": "😕 <b>کوئی مشترکہ آئٹم نہیں ملا۔</b>\n\nدونوں آرکائیوز میں کوئی مشترکہ Tdata فولڈر، .session یا .json فائل نہیں ہے۔",
        "done": (
            "✅ <b>موافق نتیجہ</b>\n\n"
            "📁 Tdata فولڈر : <b>{tdata}</b>\n"
            "🔑 سیشن فائلیں : <b>{session}</b>\n"
            "📄 JSON فائلیں : <b>{json}</b>\n"
            "━━━━━━━━━━━━━━\n"
            "✅ کل            : <b>{total} مشترکہ آئٹمز</b>"
        ),
        "invalid_format": "❌ صرف <b>.zip</b> آرکائیوز معاون ہیں۔",
        "download_failed": "❌ آرکائیو ڈاؤن لوڈ ناکام رہا۔ براہ کرم دوبارہ کوشش کریں۔",
        "result_caption": "📦 matched_files.zip — {total} آئٹمز",
    },
    "ar": {
        "file1_prompt": "📦 <b>فاحص القائمة — الخطوة 1/2</b>\n\nأرسل الأرشيف <b>الأول</b> ZIP:",
        "file2_prompt": "📦 <b>فاحص القائمة — الخطوة 2/2</b>\n\n✅ تم استلام الملف 1: <code>{name}</code>\n\nأرسل الأرشيف <b>الثاني</b> ZIP الآن:",
        "processing": "⚙️ جاري مقارنة الأرشيفات... يرجى الانتظار.",
        "no_match": "😕 <b>لم يتم العثور على عناصر مشتركة.</b>\n\nلا توجد مجلدات Tdata أو ملفات .session أو .json مشتركة في الأرشيفين.",
        "done": (
            "✅ <b>نتيجة المطابقة</b>\n\n"
            "📁 مجلدات Tdata : <b>{tdata}</b>\n"
            "🔑 ملفات الجلسة : <b>{session}</b>\n"
            "📄 ملفات JSON   : <b>{json}</b>\n"
            "━━━━━━━━━━━━━━\n"
            "✅ الإجمالي      : <b>{total} عنصر مشترك</b>"
        ),
        "invalid_format": "❌ يُدعم فقط أرشيف <b>.zip</b>.",
        "download_failed": "❌ فشل تنزيل الأرشيف. حاول مرة أخرى.",
        "result_caption": "📦 matched_files.zip — {total} عنصر",
    },
    "zh": {
        "file1_prompt": "📦 <b>列表检查器 — 第 1/2 步</b>\n\n发送<b>第一个</b> ZIP 压缩包：",
        "file2_prompt": "📦 <b>列表检查器 — 第 2/2 步</b>\n\n✅ 已收到文件 1：<code>{name}</code>\n\n现在发送<b>第二个</b> ZIP 压缩包：",
        "processing": "⚙️ 正在比较压缩包... 请稍候。",
        "no_match": "😕 <b>未找到共同项目。</b>\n\n两个压缩包中没有相同的 Tdata 文件夹、.session 或 .json 文件。",
        "done": (
            "✅ <b>匹配结果</b>\n\n"
            "📁 Tdata 文件夹 : <b>{tdata}</b>\n"
            "🔑 会话文件     : <b>{session}</b>\n"
            "📄 JSON 文件    : <b>{json}</b>\n"
            "━━━━━━━━━━━━━━\n"
            "✅ 总计          : <b>{total} 个共同项目</b>"
        ),
        "invalid_format": "❌ 仅支持 <b>.zip</b> 压缩包。",
        "download_failed": "❌ 压缩包下载失败，请重试。",
        "result_caption": "📦 matched_files.zip — {total} 个项目",
    },
}


PRIVACY_SETTINGS_MESSAGES: dict[str, dict[str, Any]] = {
    "en": {
        "prompt_file": "🔐 <b>Privacy Settings Manager</b>\n\nPlease send a <b>.session</b> file or a <b>.zip</b> archive containing Telegram sessions:",
        "prompt_2fa": "🔐 <b>2FA Password</b>\n\nPlease send your 2FA password now, or tap <b>Skip</b> if your accounts do not require 2FA:",
        "prompt_mode": "🔐 <b>Privacy Mode</b>\n\nChoose how you want to configure privacy settings:\n\n• <b>Preset Mode</b>: Apply a pre-configured privacy level in 1-click.\n• <b>Custom Mode</b>: Configure rules individually.",
        "prompt_preset": "🔐 <b>Select Privacy Preset</b>\n\nSelect a preset to apply automatically to all sessions:\n\n🔴 <b>Maximum Privacy</b>: Nobody for sensitive info; My Contacts for Photo & Invites.\n🟡 <b>Medium Privacy</b>: Contacts for sensitive info; Everybody for Photo & Voice.\n🟢 <b>Open / Public Privacy</b>: Everybody for all rules.",
        "prompt_rule_key": "🔐 <b>Custom Privacy Configuration</b>\n\nTap a privacy rule to change its setting, then tap <b>Apply Custom Settings</b>:",
        "prompt_rule_value": "🔐 <b>Configuring {rule_name}</b>\n\nWho can see / access this setting?",
        "processing": "⚙️ Applying privacy settings to account(s)... please wait.",
        "done": (
            "🔐 <b>Privacy Settings Summary</b>\n\n"
            "👥 Processed : <b>{total}</b>\n"
            "✅ Success   : <b>{succeeded}</b>\n"
            "❌ Failed    : <b>{failed}</b>\n\n"
            "⚙️ Applied Rule : <b>{preset}</b>"
            "{details}"
        ),
        "btn_preset": "Apply Preset",
        "btn_custom": "Configure Rules",
        "btn_apply_custom": "Apply Custom Settings",
        "btn_total": "Total",
        "btn_ok": "Succeeded",
        "btn_failed": "Failed",
        "invalid_file": "❌ Invalid file format. Please send a .session or .zip file.",
        "presets": {
            "maximum": "Maximum Privacy",
            "medium": "Medium Privacy",
            "open": "Open / Public Privacy",
            "custom": "Custom Rules",
        },
        "rules": {
            "last_seen": "Last Seen",
            "phone_number": "Phone Number",
            "profile_photo": "Profile Photo",
            "forwarded_messages": "Forwarded Messages",
            "calls": "Calls",
            "p2p_calls": "P2P Calls",
            "group_invites": "Group Invites",
            "voice_messages": "Voice Messages",
        },
        "values": {
            "everybody": "Everybody",
            "contacts": "My Contacts",
            "nobody": "Nobody",
        },
    },
    "bn": {
        "prompt_file": "🔐 <b>গোপনীয়তা সেটিংস ম্যানেজার</b>\n\nঅনুগ্রহ করে একটি <b>.session</b> ফাইল অথবা সেশনযুক্ত <b>.zip</b> আর্কাইভ পাঠান:",
        "prompt_2fa": "🔐 <b>2FA পাসওয়ার্ড</b>\n\nআপনার 2FA পাসওয়ার্ড পাঠান অথবা 2FA প্রয়োজন না হলে <b>স্কিপ</b> চাপুন:",
        "prompt_mode": "🔐 <b>গোপনীয়তা মোড</b>\n\nআপনি কিভাবে গোপনীয়তা সেটিংস করতে চান তা বেছে নিন:\n\n• <b>প্রিসেট মোড</b>: এক ক্লিকে প্রয়োগ করুন।\n• <b>কাস্টম মোড</b>: প্রতিটি নিয়ম আলাদাভাবে কনফিগার করুন।",
        "prompt_preset": "🔐 <b>প্রিসেট নির্বাচন করুন</b>\n\nসমস্ত সেশনে স্বয়ংক্রিয়ভাবে প্রয়োগ করতে একটি প্রিসেট নির্বাচন করুন:",
        "prompt_rule_key": "🔐 <b>কাস্টম গোপনীয়তা কনফিগারেশন</b>\n\nনিয়ম পরিবর্তন করতে ট্যাপ করুন, তারপর <b>কাস্টম প্রয়োগ করুন</b> চাপুন:",
        "prompt_rule_value": "🔐 <b>{rule_name} কনফিগারেশন</b>\n\nকে এটি দেখতে / ব্যবহার করতে পারবে?",
        "processing": "⚙️ গোপনীয়তা সেটিংস প্রয়োগ করা হচ্ছে... অপেক্ষা করুন।",
        "done": (
            "🔐 <b>গোপনীয়তা সেটিংস সারসংক্ষেপ</b>\n\n"
            "👥 প্রক্রিয়াজাত : <b>{total}</b>\n"
            "✅ সফল        : <b>{succeeded}</b>\n"
            "❌ ব্যর্থ       : <b>{failed}</b>\n\n"
            "⚙️ প্রয়োগকৃত নিয়ম : <b>{preset}</b>"
            "{details}"
        ),
        "btn_preset": "প্রিসেট প্রয়োগ করুন",
        "btn_custom": "নিয়ম কনফিগার করুন",
        "btn_apply_custom": "কাস্টম প্রয়োগ করুন",
        "btn_total": "মোট",
        "btn_ok": "সফল",
        "btn_failed": "ব্যর্থ",
        "invalid_file": "❌ অকার্যকর ফাইল। একটি .session বা .zip ফাইল পাঠান।",
        "presets": {
            "maximum": "সর্বোচ্চ গোপনীয়তা",
            "medium": "মাঝারি গোপনীয়তা",
            "open": "উন্মুক্ত / সর্বজনীন গোপনীয়তা",
            "custom": "কাস্টম নিয়ম",
        },
        "rules": {
            "last_seen": "শেষ দেখা সময়",
            "phone_number": "ফোন নম্বর",
            "profile_photo": "প্রোফাইল ছবি",
            "forwarded_messages": "ফরোয়ার্ড বার্তা",
            "calls": "কলসমূহ",
            "p2p_calls": "P2P কলসমূহ",
            "group_invites": "গ্রুপ আমন্ত্রণ",
            "voice_messages": "ভয়েস বার্তা",
        },
        "values": {
            "everybody": "সবাই",
            "contacts": "আমার কনট্যাক্টস",
            "nobody": "কেউ না",
        },
    },
    "hi": {
        "prompt_file": "🔐 <b>गोपनीयता सेटिंग्स प्रबंधक</b>\n\nकृपया एक <b>.session</b> फ़ाइल या <b>.zip</b> संग्रह भेजें:",
        "prompt_2fa": "🔐 <b>2FA पासवर्ड</b>\n\nअपना 2FA पासवर्ड भेजें या 2FA की आवश्यकता न होने पर <b>स्किप</b> दबाएँ:",
        "prompt_mode": "🔐 <b>गोपनीयता मोड</b>\n\nचुनें कि आप गोपनीयता सेटिंग्स कैसे कॉन्फ़िगर करना चाहते हैं:\n\n• <b>प्रीसेट मोड</b>: 1-क्लिक में लागू करें।\n• <b>कस्टम मोड</b>: प्रत्येक नियम को व्यक्तिगत रूप से कॉन्फ़िगर करें।",
        "prompt_preset": "🔐 <b>प्रीसेट चुनें</b>\n\nसभी सेशन पर लागू करने के लिए प्रीसेट चुनें:",
        "prompt_rule_key": "🔐 <b>कस्टम गोपनीयता कॉन्फ़िगरेशन</b>\n\nनियम बदलने के लिए टैप करें, फिर <b>कस्टम लागू करें</b> दबाएँ:",
        "prompt_rule_value": "🔐 <b>{rule_name} कॉन्फ़िगरेशन</b>\n\nयह सेटिंग कौन देख / उपयोग कर सकता है?",
        "processing": "⚙️ गोपनीयता सेटिंग्स लागू की जा रही हैं... कृपया प्रतीक्षा करें।",
        "done": (
            "🔐 <b>गोपनीयता सेटिंग्स सारांश</b>\n\n"
            "👥 संसाधित : <b>{total}</b>\n"
            "✅ सफल     : <b>{succeeded}</b>\n"
            "❌ विफल    : <b>{failed}</b>\n\n"
            "⚙️ लागू नियम : <b>{preset}</b>"
            "{details}"
        ),
        "btn_preset": "प्रीसेट लागू करें",
        "btn_custom": "नियम कॉन्फ़िगर करें",
        "btn_apply_custom": "कस्टम लागू करें",
        "btn_total": "कुल",
        "btn_ok": "सफल",
        "btn_failed": "विफल",
        "invalid_file": "❌ अमान्य फ़ाइल प्रारूप। .session या .zip फ़ाइल भेजें।",
        "presets": {
            "maximum": "अधिकतम गोपनीयता",
            "medium": "मध्यम गोपनीयता",
            "open": "खुली / सार्वजनिक गोपनीयता",
            "custom": "कस्टम नियम",
        },
        "rules": {
            "last_seen": "अंतिम बार देखा गया",
            "phone_number": "फ़ोन नंबर",
            "profile_photo": "प्रोफ़ाइल फ़ोटो",
            "forwarded_messages": "फ़ॉरवर्ड किए गए संदेश",
            "calls": "कॉल्स",
            "p2p_calls": "P2P कॉल्स",
            "group_invites": "समूह आमंत्रण",
            "voice_messages": "वॉयस संदेश",
        },
        "values": {
            "everybody": "सभी",
            "contacts": "मेरे संपर्क",
            "nobody": "कोई नहीं",
        },
    },
    "ur": {
        "prompt_file": "🔐 <b>رازداری ترتیبات مینیجر</b>\n\nبرائے مہربانی <b>.session</b> یا <b>.zip</b> فائل بھیجیں:",
        "prompt_2fa": "🔐 <b>2FA پاسورڈ</b>\n\nاپنا 2FA پاسورڈ بھیجیں یا <b>اسکپ</b> کریں:",
        "prompt_mode": "🔐 <b>رازداری موڈ</b>\n\nانتخاب کریں:\n\n• <b>پری سیٹ موڈ</b>: ایک کلک میں لاگو کریں۔\n• <b>کسٹم موڈ</b>: انفرادی ترتیبات۔",
        "prompt_preset": "🔐 <b>پری سیٹ منتخب کریں</b>\n\nسب سیشنز پر لاگو کرنے کے لیے پری سیٹ منتخب کریں:",
        "prompt_rule_key": "🔐 <b>کسٹم رازداری ترتیبات</b>\n\nترمیم کے لیے ٹیپ کریں، پھر <b>لاگو کریں</b> دبائیں:",
        "prompt_rule_value": "🔐 <b>{rule_name} ترتیبات</b>\n\nکون اسے دیکھ سکتا ہے؟",
        "processing": "⚙️ رازداری ترتیبات لاگو ہو رہی ہیں... انتظار کریں۔",
        "done": (
            "🔐 <b>رازداری ترتیبات خلاصہ</b>\n\n"
            "👥 پروسیسڈ : <b>{total}</b>\n"
            "✅ کامیاب    : <b>{succeeded}</b>\n"
            "❌ ناکام     : <b>{failed}</b>\n\n"
            "⚙️ لاگو شدہ  : <b>{preset}</b>"
            "{details}"
        ),
        "btn_preset": "پری سیٹ لاگو کریں",
        "btn_custom": "قواعد سیٹ کریں",
        "btn_apply_custom": "کسٹم لاگو کریں",
        "btn_total": "کل",
        "btn_ok": "کامیاب",
        "btn_failed": "ناکام",
        "invalid_file": "❌ غیر موزوں فائل۔ .session یا .zip بھیجیں۔",
        "presets": {
            "maximum": "زیادہ سے زیادہ رازداری",
            "medium": "درمیانی رازداری",
            "open": "کھلی / عوامی رازداری",
            "custom": "کسٹم قواعد",
        },
        "rules": {
            "last_seen": "آخری بار دیکھا گیا",
            "phone_number": "فون نمبر",
            "profile_photo": "پروفائل تصویر",
            "forwarded_messages": "فارورڈ شدہ پیغامات",
            "calls": "کالز",
            "p2p_calls": "P2P کالز",
            "group_invites": "گروپ دعوت نامے",
            "voice_messages": "وائس پیغامات",
        },
        "values": {
            "everybody": "سبھی",
            "contacts": "میرے رابطے",
            "nobody": "کوئی نہیں",
        },
    },
    "ar": {
        "prompt_file": "🔐 <b>مدير إعدادات الخصوصية</b>\n\nيرجى إرسال ملف <b>.session</b> أو أرشيف <b>.zip</b> يحتوي على جلسات:",
        "prompt_2fa": "🔐 <b>كلمة مرور 2FA</b>\n\nأدخل كلمة مرور 2FA أو اضغط <b>تخطي</b>:",
        "prompt_mode": "🔐 <b>وضع الخصوصية</b>\n\nاختر طريقة ضبط الخصوصية:\n\n• <b>وضع القوالب</b>: تطبيق بنقرة واحدة.\n• <b>الوضع المخصص</b>: ضبط كل قاعدة على حدة.",
        "prompt_preset": "🔐 <b>اختر قالب الخصوصية</b>\n\nاختر قالباً لتطبيقه تلقائياً على جميع الجلسات:",
        "prompt_rule_key": "🔐 <b>إعدادات الخصوصية المخصصة</b>\n\nاضغط على قاعدة للتعديل، ثم اضغط <b>تطبيق المخصص</b>:",
        "prompt_rule_value": "🔐 <b>إعداد {rule_name}</b>\n\nمن يمكنه رؤية / استخدام هذا الإعداد؟",
        "processing": "⚙️ جاري تطبيق إعدادات الخصوصية... يرجى الانتظار.",
        "done": (
            "🔐 <b>ملخص إعدادات الخصوصية</b>\n\n"
            "👥 المُعالجة  : <b>{total}</b>\n"
            "✅ الناجحة    : <b>{succeeded}</b>\n"
            "❌ الفاشلة   : <b>{failed}</b>\n\n"
            "⚙️ القالب المطبق : <b>{preset}</b>"
            "{details}"
        ),
        "btn_preset": "تطبيق القالب",
        "btn_custom": "ضبط القواعد",
        "btn_apply_custom": "تطبيق المخصص",
        "btn_total": "الإجمالي",
        "btn_ok": "ناجح",
        "btn_failed": "فاشل",
        "invalid_file": "❌ صيغة ملف غير صالحة. أرسل ملف .session أو .zip.",
        "presets": {
            "maximum": "أقصى خصوصية",
            "medium": "خصوصية متوسطة",
            "open": "الخصوصية المفتوحة / العامة",
            "custom": "قواعد مخصصة",
        },
        "rules": {
            "last_seen": "آخر ظهور",
            "phone_number": "رقم الهاتف",
            "profile_photo": "صورة الملف الشخصي",
            "forwarded_messages": "الرسائل المعاد توجيهها",
            "calls": "المكالمات",
            "p2p_calls": "مكالمات P2P",
            "group_invites": "دعوات المجموعات",
            "voice_messages": "الرسائل الصوتية",
        },
        "values": {
            "everybody": "الجميع",
            "contacts": "جهات اتصالي",
            "nobody": "لا أحد",
        },
    },
    "zh": {
        "prompt_file": "🔐 <b>隐私设置管理器</b>\n\n请发送 <b>.session</b> 文件或包含会话的 <b>.zip</b> 压缩包：",
        "prompt_2fa": "🔐 <b>2FA 密码</b>\n\n发送您的 2FA 密码，若无 2FA 请点击 <b>跳过</b>：",
        "prompt_mode": "🔐 <b>隐私模式</b>\n\n选择配置方式：\n\n• <b>预设模式</b>：一键应用预设安全级别。\n• <b>自定义模式</b>：逐项单独配置。",
        "prompt_preset": "🔐 <b>选择隐私预设</b>\n\n选择要自动应用到所有会话的预设：",
        "prompt_rule_key": "🔐 <b>自定义隐私配置</b>\n\n点击规则进行修改，然后点击 <b>应用自定义设置</b>：",
        "prompt_rule_value": "🔐 <b>配置 {rule_name}</b>\n\n谁可以看到 / 使用此设置？",
        "processing": "⚙️ 正在应用隐私设置... 请稍候。",
        "done": (
            "🔐 <b>隐私设置摘要</b>\n\n"
            "👥 已处理   : <b>{total}</b>\n"
            "✅ 成功     : <b>{succeeded}</b>\n"
            "❌ 失败     : <b>{failed}</b>\n\n"
            "⚙️ 应用设置 : <b>{preset}</b>"
            "{details}"
        ),
        "btn_preset": "应用预设",
        "btn_custom": "配置规则",
        "btn_apply_custom": "应用自定义设置",
        "btn_total": "总计",
        "btn_ok": "成功",
        "btn_failed": "失败",
        "invalid_file": "❌ 无效的文件格式。请发送 .session 或 .zip 文件。",
        "presets": {
            "maximum": "最高隐私",
            "medium": "中等隐私",
            "open": "公开 / 开放隐私",
            "custom": "自定义规则",
        },
        "rules": {
            "last_seen": "上线时间",
            "phone_number": "手机号码",
            "profile_photo": "个人头像",
            "forwarded_messages": "转发消息",
            "calls": "通话",
            "p2p_calls": "P2P 通话",
            "group_invites": "群组邀请",
            "voice_messages": "语音消息",
        },
        "values": {
            "everybody": "所有人",
            "contacts": "我的联系人",
            "nobody": "不允许任何人",
        },
    },
}

ENTER_CLEAN_CHAT_PROMPT = {

    "en": "📂 Please send your Telegram session file (.session) or ZIP archive to clean chat history:",
    "bn": "📂 চ্যাট ইতিহাস পরিষ্কার করতে দয়া করে আপনার টেলিগ্রাম সেশন ফাইল (.session) বা ZIP আর্কাইভ পাঠান:",
    "hi": "📂 चैट इतिहास साफ़ करने के लिए कृपया अपनी टेलीग्राम सेशन फ़ाइल (.session) या ZIP संग्रह भेजें:",
    "ur": "📂 چیٹ ہسٹری صاف کرنے کے لیے براہ کرم اپنی ٹیلیگرام سیشن فائل (.session) یا ZIP آرکائیو بھیجیں:",
    "ar": "📂 يرجى إرسال ملف جلسة تليجرام (.session) أو أرشيف ZIP لمسح سجل المحادثات:",
    "zh": "📂 请发送您的 Telegram 会话文件 (.session) 或 ZIP 压缩包以清理聊天记录：",
}

CLEAN_CHAT_MODE_PROMPT = {
    "en": (
        "📦 Found <b>{count}</b> session(s)\n\n"
        "🧹 Select one or more chat types:\n\n"
        "⚠️ Selecting Groups leaves groups; selecting Channels unsubscribes them."
    ),
    "bn": (
        "📦 <b>{count}</b>টি সেশন পাওয়া গেছে\n\n"
        "🧹 এক বা একাধিক চ্যাটের ধরন নির্বাচন করুন:\n\n"
        "⚠️ Groups নির্বাচন করলে গ্রুপ ছাড়বে; Channels নির্বাচন করলে চ্যানেল ছাড়বে।"
    ),
    "hi": (
        "📦 <b>{count}</b> सेशन मिले\n\n"
        "🧹 एक या अधिक चैट प्रकार चुनें:\n\n"
        "⚠️ Groups चुनने पर ग्रुप छूटेंगे; Channels चुनने पर चैनल छूटेंगे।"
    ),
    "ur": (
        "📦 <b>{count}</b> سیشنز ملے\n\n"
        "🧹 ایک یا زیادہ چیٹ کی اقسام منتخب کریں:\n\n"
        "⚠️ Groups منتخب کرنے پر گروپس، اور Channels پر چینلز چھوڑے جائیں گے۔"
    ),
    "ar": (
        "📦 تم العثور على <b>{count}</b> جلسة\n\n"
        "🧹 اختر نوعًا واحدًا أو أكثر من المحادثات:\n\n"
        "⚠️ اختيار Groups يغادر المجموعات؛ واختيار Channels يلغي الاشتراك فيها."
    ),
    "zh": (
        "📦 找到 <b>{count}</b> 个会话\n\n"
        "🧹 选择一种或多种聊天类型：\n\n"
        "⚠️ 选择 Groups 会退出群组；选择 Channels 会取消订阅频道。"
    ),
}

CLEAN_CHAT_MODE_LABELS = {
    "en": ("👤 DMs", "🤖 Bots", "👥 Groups", "📢 Channels"),
    "bn": ("👤 পিভি", "🤖 বট", "👥 গ্রুপ", "📢 চ্যানেল"),
    "hi": ("👤 निजी चैट", "🤖 बॉट", "👥 ग्रुप", "📢 चैनल"),
    "ur": ("👤 پی وی", "🤖 بوٹس", "👥 گروپس", "📢 چینلز"),
    "ar": ("👤 الخاص", "🤖 البوتات", "👥 المجموعات", "📢 القنوات"),
    "zh": ("👤 私聊", "🤖 机器人", "👥 群组", "📢 频道"),
}

CLEAN_CHAT_SELECTION_ACTIONS = {
    "en": {
        "select_all": "☑️ Select All",
        "clear_all": "✖️ Clear Selection",
        "confirm": "🚀 Confirm & Clean",
        "select_one": "Select at least one chat type.",
    },
    "bn": {
        "select_all": "☑️ সব নির্বাচন",
        "clear_all": "✖️ নির্বাচন মুছুন",
        "confirm": "🚀 নিশ্চিত করে পরিষ্কার করুন",
        "select_one": "কমপক্ষে একটি চ্যাটের ধরন নির্বাচন করুন।",
    },
    "hi": {
        "select_all": "☑️ सभी चुनें",
        "clear_all": "✖️ चयन हटाएँ",
        "confirm": "🚀 पुष्टि करके साफ़ करें",
        "select_one": "कम से कम एक चैट प्रकार चुनें।",
    },
    "ur": {
        "select_all": "☑️ سب منتخب کریں",
        "clear_all": "✖️ انتخاب صاف کریں",
        "confirm": "🚀 تصدیق اور کلین",
        "select_one": "کم از کم ایک چیٹ کی قسم منتخب کریں۔",
    },
    "ar": {
        "select_all": "☑️ تحديد الكل",
        "clear_all": "✖️ مسح التحديد",
        "confirm": "🚀 تأكيد والمسح",
        "select_one": "اختر نوع محادثة واحدًا على الأقل.",
    },
    "zh": {
        "select_all": "☑️ 全选",
        "clear_all": "✖️ 清除选择",
        "confirm": "🚀 确认并清理",
        "select_one": "请至少选择一种聊天类型。",
    },
}

CLEAN_CHAT_MESSAGES = {
    "en": {
        "processing_progress": "⏳ Cleaning chats from sessions...\n✅ Deleted: {done}",
        "processing": "⏳ Cleaning chats from sessions...",
        "no_sessions": "❌ No valid sessions found.",
        "request_failed": "❌ An error occurred during request processing.",
        "done": "✅ Chat Cleaned — {success} success | ❌ {failed} failed",
        "failed_report": "❌ All attempts failed — {failed} failed",
        "btn_total": "Total",
        "btn_success": "Cleaned",
        "btn_failed": "Failed",
    },
    "bn": {
        "processing_progress": "⏳ সেশন থেকে চ্যাট পরিষ্কার করা হচ্ছে...\n✅ মুছে ফেলা হয়েছে: {done}",
        "processing": "⏳ সেশন থেকে চ্যাট পরিষ্কার করা হচ্ছে...",
        "no_sessions": "❌ কোনো বৈধ সেশন পাওয়া যায়নি।",
        "request_failed": "❌ অনুরোধ প্রসেসিংকালে ত্রুটি ঘটেছে।",
        "done": "✅ চ্যাট পরিষ্কার সম্পন্ন — {success}টি সফল | ❌ {failed}টি ব্যর্থ",
        "failed_report": "❌ সব প্রচেষ্টা ব্যর্থ — {failed}টি ব্যর্থ",
        "btn_total": "মোট",
        "btn_success": "পরিষ্কারকৃত",
        "btn_failed": "ব্যর্থ",
    },
    "hi": {
        "processing_progress": "⏳ सेशन से चैट साफ़ किए जा रहे हैं...\n✅ हटाए गए: {done}",
        "processing": "⏳ सेशन से चैट साफ़ किए जा रहे हैं...",
        "no_sessions": "❌ कोई वैध सेशन नहीं मिला।",
        "request_failed": "❌ अनुरोध प्रक्रिया के दौरान त्रुटि हुई।",
        "done": "✅ चैट साफ़ पूर्ण — {success} सफल | ❌ {failed} विफल",
        "failed_report": "❌ सभी प्रयास विफल — {failed} विफल",
        "btn_total": "कुल",
        "btn_success": "साफ़",
        "btn_failed": "विफल",
    },
    "ur": {
        "processing_progress": "⏳ سیشنز سے چیٹس صاف کی جا رہی ہیں...\n✅ حذف شدہ: {done}",
        "processing": "⏳ سیشنز سے چیٹس صاف کی جا رہی ہیں...",
        "no_sessions": "❌ کوئی بھی درست سیشن نہیں ملا۔",
        "request_failed": "❌ درخواست کے عمل کے دوران ایک خرابی پیش آئی۔",
        "done": "✅ چیٹ صاف مکمل — {success} کامیاب | ❌ {failed} ناکام",
        "failed_report": "❌ تمام کوششیں ناکام — {failed} ناکام",
        "btn_total": "کل",
        "btn_success": "صاف کردہ",
        "btn_failed": "ناکام",
    },
    "ar": {
        "processing_progress": "⏳ جاري مسح المحادثات من الجلسات...\n✅ تم حذف: {done}",
        "processing": "⏳ جاري مسح المحادثات من الجلسات...",
        "no_sessions": "❌ لم يتم العثور على جلسات صالحة.",
        "request_failed": "❌ حدث خطأ أثناء معالجة الطلب.",
        "done": "✅ اكتمل مسح المحادثات — {success} نجاح | ❌ {failed} فشل",
        "failed_report": "❌ فشلت جميع المحاولات — {failed} فشل",
        "btn_total": "الإجمالي",
        "btn_success": "تم المسح",
        "btn_failed": "الفاشلة",
    },
    "zh": {
        "processing_progress": "⏳ 正在从会话中清理聊天...\n✅ 已删除: {done}",
        "processing": "⏳ 正在从会话中清理聊天...",
        "no_sessions": "❌ 未找到有效会话。",
        "request_failed": "❌ 处理请求时出错。",
        "done": "✅ 聊天已清理 — {success} 成功 | ❌ {failed} 失败",
        "failed_report": "❌ 所有尝试均失败 — {failed} 失败",
        "btn_total": "总计",
        "btn_success": "已清理",
        "btn_failed": "失败",
    },
}

ENTER_DELETE_CONTACT_PROMPT = {
    "en": "📂 Please send your Telegram session file (.session) or ZIP archive to select contacts for deletion:",
    "bn": "📂 মুছে ফেলার জন্য কনট্যাক্ট বেছে নিতে আপনার টেলিগ্রাম সেশন ফাইল (.session) বা ZIP আর্কাইভ পাঠান:",
    "hi": "📂 हटाने के लिए संपर्क चुनने के लिए अपनी टेलीग्राम सेशन फ़ाइल (.session) या ZIP संग्रह भेजें:",
    "ur": "📂 حذف کرنے کے لیے روابط منتخب کرنے کے لیے اپنی ٹیلیگرام سیشن فائل (.session) یا ZIP آرکائیو بھیجیں:",
    "ar": "📂 يرجى إرسال ملف جلسة تليجرام (.session) أو أرشيف ZIP لاختيار جهات الاتصال للحذف:",
    "zh": "📂 请发送您的 Telegram 会话文件 (.session) 或 ZIP 压缩包以选择要删除的联系人：",
}

DELETE_CONTACT_SELECT_PROMPT = {
    "en": "📇 <b>Delete Contacts Selection</b>\n\nFound <b>{count}</b> contact(s). Select the contacts to delete:",
    "bn": "📇 <b>কনট্যাক্ট নির্বাচন মুছুন</b>\n\n<b>{count}</b>টি কনট্যাক্ট পাওয়া গেছে। মুছে ফেলার জন্য কনট্যাক্ট নির্বাচন করুন:",
    "hi": "📇 <b>संपर्क चयन हटाएँ</b>\n\n<b>{count}</b> संपर्क मिले। हटाने के लिए संपर्क चुनें:",
    "ur": "📇 <b>روابط کے انتخاب کو حذف کریں</b>\n\n<b>{count}</b> روابط ملے۔ حذف کرنے کے لیے روابط منتخب کریں:",
    "ar": "📇 <b>تحديد جهات الاتصال للحذف</b>\n\nتم العثور على <b>{count}</b> جهة اتصال. اختر جهات الاتصال المراد حذفها:",
    "zh": "📇 <b>选择要删除的联系人</b>\n\n找到 <b>{count}</b> 个联系人。选择要删除的联系人：",
}

DELETE_CONTACT_MESSAGES = {
    "en": {
        "fetching": "⏳ Fetching contacts list from session...",
        "processing": "⏳ Deleting selected contacts...",
        "no_sessions": "❌ No valid sessions found.",
        "no_contacts": "ℹ️ No contacts found in this session.",
        "request_failed": "❌ An error occurred during request processing.",
        "done": "✅ Contacts Deleted — {success} success | ❌ {failed} failed",
        "failed_report": "❌ All attempts failed — {failed} failed",
        "btn_total": "Total",
        "btn_deleted": "Deleted",
        "btn_failed": "Failed",
        "select_all": "✅ Select All",
        "deselect_all": "❌ Deselect All",
        "delete_btn": "🗑️ Delete Selected ({count})",
        "select_at_least_one": "Please select at least one contact to delete.",
    },
    "bn": {
        "fetching": "⏳ সেশন থেকে কনট্যাক্ট তালিকা আনা হচ্ছে...",
        "processing": "⏳ নির্বাচিত কনট্যাক্ট মুছে ফেলা হচ্ছে...",
        "no_sessions": "❌ কোনো বৈধ সেশন পাওয়া যায়নি।",
        "no_contacts": "ℹ️ এই সেশনে কোনো কনট্যাক্ট পাওয়া যায়নি।",
        "request_failed": "❌ অনুরোধ প্রসেসিংকালে ত্রুটি ঘটেছে।",
        "done": "✅ কনট্যাক্ট মুছে ফেলা সম্পন্ন — {success}টি সফল | ❌ {failed}টি ব্যর্থ",
        "failed_report": "❌ সব প্রচেষ্টা ব্যর্থ — {failed}টি ব্যর্থ",
        "btn_total": "মোট",
        "btn_deleted": "মুছে ফেলা হয়েছে",
        "btn_failed": "ব্যর্থ",
        "select_all": "✅ সব নির্বাচন",
        "deselect_all": "❌ সব বাতিল",
        "delete_btn": "🗑️ নির্বাচিতগুলো মুছুন ({count})",
        "select_at_least_one": "মুছে ফেলার জন্য কমপক্ষে একটি কনট্যাক্ট নির্বাচন করুন।",
    },
    "hi": {
        "fetching": "⏳ सेशन से संपर्क सूची प्राप्त की जा रही है...",
        "processing": "⏳ चयनित संपर्क हटाए जा रहे हैं...",
        "no_sessions": "❌ कोई वैध सेशन नहीं मिला।",
        "no_contacts": "ℹ️ इस सेशन में कोई संपर्क नहीं मिला।",
        "request_failed": "❌ अनुरोध प्रक्रिया के दौरान त्रुटि हुई।",
        "done": "✅ संपर्क हटाए गए — {success} सफल | ❌ {failed} विफल",
        "failed_report": "❌ सभी प्रयास विफल — {failed} विफल",
        "btn_total": "कुल",
        "btn_deleted": "हटाया गया",
        "btn_failed": "विफल",
        "select_all": "✅ सभी चुनें",
        "deselect_all": "❌ सभी हटाएं",
        "delete_btn": "🗑️ चयनित हटाएँ ({count})",
        "select_at_least_one": "हटाने के लिए कृपया कम से कम एक संपर्क चुनें।",
    },
    "ur": {
        "fetching": "⏳ سیشن سے روابط کی فہرست حاصل کی جا رہی ہے...",
        "processing": "⏳ منتخب کردہ روابط حذف کیے جا رہے ہیں...",
        "no_sessions": "❌ کوئی بھی درست سیشن نہیں ملا۔",
        "no_contacts": "ℹ️ اس سیشن میں کوئی بھی رابطہ نہیں ملا۔",
        "request_failed": "❌ درخواست کے عمل کے دوران ایک خرابی پیش آئی۔",
        "done": "✅ روابط حذف مکمل — {success} کامیاب | ❌ {failed} ناکام",
        "failed_report": "❌ تمام کوششیں ناکام — {failed} ناکام",
        "btn_total": "کل",
        "btn_deleted": "حذف شدہ",
        "btn_failed": "ناکام",
        "select_all": "✅ سب منتخب کریں",
        "deselect_all": "❌ سب منسوخ کریں",
        "delete_btn": "🗑️ منتخب حذف کریں ({count})",
        "select_at_least_one": "براہ کرم حذف کرنے کے لیے کم از کم ایک رابطہ منتخب کریں۔",
    },
    "ar": {
        "fetching": "⏳ جاري جلب قائمة جهات الاتصال من الجلسة...",
        "processing": "⏳ جاري حذف جهات الاتصال المحددة...",
        "no_sessions": "❌ لم يتم العثور على جلسات صالحة.",
        "no_contacts": "ℹ️ لم يتم العثور على جهات اتصال في هذه الجلسة.",
        "request_failed": "❌ حدث خطأ أثناء معالجة الطلب.",
        "done": "✅ اكتمل حذف جهات الاتصال — {success} نجاح | ❌ {failed} فشل",
        "failed_report": "❌ فشلت جميع المحاولات — {failed} فشل",
        "btn_total": "الإجمالي",
        "btn_deleted": "تم الحذف",
        "btn_failed": "الفاشلة",
        "select_all": "✅ تحديد الكل",
        "deselect_all": "❌ إلغاء تحديد الكل",
        "delete_btn": "🗑️ حذف المحدد ({count})",
        "select_at_least_one": "يرجى تحديد جهة اتصال واحدة على الأقل للحذف.",
    },
    "zh": {
        "fetching": "⏳ 正在从会话获取联系人列表...",
        "processing": "⏳ 正在删除所选联系人...",
        "no_sessions": "❌ 未找到有效会话。",
        "no_contacts": "ℹ️ 在此会话中未找到联系人。",
        "request_failed": "❌ 处理请求时出错。",
        "done": "✅ 联系人已删除 — {success} 成功 | ❌ {failed} 失败",
        "failed_report": "❌ 所有尝试均失败 — {failed} 失败",
        "btn_total": "总计",
        "btn_deleted": "已删除",
        "btn_failed": "失败",
        "select_all": "✅ 全选",
        "deselect_all": "❌ 取消全选",
        "delete_btn": "🗑️ 删除所选 ({count})",
        "select_at_least_one": "请至少选择一个要删除的联系人。",
    },
}

ENTER_PROFILE_SETUP_PROMPT = {
    "en": "📂 Please send your Telegram session file (.session) or ZIP archive to edit account profiles:",
    "bn": "📂 অ্যাকাউন্ট প্রোফাইল এডিট করতে আপনার টেলিগ্রাম সেশন ফাইল (.session) বা ZIP আর্কাইভ পাঠান:",
    "hi": "📂 अकाउंट प्रोफ़ाइल एडिट करने के लिए अपनी टेलीग्राम सेशन फ़ाइल (.session) या ZIP संग्रह भेजें:",
    "ur": "📂 اکاؤنٹ پروفائل ایڈیٹ کرنے کے لیے اپنی ٹیلیگرام سیشن فائل (.session) یا ZIP آرکائیو بھیجیں:",
    "ar": "📂 يرجى إرسال ملف جلسة تليجرام (.session) أو أرشيف ZIP لتعديل ملفات التعريف:",
    "zh": "📂 请发送您的 Telegram 会话文件 (.session) 或 ZIP 压缩包以编辑账号资料：",
}

PROFILE_SETUP_ACCOUNT_PROMPT = {
    "en": (
        "🎭 <b>Profile Setup (Account {current}/{total})</b>\n\n"
        "📱 <b>Phone / File:</b> <code>{identifier}</code>\n"
        "👤 <b>First Name:</b> {first_name} {pending_first}\n"
        "👤 <b>Last Name:</b> {last_name} {pending_last}\n"
        "🏷️ <b>Username:</b> {username} {pending_username}\n"
        "📝 <b>Bio:</b> {about} {pending_about}\n"
        "🖼️ <b>Photo:</b> {photo_status}\n\n"
        "Select a field below to edit, apply changes, or skip this account:"
    ),
    "bn": (
        "🎭 <b>প্রোফাইল সেটআপ (অ্যাকাউন্ট {current}/{total})</b>\n\n"
        "📱 <b>ফোন / ফাইল:</b> <code>{identifier}</code>\n"
        "👤 <b>নাম:</b> {first_name} {pending_first}\n"
        "👤 <b>পদবি:</b> {last_name} {pending_last}\n"
        "🏷️ <b>ইউজারনেম:</b> {username} {pending_username}\n"
        "📝 <b>বায়ো:</b> {about} {pending_about}\n"
        "🖼️ <b>ছবি:</b> {photo_status}\n\n"
        "সম্পাদনা করতে নিচের ফিল্ড বেছে নিন, পরিবর্তন প্রয়োগ করুন বা স্কিপ করুন:"
    ),
    "hi": (
        "🎭 <b>प्रोफ़ाइल सेटअप (अकाउंट {current}/{total})</b>\n\n"
        "📱 <b>फ़ोन / फ़ाइल:</b> <code>{identifier}</code>\n"
        "👤 <b>नाम:</b> {first_name} {pending_first}\n"
        "👤 <b>उपनाम:</b> {last_name} {pending_last}\n"
        "🏷️ <b>यूज़रनेम:</b> {username} {pending_username}\n"
        "📝 <b>बायो:</b> {about} {pending_about}\n"
        "🖼️ <b>फ़ोटो:</b> {photo_status}\n\n"
        "संपादित करने के लिए नीचे फ़ील्ड चुनें, परिवर्तन लागू करें या छोड़ें:"
    ),
    "ur": (
        "🎭 <b>پروفائل سیٹ اپ (اکاؤنٹ {current}/{total})</b>\n\n"
        "📱 <b>فون / فائل:</b> <code>{identifier}</code>\n"
        "👤 <b>نام:</b> {first_name} {pending_first}\n"
        "👤 <b>آخری نام:</b> {last_name} {pending_last}\n"
        "🏷️ <b>یوزر نیم:</b> {username} {pending_username}\n"
        "📝 <b>بائیو:</b> {about} {pending_about}\n"
        "🖼️ <b>تصویر:</b> {photo_status}\n\n"
        "ترمیم کے لیے نیچے سے فیلڈ منتخب کریں، تبدیلیاں لاگو کریں یا اسکیپ کریں:"
    ),
    "ar": (
        "🎭 <b>إعداد الملف الشخصي (الحساب {current}/{total})</b>\n\n"
        "📱 <b>الهاتف / الملف:</b> <code>{identifier}</code>\n"
        "👤 <b>الاسم الأول:</b> {first_name} {pending_first}\n"
        "👤 <b>اسم العائلة:</b> {last_name} {pending_last}\n"
        "🏷️ <b>اسم المستخدم:</b> {username} {pending_username}\n"
        "📝 <b>السيرة الذاتية:</b> {about} {pending_about}\n"
        "🖼️ <b>الصورة:</b> {photo_status}\n\n"
        "اختر حقلًا أدناه للتعديل، تطبيق التغييرات، أو تخطي هذا الحساب:"
    ),
    "zh": (
        "🎭 <b>个人资料设置 (账号 {current}/{total})</b>\n\n"
        "📱 <b>手机/文件:</b> <code>{identifier}</code>\n"
        "👤 <b>名字:</b> {first_name} {pending_first}\n"
        "👤 <b>姓氏:</b> {last_name} {pending_last}\n"
        "🏷️ <b>用户名:</b> {username} {pending_username}\n"
        "📝 <b>简介:</b> {about} {pending_about}\n"
        "🖼️ <b>头像:</b> {photo_status}\n\n"
        "请选择下方字段进行编辑、应用更改或跳过此账号："
    ),
}

PROFILE_SETUP_NAME_PROMPT = {
    "en": "👤 Send the new <b>First Name</b> (and optional last name separated by space):",
    "bn": "👤 নতুন <b>নাম</b> পাঠান (স্পেস দিয়ে পদবি সহ):",
    "hi": "👤 नया <b>पहला नाम</b> (और स्पेस के साथ उपनाम) भेजें:",
    "ur": "👤 نیا <b>نام</b> (اور جگہ کے ساتھ آخری نام) بھیجیں:",
    "ar": "👤 أرسل <b>الاسم الأول</b> الجديد (واسم العائلة مفصولاً بمسافة):",
    "zh": "👤 发送新的<b>名字</b>（用空格隔开姓氏）：",
}

PROFILE_SETUP_USERNAME_PROMPT = {
    "en": "🏷️ Send the new <b>Username</b> (without @):",
    "bn": "🏷️ নতুন <b>ইউজারনেম</b> পাঠান (@ ছাড়া):",
    "hi": "🏷️ नया <b>यूज़रनेम</b> (@ के बिना) भेजें:",
    "ur": "🏷️ نیا <b>یوزر نیم</b> (@ کے بغیر) بھیجیں:",
    "ar": "🏷️ أرسل <b>اسم المستخدم</b> الجديد (بدون @):",
    "zh": "🏷️ 发送新的<b>用户名</b>（不带 @）：",
}

PROFILE_SETUP_ABOUT_PROMPT = {
    "en": "📝 Send the new <b>Bio / About</b> text:",
    "bn": "📝 নতুন <b>বায়ো / বিবরণ</b> পাঠ্য পাঠান:",
    "hi": "📝 नया <b>बायो / विवरण</b> भेजें:",
    "ur": "📝 نیا <b>بائیو / تفصیل</b> متن بھیجیں:",
    "ar": "📝 أرسل نص <b>السيرة الذاتية</b> الجديد:",
    "zh": "📝 发送新的<b>个人简介</b>文本：",
}

PROFILE_SETUP_PHOTO_PROMPT = {
    "en": "🖼️ Send a <b>Photo</b> for profile picture:",
    "bn": "🖼️ প্রোফাইল ছবির জন্য একটি <b>ছবি</b> পাঠান:",
    "hi": "🖼️ प्रोफ़ाइल चित्र के लिए एक <b>फ़ोटो</b> भेजें:",
    "ur": "🖼️ پروفائل تصویر کے لیے ایک <b>تصویر</b> بھیجیں:",
    "ar": "🖼️ أرسل <b>صورة</b> للملف الشخصي:",
    "zh": "🖼️ 发送一张<b>图片</b>作为头像：",
}

PROFILE_SETUP_MESSAGES = {
    "en": {
        "fetching": "⏳ Fetching profile details...",
        "applying": "⏳ Applying profile updates...",
        "no_sessions": "❌ No valid sessions found.",
        "request_failed": "❌ An error occurred during request processing.",
        "done": "✅ Profile Setup Completed — {modified} modified | ⏭️ {skipped} skipped | ❌ {failed} failed",
        "failed_report": "❌ All attempts failed — {failed} failed",
        "btn_total": "Total",
        "btn_modified": "Modified",
        "btn_skipped": "Skipped",
        "btn_failed": "Failed",
        "btn_edit_name": "Edit Name",
        "btn_edit_username": "Edit Username",
        "btn_edit_about": "Edit Bio",
        "btn_set_photo": "Set Photo",
        "btn_apply": "Apply Changes & Next",
        "btn_skip": "Skip Account",
        "photo_pending": "New Photo Selected",
        "photo_none": "None",
    },
    "bn": {
        "fetching": "⏳ প্রোফাইল বিবরণ আনা হচ্ছে...",
        "applying": "⏳ প্রোফাইল আপডেট প্রয়োগ করা হচ্ছে...",
        "no_sessions": "❌ কোনো বৈধ সেশন পাওয়া যায়নি।",
        "request_failed": "❌ অনুরোধ প্রসেসিংকালে ত্রুটি ঘটেছে।",
        "done": "✅ প্রোফাইল সেটআপ সম্পন্ন — {modified} পরিবর্তন | ⏭️ {skipped} স্কিপ | ❌ {failed} ব্যর্থ",
        "failed_report": "❌ সব প্রচেষ্টা ব্যর্থ — {failed}টি ব্যর্থ",
        "btn_total": "মোট",
        "btn_modified": "পরিবর্তিত",
        "btn_skipped": "স্কিপড",
        "btn_failed": "ব্যর্থ",
        "btn_edit_name": "নাম এডিট",
        "btn_edit_username": "ইউজারনেম এডিট",
        "btn_edit_about": "বায়ো এডিট",
        "btn_set_photo": "ছবি যুক্ত",
        "btn_apply": "পরিবর্তন প্রয়োগ ও পরবর্তী",
        "btn_skip": "অ্যাকাউন্ট স্কিপ",
        "photo_pending": "নতুন ছবি নির্বাচিত",
        "photo_none": "নাই",
    },
    "hi": {
        "fetching": "⏳ प्रोफ़ाइल विवरण प्राप्त हो रहे हैं...",
        "applying": "⏳ प्रोफ़ाइल अपडेट लागू हो रहे हैं...",
        "no_sessions": "❌ कोई वैध सेशन नहीं मिला।",
        "request_failed": "❌ अनुरोध प्रक्रिया के दौरान त्रुटि हुई।",
        "done": "✅ प्रोफ़ाइल सेटअप पूर्ण — {modified} संशोधित | ⏭️ {skipped} छूटे | ❌ {failed} विफल",
        "failed_report": "❌ सभी प्रयास विफल — {failed} विफल",
        "btn_total": "कुल",
        "btn_modified": "संशोधित",
        "btn_skipped": "छूटे",
        "btn_failed": "विफल",
        "btn_edit_name": "नाम बदलें",
        "btn_edit_username": "यूज़रनेम बदलें",
        "btn_edit_about": "बायो बदलें",
        "btn_set_photo": "फ़ोटो जोड़ें",
        "btn_apply": "बदलाव लागू करें और आगे",
        "btn_skip": "अकाउंट छोड़ें",
        "photo_pending": "नयी फ़ोटो चुनी गई",
        "photo_none": "कोई नहीं",
    },
    "ur": {
        "fetching": "⏳ پروفائل کی تفصیلات حاصل کی جا رہی ہیں...",
        "applying": "⏳ پروفائل اپ ڈیٹس لاگو کی جا رہی ہیں...",
        "no_sessions": "❌ کوئی بھی درست سیشن نہیں ملا۔",
        "request_failed": "❌ درخواست کے عمل کے دوران ایک خرابی پیش آئی۔",
        "done": "✅ پروفائل سیٹ اپ مکمل — {modified} تبدیل | ⏭️ {skipped} چھوڑے | ❌ {failed} ناکام",
        "failed_report": "❌ تمام کوششیں ناکام — {failed} ناکام",
        "btn_total": "کل",
        "btn_modified": "تبدیل شدہ",
        "btn_skipped": "اسکیپ شدہ",
        "btn_failed": "ناکام",
        "btn_edit_name": "نام ایڈٹ",
        "btn_edit_username": "یوزر نیم ایڈٹ",
        "btn_edit_about": "بائیو ایڈٹ",
        "btn_set_photo": "تصویر منتخب",
        "btn_apply": "تبدیلیاں لاگو اور آگے",
        "btn_skip": "اکاؤنٹ اسکیپ",
        "photo_pending": "نئی تصویر منتخب",
        "photo_none": "کوئی نہیں",
    },
    "ar": {
        "fetching": "⏳ جاري جلب تفاصيل الملف الشخصي...",
        "applying": "⏳ جاري تطبيق التحديثات...",
        "no_sessions": "❌ لم يتم العثور على جلسات صالحة.",
        "request_failed": "❌ حدث خطأ أثناء معالجة الطلب.",
        "done": "✅ اكتمل إعداد الملف الشخصي — {modified} معدل | ⏭️ {skipped} متخطي | ❌ {failed} فشل",
        "failed_report": "❌ فشلت جميع المحاولات — {failed} فشل",
        "btn_total": "الإجمالي",
        "btn_modified": "المعدلة",
        "btn_skipped": "المتخطاة",
        "btn_failed": "الفاشلة",
        "btn_edit_name": "تعديل الاسم",
        "btn_edit_username": "تعديل اسم المستخدم",
        "btn_edit_about": "تعديل السيرة الذاتية",
        "btn_set_photo": "تعيين صورة",
        "btn_apply": "تطبيق والتالي",
        "btn_skip": "تخطي الحساب",
        "photo_pending": "تم تحديد صورة جديدة",
        "photo_none": "لا يوجد",
    },
    "zh": {
        "fetching": "⏳ 正在获取个人资料...",
        "applying": "⏳ 正在应用更新...",
        "no_sessions": "❌ 未找到有效会话。",
        "request_failed": "❌ 处理请求时出错。",
        "done": "✅ 个人资料设置完成 — {modified} 已修改 | ⏭️ {skipped} 已跳过 | ❌ {failed} 失败",
        "failed_report": "❌ 所有尝试均失败 — {failed} 失败",
        "btn_total": "总计",
        "btn_modified": "已修改",
        "btn_skipped": "已跳过",
        "btn_failed": "失败",
        "btn_edit_name": "编辑姓名",
        "btn_edit_username": "编辑用户名",
        "btn_edit_about": "编辑简介",
        "btn_set_photo": "设置头像",
        "btn_apply": "应用更改并继续",
        "btn_skip": "跳过此账号",
        "photo_pending": "已选择新头像",
        "photo_none": "无",
    },
}

ENTER_CURRENT_2FA_PROMPT = {
    "en": (
        "🔐 <b>2FA</b>\n\n"
        "📦 Found <b>{count}</b> session(s)\n\n"
        "🔑 Enter the <b>current 2FA password</b>:"
    ),
    "bn": (
        "🔐 <b>২FA</b>\n\n"
        "📦 <b>{count}</b>টি সেশন পাওয়া গেছে\n\n"
        "🔑 <b>বর্তমান ২FA পাসওয়ার্ড</b> লিখুন:"
    ),
    "hi": (
        "🔐 <b>2FA</b>\n\n"
        "📦 <b>{count}</b> सेशन मिले\n\n"
        "🔑 <b>वर्तमान 2FA पासवर्ड</b> दर्ज करें:"
    ),
    "ur": (
        "🔐 <b>2FA</b>\n\n"
        "📦 <b>{count}</b> سیشنز ملے\n\n"
        "🔑 <b>موجودہ 2FA پاس ورڈ</b> درج کریں:"
    ),
    "ar": (
        "🔐 <b>2FA</b>\n\n"
        "📦 تم العثور على <b>{count}</b> جلسة\n\n"
        "🔑 أدخل <b>كلمة سر 2FA الحالية</b>:"
    ),
    "zh": (
        "🔐 <b>2FA</b>\n\n"
        "📦 找到 <b>{count}</b> 个会话\n\n"
        "🔑 输入<b>当前 2FA 密码</b>："
    ),
}

ENTER_NEW_2FA_PROMPT = {
    "en": ("🔐 <b>New 2FA Password</b>\n\nNow enter the <b>new password</b>:"),
    "bn": ("🔐 <b>নতুন ২FA পাসওয়ার্ড</b>\n\nএখন <b>নতুন পাসওয়ার্ড</b> লিখুন:"),
    "hi": ("🔐 <b>नया 2FA पासवर्ड</b>\n\nअब <b>नया पासवर्ड</b> दर्ज करें:"),
    "ur": ("🔐 <b>نیا 2FA پاس ورڈ</b>\n\nاب <b>نیا پاس ورڈ</b> درج کریں:"),
    "ar": ("🔐 <b>كلمة سر 2FA جديدة</b>\n\nالآن أدخل <b>كلمة السر الجديدة</b>:"),
    "zh": ("🔐 <b>新 2FA 密码</b>\n\n现在输入<b>新密码</b>："),
}

TWO_FACTOR_ACCOUNT_CURRENT_PROMPT = {
    "en": (
        "🔐 <b>Account {current}/{total}</b>\n"
        "📄 <code>{session}</code>\n\n"
        "🔑 Enter this account's <b>current 2FA password</b>:"
    ),
    "bn": (
        "🔐 <b>অ্যাকাউন্ট {current}/{total}</b>\n📄 <code>{session}</code>\n\n"
        "🔑 এই অ্যাকাউন্টের <b>বর্তমান ২FA পাসওয়ার্ড</b> লিখুন:"
    ),
    "hi": (
        "🔐 <b>खाता {current}/{total}</b>\n📄 <code>{session}</code>\n\n"
        "🔑 इस खाते का <b>वर्तमान 2FA पासवर्ड</b> दर्ज करें:"
    ),
    "ur": (
        "🔐 <b>اکاؤنٹ {current}/{total}</b>\n📄 <code>{session}</code>\n\n"
        "🔑 اس اکاؤنٹ کا <b>موجودہ 2FA پاس ورڈ</b> درج کریں:"
    ),
    "ar": (
        "🔐 <b>الحساب {current}/{total}</b>\n📄 <code>{session}</code>\n\n"
        "🔑 أدخل <b>كلمة سر 2FA الحالية</b> لهذا الحساب:"
    ),
    "zh": (
        "🔐 <b>账号 {current}/{total}</b>\n📄 <code>{session}</code>\n\n"
        "🔑 输入此账号的<b>当前 2FA 密码</b>："
    ),
}

TWO_FACTOR_ACCOUNT_NEW_PROMPT = {
    "en": (
        "🔐 <b>Account {current}/{total}</b>\n"
        "📄 <code>{session}</code>\n\n"
        "🆕 Enter the <b>new 2FA password</b> for this account:"
    ),
    "bn": (
        "🔐 <b>অ্যাকাউন্ট {current}/{total}</b>\n📄 <code>{session}</code>\n\n"
        "🆕 এই অ্যাকাউন্টের <b>নতুন ২FA পাসওয়ার্ড</b> লিখুন:"
    ),
    "hi": (
        "🔐 <b>खाता {current}/{total}</b>\n📄 <code>{session}</code>\n\n"
        "🆕 इस खाते का <b>नया 2FA पासवर्ड</b> दर्ज करें:"
    ),
    "ur": (
        "🔐 <b>اکاؤنٹ {current}/{total}</b>\n📄 <code>{session}</code>\n\n"
        "🆕 اس اکاؤنٹ کا <b>نیا 2FA پاس ورڈ</b> درج کریں:"
    ),
    "ar": (
        "🔐 <b>الحساب {current}/{total}</b>\n📄 <code>{session}</code>\n\n"
        "🆕 أدخل <b>كلمة سر 2FA الجديدة</b> لهذا الحساب:"
    ),
    "zh": (
        "🔐 <b>账号 {current}/{total}</b>\n📄 <code>{session}</code>\n\n"
        "🆕 输入此账号的<b>新 2FA 密码</b>："
    ),
}

TWO_FACTOR_MESSAGES = {
    "en": {
        "processing": "⏳ Processing 2FA request...",
        "no_sessions": "❌ No valid sessions found.",
        "password_required": "❌ Enter a non-empty 2FA password.",
        "request_failed": "❌ The 2FA request could not be completed.",
        "done_change_disable": "✅ Done — {success} success | ❌ {failed} failed",
        "done_reset": "🔄 Done — ✅ {success} | ⏳ {pending} pending | ❌ {failed}",
        "btn_total": "Total",
        "btn_success": "Success",
        "btn_pending": "Pending",
        "btn_failed": "Failed",
        "cancelled": "🚫 Operation cancelled.",
    },
    "bn": {
        "processing": "⏳ ২FA প্রসেসিং হচ্ছে...",
        "no_sessions": "❌ কোনো বৈধ সেশন পাওয়া যায়নি।",
        "password_required": "❌ একটি খালি নয় এমন ২FA পাসওয়ার্ড লিখুন।",
        "request_failed": "❌ ২FA অনুরোধটি সম্পন্ন করা যায়নি।",
        "done_change_disable": "✅ সম্পন্ন — {success}টি সফল | ❌ {failed}টি ব্যর্থ",
        "done_reset": "🔄 সম্পন্ন — ✅ {success} | ⏳ {pending} অপেক্ষমাণ | ❌ {failed}",
        "btn_total": "মোট",
        "btn_success": "সফল",
        "btn_pending": "অপেক্ষমাণ",
        "btn_failed": "ব্যর্থ",
        "cancelled": "🚫 কার্যক্রম বাতিল হয়েছে।",
    },
    "hi": {
        "processing": "⏳ 2FA प्रक्रिया जारी है...",
        "no_sessions": "❌ कोई वैध सेशन नहीं मिला।",
        "password_required": "❌ एक गैर-रिक्त 2FA पासवर्ड दर्ज करें।",
        "request_failed": "❌ 2FA अनुरोध पूरा नहीं किया जा सका।",
        "done_change_disable": "✅ पूर्ण — {success} सफल | ❌ {failed} विफल",
        "done_reset": "🔄 पूर्ण — ✅ {success} | ⏳ {pending} लंबित | ❌ {failed}",
        "btn_total": "कुल",
        "btn_success": "सफल",
        "btn_pending": "लंबित",
        "btn_failed": "विफल",
        "cancelled": "🚫 कार्य रद्द कर दिया गया।",
    },
    "ur": {
        "processing": "⏳ 2FA عمل جاری ہے...",
        "no_sessions": "❌ کوئی بھی درست سیشن نہیں ملا۔",
        "password_required": "❌ غیر خالی 2FA پاس ورڈ درج کریں۔",
        "request_failed": "❌ 2FA درخواست مکمل نہیں ہو سکی۔",
        "done_change_disable": "✅ مکمل — {success} کامیاب | ❌ {failed} ناکام",
        "done_reset": "🔄 مکمل — ✅ {success} | ⏳ {pending} زیرِ انتظار | ❌ {failed}",
        "btn_total": "کل",
        "btn_success": "کامیاب",
        "btn_pending": "زیرِ انتظار",
        "btn_failed": "ناکام",
        "cancelled": "🚫 کار منسوخ کر دیا گیا۔",
    },
    "ar": {
        "processing": "⏳ جاري معالجة 2FA...",
        "no_sessions": "❌ لم يتم العثور على جلسات صالحة.",
        "password_required": "❌ أدخل كلمة سر 2FA غير فارغة.",
        "request_failed": "❌ تعذر إكمال طلب 2FA.",
        "done_change_disable": "✅ اكتمل — {success} نجاح | ❌ {failed} فشل",
        "done_reset": "🔄 اكتمل — ✅ {success} | ⏳ {pending} قيد الانتظار | ❌ {failed}",
        "btn_total": "الإجمالي",
        "btn_success": "الناجحة",
        "btn_pending": "قيد الانتظار",
        "btn_failed": "الفاشلة",
        "cancelled": "🚫 تم إلغاء العملية.",
    },
    "zh": {
        "processing": "⏳ 正在处理 2FA...",
        "no_sessions": "❌ 未找到有效会话。",
        "password_required": "❌ 请输入非空的 2FA 密码。",
        "request_failed": "❌ 无法完成 2FA 请求。",
        "done_change_disable": "✅ 完成 — {success} 成功 | ❌ {failed} 失败",
        "done_reset": "🔄 完成 — ✅ {success} | ⏳ {pending} 等待中 | ❌ {failed}",
        "btn_total": "总计",
        "btn_success": "成功",
        "btn_pending": "等待中",
        "btn_failed": "失败",
        "cancelled": "🚫 操作已取消。",
    },
}

TWO_FACTOR_ERRORS = {
    "en": {
        "fresh_authorization_forbidden": "Reset is blocked for a newly authorized session.",
        "recovery_email_unavailable": "No recovery email is configured for this account.",
        "password_too_fresh": "The 2FA password is too new; Telegram requires waiting.",
        "reset_request_missing": "No active 2FA reset request exists.",
        "too_many_attempts": "Too many reset attempts; try again later.",
        "flood_wait": "Telegram rate-limited the reset request; try again later.",
        "reset_failed_wait": "Telegram requires waiting before another reset attempt.",
        "unauthorized_session": "The session is not authorized.",
        "invalid_session": "The session file is invalid.",
        "api_credentials_or_network_failed": "The API credentials or network connection failed.",
        "telethon_unavailable": "The Telegram client library is unavailable.",
        "unexpected_reset_response": "Telegram returned an unexpected reset response.",
        "telegram_rejected_reset": "Telegram rejected the 2FA reset request.",
        "internal_reset_error": "An internal error occurred while resetting 2FA.",
    },
    "bn": {
        "fresh_authorization_forbidden": "নতুন অনুমোদিত সেশনের জন্য রিসেট বন্ধ রয়েছে।",
        "recovery_email_unavailable": "এই অ্যাকাউন্টে রিকভারি ইমেইল সেট করা নেই।",
        "password_too_fresh": "2FA পাসওয়ার্ডটি খুব নতুন; অপেক্ষা করতে হবে।",
        "reset_request_missing": "কোনো সক্রিয় 2FA রিসেট অনুরোধ নেই।",
        "too_many_attempts": "অনেকবার চেষ্টা করা হয়েছে; পরে আবার চেষ্টা করুন।",
        "flood_wait": "Telegram অনুরোধটি সীমিত করেছে; পরে আবার চেষ্টা করুন।",
        "reset_failed_wait": "আবার রিসেট করার আগে অপেক্ষা করতে হবে।",
        "unauthorized_session": "সেশনটি অনুমোদিত নয়।",
        "invalid_session": "সেশন ফাইলটি অবৈধ।",
        "api_credentials_or_network_failed": "API তথ্য বা নেটওয়ার্ক সংযোগ ব্যর্থ হয়েছে।",
        "telethon_unavailable": "Telegram ক্লায়েন্ট লাইব্রেরি উপলভ্য নয়।",
        "unexpected_reset_response": "Telegram অপ্রত্যাশিত রিসেট উত্তর দিয়েছে।",
        "telegram_rejected_reset": "Telegram 2FA রিসেট অনুরোধ প্রত্যাখ্যান করেছে।",
        "internal_reset_error": "2FA রিসেট করার সময় অভ্যন্তরীণ ত্রুটি ঘটেছে।",
    },
    "hi": {
        "fresh_authorization_forbidden": "नए अधिकृत सेशन के लिए रीसेट अवरुद्ध है।",
        "recovery_email_unavailable": "इस खाते में रिकवरी ईमेल सेट नहीं है।",
        "password_too_fresh": "2FA पासवर्ड बहुत नया है; प्रतीक्षा करना आवश्यक है।",
        "reset_request_missing": "कोई सक्रिय 2FA रीसेट अनुरोध मौजूद नहीं है।",
        "too_many_attempts": "बहुत अधिक प्रयास हुए; बाद में फिर प्रयास करें।",
        "flood_wait": "Telegram ने अनुरोध सीमित किया है; बाद में प्रयास करें।",
        "reset_failed_wait": "दोबारा रीसेट करने से पहले प्रतीक्षा करनी होगी।",
        "unauthorized_session": "सेशन अधिकृत नहीं है।",
        "invalid_session": "सेशन फ़ाइल अमान्य है।",
        "api_credentials_or_network_failed": "API क्रेडेंशियल या नेटवर्क कनेक्शन विफल हुआ।",
        "telethon_unavailable": "Telegram क्लाइंट लाइब्रेरी उपलब्ध नहीं है।",
        "unexpected_reset_response": "Telegram ने अप्रत्याशित रीसेट उत्तर दिया।",
        "telegram_rejected_reset": "Telegram ने 2FA रीसेट अनुरोध अस्वीकार किया।",
        "internal_reset_error": "2FA रीसेट करते समय आंतरिक त्रुटि हुई।",
    },
    "ur": {
        "fresh_authorization_forbidden": "نئے مجاز سیشن کے لیے ری سیٹ ممنوع ہے۔",
        "recovery_email_unavailable": "اس اکاؤنٹ میں ریکوری ای میل موجود نہیں۔",
        "password_too_fresh": "2FA پاس ورڈ بہت نیا ہے؛ انتظار کرنا ہوگا۔",
        "reset_request_missing": "کوئی فعال 2FA ری سیٹ درخواست موجود نہیں۔",
        "too_many_attempts": "بہت زیادہ کوششیں ہوئیں؛ بعد میں دوبارہ کوشش کریں۔",
        "flood_wait": "Telegram نے درخواست محدود کر دی؛ بعد میں کوشش کریں۔",
        "reset_failed_wait": "دوبارہ ری سیٹ سے پہلے انتظار ضروری ہے۔",
        "unauthorized_session": "سیشن مجاز نہیں ہے۔",
        "invalid_session": "سیشن فائل درست نہیں ہے۔",
        "api_credentials_or_network_failed": "API معلومات یا نیٹ ورک کنکشن ناکام ہوا۔",
        "telethon_unavailable": "Telegram کلائنٹ لائبریری دستیاب نہیں۔",
        "unexpected_reset_response": "Telegram نے غیر متوقع جواب دیا۔",
        "telegram_rejected_reset": "Telegram نے 2FA ری سیٹ درخواست مسترد کی۔",
        "internal_reset_error": "2FA ری سیٹ کے دوران اندرونی خرابی ہوئی۔",
    },
    "ar": {
        "fresh_authorization_forbidden": "إعادة الضبط محظورة للجلسة المصرح بها حديثًا.",
        "recovery_email_unavailable": "لا يوجد بريد استرداد مضبوط لهذا الحساب.",
        "password_too_fresh": "كلمة سر 2FA حديثة جدًا؛ يجب الانتظار.",
        "reset_request_missing": "لا يوجد طلب نشط لإعادة ضبط 2FA.",
        "too_many_attempts": "محاولات كثيرة؛ حاول لاحقًا.",
        "flood_wait": "قيّد Telegram الطلب؛ حاول لاحقًا.",
        "reset_failed_wait": "يجب الانتظار قبل محاولة إعادة الضبط مرة أخرى.",
        "unauthorized_session": "الجلسة غير مصرح بها.",
        "invalid_session": "ملف الجلسة غير صالح.",
        "api_credentials_or_network_failed": "فشلت بيانات API أو شبكة الاتصال.",
        "telethon_unavailable": "مكتبة عميل Telegram غير متاحة.",
        "unexpected_reset_response": "أعاد Telegram استجابة غير متوقعة.",
        "telegram_rejected_reset": "رفض Telegram طلب إعادة ضبط 2FA.",
        "internal_reset_error": "حدث خطأ داخلي أثناء إعادة ضبط 2FA.",
    },
    "zh": {
        "fresh_authorization_forbidden": "新授权的会话暂时禁止重置。",
        "recovery_email_unavailable": "该账户未设置恢复邮箱。",
        "password_too_fresh": "2FA 密码设置时间太短，需要等待。",
        "reset_request_missing": "不存在有效的 2FA 重置请求。",
        "too_many_attempts": "尝试次数过多，请稍后再试。",
        "flood_wait": "Telegram 已限制该请求，请稍后再试。",
        "reset_failed_wait": "再次尝试重置前需要等待。",
        "unauthorized_session": "会话未授权。",
        "invalid_session": "会话文件无效。",
        "api_credentials_or_network_failed": "API 凭据或网络连接失败。",
        "telethon_unavailable": "Telegram 客户端库不可用。",
        "unexpected_reset_response": "Telegram 返回了意外的重置响应。",
        "telegram_rejected_reset": "Telegram 拒绝了 2FA 重置请求。",
        "internal_reset_error": "重置 2FA 时发生内部错误。",
    },
}

DIRECT_FILE_MESSAGES = {
    "en": {
        "expired": "⌛ File expired. Please send the file again.",
        "invalid_action": "❌ This action is not available for the received file.",
    },
    "bn": {
        "expired": "⌛ ফাইলটির সময় শেষ হয়েছে। অনুগ্রহ করে আবার পাঠান।",
        "invalid_action": "❌ প্রাপ্ত ফাইলের জন্য এই কাজটি উপলভ্য নয়।",
    },
    "hi": {
        "expired": "⌛ फ़ाइल की समय-सीमा समाप्त हो गई। कृपया इसे फिर भेजें।",
        "invalid_action": "❌ प्राप्त फ़ाइल के लिए यह कार्रवाई उपलब्ध नहीं है।",
    },
    "ur": {
        "expired": "⌛ فائل کی مدت ختم ہو گئی۔ براہ کرم دوبارہ بھیجیں۔",
        "invalid_action": "❌ موصول شدہ فائل کے لیے یہ کارروائی دستیاب نہیں۔",
    },
    "ar": {
        "expired": "⌛ انتهت صلاحية الملف. يرجى إرساله مرة أخرى.",
        "invalid_action": "❌ هذا الإجراء غير متاح للملف المستلم.",
    },
    "zh": {
        "expired": "⌛ 文件已过期，请重新发送。",
        "invalid_action": "❌ 此操作不适用于收到的文件。",
    },
}

SPLIT_CHUNK_PROMPTS = {
    "en": "📏 Enter the desired chunk size in MB (e.g. 5):",
    "bn": "📏 মেগাবাইটে (MB) টুকরোর সাইজ লিখুন (যেমন ৫):",
    "hi": "📏 MB में वांछित भाग का आकार दर्ज करें (जैसे 5):",
    "ur": "📏 MB میں مطلوبہ حصے کا سائز درج کریں (مثلاً 5):",
    "ar": "📏 أدخل حجم الجزء المطلوب بالميجابايت (مثال: 5):",
    "zh": "📏 输入期望的分块大小（MB，例如 5）：",
}

SPLIT_ERRORS = {
    "en": {
        "invalid_number": (
            "❌ Invalid number. Please enter a positive integer for chunk size in MB."
        ),
        "file_not_found": "❌ Temporary file not found. Please start over.",
        "max_chunks_exceeded": (
            "❌ A maximum of 20 split chunks is allowed. Increase chunk size."
        ),
        "integer_required": (
            "❌ Please send a valid number representing chunk size in MB."
        ),
        "manifest_caption": "📄 Manifest file for split chunks",
    },
    "bn": {
        "invalid_number": ("❌ অবৈধ সংখ্যা। অনুগ্রহ করে মেগাবাইটে একটি ধনাত্মক পূর্ণসংখ্যা লিখুন।"),
        "file_not_found": ("❌ সাময়িক ফাইল পাওয়া যায়নি। দয়া করে আবার শুরু করুন।"),
        "max_chunks_exceeded": ("❌ সর্বোচ্চ ২০টি টুকরো তৈরি সম্ভব। টুকরোর সাইজ বাড়ান।"),
        "integer_required": ("❌ মেগাবাইটে টুকরোর সাইজ নির্দেশ করে এমন একটি বৈধ সংখ্যা লিখুন।"),
        "manifest_caption": "📄 বিভাজিত টুকরোগুলির জন্য ম্যানিফেস্ট ফাইল",
    },
    "hi": {
        "invalid_number": ("❌ अमान्य संख्या। कृपया MB में एक धनात्मक पूर्णांक दर्ज करें।"),
        "file_not_found": "❌ अस्थायी फ़ाइल नहीं मिली। कृपया पुनः आरंभ करें।",
        "max_chunks_exceeded": ("❌ अधिकतम 20 भागों की अनुमति है। भाग का आकार बढ़ाएं।"),
        "integer_required": ("❌ कृपया MB में भाग का आकार दर्शाने वाली एक मान्य संख्या भेजें।"),
        "manifest_caption": "📄 विभाजित भागों के लिए मेनिफेस्ट फ़ाइल",
    },
    "ur": {
        "invalid_number": ("❌ غلط نمبر۔ برائے مہربانی MB میں مثبت عدد درج کریں۔"),
        "file_not_found": ("❌ عارضی فائل نہیں ملی۔ برائے مہربانی دوبارہ شروع کریں۔"),
        "max_chunks_exceeded": (
            "❌ زیادہ سے زیادہ 20 ٹکڑوں کی اجازت ہے۔ سائز بڑھائیں۔"
        ),
        "integer_required": (
            "❌ برائے مہربانی MB میں سائز ظاہر کرنے والا درست نمبر بھیجیں۔"
        ),
        "manifest_caption": "📄 تقسیم شدہ ٹکڑوں کے لیے مینی فیسٹ فائل",
    },
    "ar": {
        "invalid_number": (
            "❌ عدد غير صالح. يرجى إدخال عدد صحيح موجب لحجم الجزء بالميجابايت."
        ),
        "file_not_found": ("❌ لم يتم العثور على الملف المؤقت. يرجى البدء من جديد."),
        "max_chunks_exceeded": ("❌ يُسمح بحد أقصى 20 جزءاً. يرجى زيادة حجم الجزء."),
        "integer_required": ("❌ يرجى إرسال رقم صالح يمثل حجم الجزء بالميجابايت."),
        "manifest_caption": "📄 ملف بيان (Manifest) للأجزاء المقسمة",
    },
    "zh": {
        "invalid_number": "❌ 数字无效。请输入以 MB 为单位的正整数。",
        "file_not_found": "❌ 未找到临时文件。请重新开始。",
        "max_chunks_exceeded": ("❌ 最多允许 20 个分割块。请增加块大小。"),
        "integer_required": "❌ 请发送一个有效的数字作为分块大小（MB）。",
        "manifest_caption": "📄 分割块的清单文件",
    },
}

ANALYSIS_MESSAGES = {
    "en": {
        "analyzing": "⏳ Analyzing file...",
        "completed": "✅ Analysis completed",
        "name": "Name",
        "type": "Type",
        "size": "Size",
        "zip_members": "ZIP Members",
        "uncompressed_size": "Uncompressed Size",
        "internal_error": "❌ Internal error occurred during processing.",
    },
    "bn": {
        "analyzing": "⏳ ফাইল বিশ্লেষণ করা হচ্ছে...",
        "completed": "✅ বিশ্লেষণ সম্পূর্ণ হয়েছে",
        "name": "নাম",
        "type": "ধরন",
        "size": "আকার",
        "zip_members": "ZIP সদস্য",
        "uncompressed_size": "আনকম্প্রেসড আকার",
        "internal_error": ("❌ প্রক্রিয়াকরণের সময় একটি অভ্যন্তরীণ ত্রুটি ঘটেছে।"),
    },
    "hi": {
        "analyzing": "⏳ फ़ाइल का विश्लेषण हो रहा है...",
        "completed": "✅ विश्लेषण पूरा हुआ",
        "name": "नाम",
        "type": "प्रकार",
        "size": "आकार",
        "zip_members": "ZIP सदस्यों",
        "uncompressed_size": "अनकंप्रेस्ड आकार",
        "internal_error": "❌ प्रसंस्करण के दौरान आंतरिक त्रुटि हुई।",
    },
    "ur": {
        "analyzing": "⏳ فائل کا تجزیہ ہو رہا ہے...",
        "completed": "✅ تجزیہ مکمل ہو گیا",
        "name": "نام",
        "type": "قسم",
        "size": "سائز",
        "zip_members": "ZIP ممبرز",
        "uncompressed_size": "غیر کمپریسڈ سائز",
        "internal_error": ("❌ پروسیسنگ کے دوران اندرونی خرابی پیش آ گئی۔"),
    },
    "ar": {
        "analyzing": "⏳ جاري تحليل الملف...",
        "completed": "✅ اكتمل التحليل",
        "name": "الاسم",
        "type": "النوع",
        "size": "الحجم",
        "zip_members": "أعضاء ZIP",
        "uncompressed_size": "الحجم غير المضغوط",
        "internal_error": "❌ حدث خطأ داخلي أثناء المعالجة.",
    },
    "zh": {
        "analyzing": "⏳ 正在分析文件...",
        "completed": "✅ 分析完成",
        "name": "名称",
        "type": "类型",
        "size": "大小",
        "zip_members": "ZIP 成员",
        "uncompressed_size": "解压后大小",
        "internal_error": "❌ 处理过程中发生内部错误。",
    },
}

SPLIT_MESSAGES = {
    "en": {
        "choose_type": "✂️ <b>Choose file split type</b>\n\n📦 Found <b>{count}</b> sessions",
        "btn_country": "Split by Country",
        "btn_quantity": "Split by Quantity",
        "btn_cancel": "Cancel",
        "quantity_prompt": (
            "🔢 <b>Split by Quantity</b>\n\n"
            "Enter number of sessions per zip:\n\nExample: <code>10</code>"
        ),
        "splitting": "⏳ Splitting sessions...",
        "country_completed": (
            "✅ <b>Split complete!</b>\n\n"
            "📦 Total: <code>{total}</code>\n"
            "🌍 Countries: <code>{groups}</code>"
        ),
        "quantity_completed": (
            "✅ <b>Split complete!</b>\n\n"
            "📦 Total: <code>{total}</code> sessions → "
            "<code>{groups}</code> parts"
        ),
        "caption_country": "{flag} {label} — {count} sessions",
        "caption_part": "📦 {label} — {count} sessions",
        "no_sessions": "❌ No valid session files were found.",
        "invalid_quantity": "❌ Send a positive whole number.",
        "internal_error": "❌ Internal error occurred during splitting.",
        "btn_total": "Total",
        "btn_split": "Split",
        "btn_failed": "Failed",
    },
    "bn": {
        "choose_type": "✂️ <b>ফাইল বিভাজনের ধরন বেছে নিন</b>\n\n📦 <b>{count}</b>টি সেশন পাওয়া গেছে",
        "btn_country": "দেশ অনুযায়ী বিভক্ত করুন",
        "btn_quantity": "সংখ্যা অনুযায়ী বিভক্ত করুন",
        "btn_cancel": "বাতিল",
        "quantity_prompt": "🔢 <b>সংখ্যা অনুযায়ী বিভক্ত করুন</b>\n\nপ্রতি ZIP-এ সেশনের সংখ্যা লিখুন:\n\nউদাহরণ: <code>10</code>",
        "splitting": "⏳ সেশন বিভাজন করা হচ্ছে...",
        "country_completed": "✅ <b>বিভাজন সম্পন্ন!</b>\n\n📦 মোট: <code>{total}</code>\n🌍 দেশ: <code>{groups}</code>",
        "quantity_completed": "✅ <b>বিভাজন সম্পন্ন!</b>\n\n📦 মোট: <code>{total}</code> সেশন → <code>{groups}</code> অংশ",
        "caption_country": "{flag} {label} — {count} সেশন",
        "caption_part": "📦 {label} — {count} সেশন",
        "no_sessions": "❌ কোনো বৈধ সেশন ফাইল পাওয়া যায়নি।",
        "invalid_quantity": "❌ একটি ধনাত্মক পূর্ণসংখ্যা পাঠান।",
        "internal_error": "❌ ভাগ করার সময় অভ্যন্তরীণ ত্রুটি ঘটেছে।",
        "btn_total": "মোট",
        "btn_split": "বিভক্ত",
        "btn_failed": "ব্যর্থ",
    },
    "hi": {
        "choose_type": "✂️ <b>फ़ाइल विभाजन प्रकार चुनें</b>\n\n📦 <b>{count}</b> सेशन मिले",
        "btn_country": "देश के अनुसार विभाजित करें",
        "btn_quantity": "संख्या के अनुसार विभाजित करें",
        "btn_cancel": "रद्द करें",
        "quantity_prompt": "🔢 <b>संख्या के अनुसार विभाजन</b>\n\nप्रति ZIP सेशन की संख्या दर्ज करें:\n\nउदाहरण: <code>10</code>",
        "splitting": "⏳ सेशन विभाजित किए जा रहे हैं...",
        "country_completed": "✅ <b>विभाजन पूरा!</b>\n\n📦 कुल: <code>{total}</code>\n🌍 देश: <code>{groups}</code>",
        "quantity_completed": "✅ <b>विभाजन पूरा!</b>\n\n📦 कुल: <code>{total}</code> सेशन → <code>{groups}</code> भाग",
        "caption_country": "{flag} {label} — {count} सेशन",
        "caption_part": "📦 {label} — {count} सेशन",
        "no_sessions": "❌ कोई वैध सेशन फ़ाइल नहीं मिली।",
        "invalid_quantity": "❌ एक धनात्मक पूर्णांक भेजें।",
        "internal_error": "❌ विभाजन के दौरान आंतरिक त्रुटि हुई।",
        "btn_total": "कुल",
        "btn_split": "विभाजित",
        "btn_failed": "विफल",
    },
    "ur": {
        "choose_type": "✂️ <b>فائل تقسیم کی قسم منتخب کریں</b>\n\n📦 <b>{count}</b> سیشن ملے",
        "btn_country": "ملک کے لحاظ سے تقسیم",
        "btn_quantity": "تعداد کے لحاظ سے تقسیم",
        "btn_cancel": "منسوخ کریں",
        "quantity_prompt": "🔢 <b>تعداد کے لحاظ سے تقسیم</b>\n\nہر ZIP میں سیشن کی تعداد درج کریں:\n\nمثال: <code>10</code>",
        "splitting": "⏳ سیشن تقسیم ہو رہے ہیں...",
        "country_completed": "✅ <b>تقسیم مکمل!</b>\n\n📦 کل: <code>{total}</code>\n🌍 ممالک: <code>{groups}</code>",
        "quantity_completed": "✅ <b>تقسیم مکمل!</b>\n\n📦 کل: <code>{total}</code> سیشن → <code>{groups}</code> حصے",
        "caption_country": "{flag} {label} — {count} سیشن",
        "caption_part": "📦 {label} — {count} سیشن",
        "no_sessions": "❌ کوئی درست سیشن فائل نہیں ملی۔",
        "invalid_quantity": "❌ مثبت صحیح عدد بھیجیں۔",
        "internal_error": "❌ تقسیم کے دوران اندرونی خرابی پیش آ گئی۔",
        "btn_total": "کل",
        "btn_split": "تقسیم",
        "btn_failed": "ناکام",
    },
    "ar": {
        "choose_type": "✂️ <b>اختر نوع تقسيم الملف</b>\n\n📦 تم العثور على <b>{count}</b> جلسة",
        "btn_country": "تقسيم حسب الدولة",
        "btn_quantity": "تقسيم حسب العدد",
        "btn_cancel": "إلغاء",
        "quantity_prompt": "🔢 <b>تقسيم حسب العدد</b>\n\nأدخل عدد الجلسات لكل ZIP:\n\nمثال: <code>10</code>",
        "splitting": "⏳ جارٍ تقسيم الجلسات...",
        "country_completed": "✅ <b>اكتمل التقسيم!</b>\n\n📦 الإجمالي: <code>{total}</code>\n🌍 الدول: <code>{groups}</code>",
        "quantity_completed": "✅ <b>اكتمل التقسيم!</b>\n\n📦 الإجمالي: <code>{total}</code> جلسة ← <code>{groups}</code> أجزاء",
        "caption_country": "{flag} {label} — {count} جلسة",
        "caption_part": "📦 {label} — {count} جلسة",
        "no_sessions": "❌ لم يتم العثور على ملفات جلسة صالحة.",
        "invalid_quantity": "❌ أرسل عدداً صحيحاً موجباً.",
        "internal_error": "❌ حدث خطأ داخلي أثناء التقسيم.",
        "btn_total": "الإجمالي",
        "btn_split": "المقسمة",
        "btn_failed": "الفاشلة",
    },
    "zh": {
        "choose_type": "✂️ <b>选择文件分割类型</b>\n\n📦 找到 <b>{count}</b 个会话",
        "btn_country": "按国家分割",
        "btn_quantity": "按数量分割",
        "btn_cancel": "取消",
        "quantity_prompt": "🔢 <b>按数量分割</b>\n\n请输入每个 ZIP 的会话数量：\n\n示例：<code>10</code>",
        "splitting": "⏳ 正在分割会话...",
        "country_completed": "✅ <b>分割完成！</b>\n\n📦 总计：<code>{total}</code>\n🌍 国家：<code>{groups}</code>",
        "quantity_completed": "✅ <b>分割完成！</b>\n\n📦 总计：<code>{total}</code> 个会话 → <code>{groups}</code> 个部分",
        "caption_country": "{flag} {label} — {count} 个会话",
        "caption_part": "📦 {label} — {count} 个会话",
        "no_sessions": "❌ 未找到有效的会话文件。",
        "invalid_quantity": "❌ 请发送正整数。",
        "internal_error": "❌ 拆分过程中发生内部错误。",
        "btn_total": "总计",
        "btn_split": "已分割",
        "btn_failed": "失败",
    },
}

READ_OTP_PROMPTS = {
    "en": (
        "📨 <b>Read OTP</b>\n\nSend a <code>.session</code> file or <code>.zip</code>."
    ),
    "bn": (
        "📨 <b>OTP পড়ুন</b>\n\nএকটি <code>.session</code> ফাইল অথবা <code>.zip</code> পাঠান।"
    ),
    "hi": (
        "📨 <b>OTP पढ़ें</b>\n\nएक <code>.session</code> फ़ाइल या <code>.zip</code> भेजें।"
    ),
    "ur": (
        "📨 <b>OTP پڑھیں</b>\n\nایک <code>.session</code> فائل یا"
        " <code>.zip</code> بھیجیں۔"
    ),
    "ar": (
        "📨 <b>قراءة OTP</b>\n\nأرسل ملف <code>.session</code> أو <code>.zip</code>."
    ),
    "zh": (
        "📨 <b>读取 OTP</b>\n\n请发送 <code>.session</code> 文件或 <code>.zip</code>。"
    ),
}

READ_OTP_MESSAGES = {
    "en": {
        "account_header": (
            "👤 <b>Account {current}/{total}</b>\n\n📁 Session:"
            " <code>{session_id}</code>\n⬇️ Press <b>Check</b> to read OTPs."
        ),
        "account_details": (
            "👤 <b>Account {current}/{total}</b>\n\n👤 User: <b>{user}</b>\n📱"
            " Number: <code>{phone}</code>\n🔖 Username: <b>{username}</b>\n\n🧩"
            " <b>OTP Codes (Last 2 Hours):</b>\n{otp_content}"
        ),
        "account_details_again": (
            "👤 <b>Account {current}/{total}</b>\n\n👤 User: <b>{user}</b>\n📱"
            " Number: <code>{phone}</code>\n🔖 Username: <b>{username}</b>\n\n🧩"
            " <b>OTP Codes (Last 2 Hours):</b>\n{otp_content}"
        ),
        "no_otps_2h": "<i>No OTP codes found in the last 2 hours.</i>",
        "no_otps_since": "<i>No OTP codes found in the last 2 hours.</i>",
        "logged_out": "🚪 Session logged out successfully.",
        "skipped_one": "⏭️ <i>Skipped {count}.</i>",
        "no_sessions": "No valid .session files were found.",
        "all_processed": "✅ <b>All {total} accounts processed!</b>",
        "btn_check": "✅ Check",
        "btn_skip": "⏭️ Skip",
        "btn_check_again": "🔄 Check Again",
        "btn_logout": "🚪 Logout",
        "error_banned": (
            "🚫 <b>Account banned/deactivated.</b>\n\n📁 Session:"
            " <code>{session_id}</code>\n"
            "This account has been banned or deactivated by Telegram, so its"
            " OTP messages can no longer be read. Skip it and continue."
        ),
        "error_2fa": (
            "🔐 <b>Two-step verification required.</b>\n\n📁 Session:"
            " <code>{session_id}</code>\n"
            "Login is protected by a two-step password; OTPs cannot be read without it."
        ),
        "error_invalid": (
            "❌ <b>Invalid/corrupt session.</b>\n\n📁 Session:"
            " <code>{session_id}</code>\n"
            "The session database is corrupt; OTPs cannot be read."
        ),
        "error_inconclusive": (
            "⚠️ <b>Could not read OTPs.</b>\n\n📁 Session:"
            " <code>{session_id}</code>\n"
            "A connection error occurred (network timeout or credential problem)."
        ),
        "no_api_credentials": (
            "⚠️ <b>Cannot read OTPs.</b>\n\n📁 Session:"
            " <code>{session_id}</code>\n"
            "No API credentials are configured on this bot, so OTP messages"
            " cannot be read from Telegram."
        ),
        "logout_failed": (
            "🚪 <b>Logout failed.</b>\n\n📁 Session: <code>{session_id}</code>\n"
            "The session could not be logged out (no API credentials,"
            " unauthorized session, or a connection error)."
        ),
    },
    "bn": {
        "account_header": (
            "👤 <b>অ্যাকাউন্ট {current}/{total}</b>\n\n📁 সেশন:"
            " <code>{session_id}</code>\n⬇️ OTP পড়তে <b>Check</b> চাপুন।"
        ),
        "account_details": (
            "👤 <b>অ্যাকাউন্ট {current}/{total}</b>\n\n👤 ব্যবহারকারী:"
            " <b>{user}</b>\n📱 নম্বর: <code>{phone}</code>\n🔖 ইউজারনেম:"
            " <b>{username}</b>\n\n🧩 <b>OTP কোড (গত ২ ঘন্টা):</b>\n{otp_content}"
        ),
        "account_details_again": (
            "👤 <b>অ্যাকাউন্ট {current}/{total}</b>\n\n👤 ব্যবহারকারী:"
            " <b>{user}</b>\n📱 নম্বর: <code>{phone}</code>\n🔖 ইউজারনেম:"
            " <b>{username}</b>\n\n🧩 <b>OTP কোড (গত ২ ঘন্টা):</b>\n{otp_content}"
        ),
        "no_otps_2h": "<i>গত ২ ঘণ্টায় কোনো OTP কোড পাওয়া যায়নি।</i>",
        "no_otps_since": "<i>গত ২ ঘণ্টায় কোনো OTP কোড পাওয়া যায়নি।</i>",
        "logged_out": "🚪 সেশন সফলভাবে লগআউট করা হয়েছে।",
        "skipped_one": "⏭️ <i>{count}টি এড়িয়ে যাওয়া হয়েছে।</i>",
        "no_sessions": "কোনো বৈধ .session ফাইল পাওয়া যায়নি।",
        "all_processed": "✅ <b>সকল {total} টি অ্যাকাউন্ট সম্পন্ন হয়েছে!</b>",
        "btn_check": "✅ চেক করুন",
        "btn_skip": "⏭️ এড়িয়ে যান",
        "btn_check_again": "🔄 পুনরায় চেক করুন",
        "btn_logout": "🚪 লগআউট",
        "error_banned": (
            "🚫 <b>অ্যাকাউন্ট ব্যান/নিষ্ক্রিয়।</b>\n\n📁 সেশন:"
            " <code>{session_id}</code>\nআউনা অ্যাকাউন্টটি ব্যান বা নিষ্ক্রিয় হয়ে"
            " গেছে, তাই এর OTP পড়া যাবে না। এটি এড়িয়ে যান।"
        ),
        "error_2fa": (
            "🔐 <b>দুই-ধাপ যাচাই প্রয়োজন।</b>\n\n📁 সেশন:"
            " <code>{session_id}</code>\nOটিপি পড়তে পাসওয়ার্ড দরকার।"
        ),
        "error_invalid": (
            "❌ <b>অবৈধ/দূষিত সেশন।</b>\n\n📁 সেশন: <code>{session_id}</code>"
            "সেশন ডেটাবেস ক্ষতিগ্রস্ত।"
        ),
        "error_inconclusive": (
            "⚠️ <b>OTP পড়া যায়নি।</b>\n\n📁 সেশন: <code>{session_id}</code>"
            "সংযোগ ত্রুটি ঘটেছে।"
        ),
        "no_api_credentials": (
            "⚠️ <b>OTP পড়া যায়নি।</b>\n\n📁 সেশন:"
            " <code>{session_id}</code>\n"
            "এই বটে কোনো API ক্রেডেনশিয়াল কনফিগার করা নেই, তাই OTP মেসেজ"
            " টেলিগ্রাম থেকে পড়া যাবে না।"
        ),
        "logout_failed": (
            "🚪 <b>লগআউট ব্যর্থ হয়েছে।</b>\n\n📁 সেশন:"
            " <code>{session_id}</code>\n"
            "সেশনটি লগআউট করা যায়নি (API ক্রেডেনশিয়াল নেই, অননুমোদিত সেশন"
            " বা সংযোগ ত্রুটি)।"
        ),
    },
    "hi": {
        "account_header": (
            "👤 <b>अकाउंट {current}/{total}</b>\n\n📁 सेशन:"
            " <code>{session_id}</code>\n⬇️ OTP पढ़ने के लिए <b>Check</b>"
            " दबाएं।"
        ),
        "account_details": (
            "👤 <b>अकाउंट {current}/{total}</b>\n\n👤 उपयोगकर्ता:"
            " <b>{user}</b>\n📱 नंबर: <code>{phone}</code>\n🔖 यूज़रनेम:"
            " <b>{username}</b>\n\n🧩 <b>OTP कोड (पिछले 2 घंटे):</b>\n{otp_content}"
        ),
        "account_details_again": (
            "👤 <b>अकाउंट {current}/{total}</b>\n\n👤 उपयोगकर्ता:"
            " <b>{user}</b>\n📱 नंबर: <code>{phone}</code>\n🔖 यूज़रनेम:"
            " <b>{username}</b>\n\n🧩 <b>OTP कोड (पिछले 2 घंटे):</b>\n{otp_content}"
        ),
        "no_otps_2h": "<i>पिछले 2 घंटों में कोई OTP कोड नहीं मिला।</i>",
        "no_otps_since": "<i>पिछले 2 घंटों में कोई OTP कोड नहीं मिला।</i>",
        "logged_out": "🚪 सेशन सफलतापूर्वक लॉग आउट हो गया।",
        "skipped_one": "⏭️ <i>{count} छोड़े गए।</i>",
        "no_sessions": "कोई मान्य .session फ़ाइल नहीं मिली।",
        "all_processed": "✅ <b>सभी {total} अकाउंट प्रोसेस हो गए!</b>",
        "btn_check": "✅ जाँचें",
        "btn_skip": "⏭️ छोड़ें",
        "btn_check_again": "🔄 पुनः जाँचें",
        "btn_logout": "🚪 लॉग आउट",
        "error_banned": (
            "🚫 <b>अकाउंट प्रतिबंधित/निष्क्रिय।</b>\n\n📁 सेशन:"
            " <code>{session_id}</code>\nयह अकाउंट टेलीग्राम द्वारा बैन या निष्क्रिय"
            " कर दिया गया है, इसलिए OTP नहीं पढ़े जा सकते। इसे छोड़ें।"
        ),
        "error_2fa": (
            "🔐 <b>दो-चरणीय सत्यापन आवश्यक।</b>\n\n📁 सेशन: <code>{session_id}</code>"
"OTP पढ़ने के लिए पासवर्ड चाहिए।"
        ),
        "error_invalid": (
            "❌ <b>अमान्य/क्षतिग्रस्त सेशन।</b>\n\n📁 सेशन: <code>{session_id}</code>"
            "सेशन डेटाबेस दूषित है।"
        ),
        "error_inconclusive": (
            "⚠️ <b>OTP नहीं पढ़ सके।</b>\n\n📁 सेशन: <code>{session_id}</code>"
            "कनेक्शन त्रुटि हुई।"
        ),
        "no_api_credentials": (
            "⚠️ <b>OTP नहीं पढ़ सके।</b>\n\n📁 सेशन:"
            " <code>{session_id}</code>\n"
            "इस बॉट पर कोई API क्रेडेंशियल कॉन्फ़िगर नहीं है, इसलिए OTP संदेश"
            " टेलीग्राम से नहीं पढ़े जा सकते।"
        ),
        "logout_failed": (
            "🚪 <b>लॉगआउट विफल।</b>\n\n📁 सेशन: <code>{session_id}</code>\n"
            "सेशन लॉगआउट नहीं हो सका (कोई API क्रेडेंशियल नहीं, अनधिकृत सेशन,"
            " या कनेक्शन त्रुटि)।"
        ),
    },
    "ur": {
        "account_header": (
            "👤 <b>اکاؤنٹ {current}/{total}</b>\n\n📁 سیشن:"
            " <code>{session_id}</code>\n⬇️ OTP پڑھنے کے لیے <b>Check</b>"
            " دبائیں۔"
        ),
        "account_details": (
            "👤 <b>اکاؤنٹ {current}/{total}</b>\n\n👤 صارف: <b>{user}</b>\n📱"
            " نمبر: <code>{phone}</code>\n🔖 یوزر نیم: <b>{username}</b>\n\n🧩"
            " <b>OTP کوڈز (گزشتہ 2 گھنٹے):</b>\n{otp_content}"
        ),
        "account_details_again": (
            "👤 <b>اکاؤنٹ {current}/{total}</b>\n\n👤 صارف: <b>{user}</b>\n📱"
            " نمبر: <code>{phone}</code>\n🔖 یوزر نیم: <b>{username}</b>\n\n🧩"
            " <b>OTP کوڈز (گزشتہ 2 گھنٹے):</b>\n{otp_content}"
        ),
        "no_otps_2h": "<i>گزشتہ 2 گھنٹوں میں کوئی OTP کوڈ نہیں ملا۔</i>",
        "no_otps_since": "<i>گزشتہ 2 گھنٹوں میں کوئی OTP کوڈ نہیں ملا۔</i>",
        "logged_out": "🚪 سیشن کامیابی کے ساتھ لاگ آؤٹ ہو گیا۔",
        "skipped_one": "⏭️ <i>{count} چھوڑ دیے گئے۔</i>",
        "no_sessions": "کوئی درست .session فائل نہیں ملی۔",
        "all_processed": "✅ <b>تمام {total} اکاؤنٹس پروسیس ہو گئے!</b>",
        "btn_check": "✅ چیک کریں",
        "btn_skip": "⏭️ چھوڑیں",
        "btn_check_again": "🔄 دوبارہ چیک کریں",
        "btn_logout": "🚪 لاگ آؤٹ",
        "error_banned": (
            "🚫 <b>اکاؤنٹ بین/غیر فعال۔</b>\n\n📁 سیشن: <code>{session_id}</code>"
"یہ اکاؤنٹ بین یا غیر فعال ہو چکا ہے، OTP پڑھا نہیں جا سکتا۔ اسے چھوڑیں۔"
        ),
        "error_2fa": (
            "🔐 <b>دو مرحلہ توثیق ضروری۔</b>\n\n📁 سیشن: <code>{session_id}</code>"
"OTP پڑھنے کے لیے پاسورڈ درکار ہے۔"
        ),
        "error_invalid": (
            "❌ <b>غلط/خراب سیشن۔</b>\n\n📁 سیشن: <code>{session_id}</code>"
            "سیشن ڈیٹا بیس خراب ہے۔"
        ),
        "error_inconclusive": (
            "⚠️ <b>OTP پڑھا نہیں جا سکا۔</b>\n\n📁 سیشن: <code>{session_id}</code>"
            "کنکشن خرابی واقع ہوئی۔"
        ),
        "no_api_credentials": (
            "⚠️ <b>OTP پڑھا نہیں جا سکا۔</b>\n\n📁 سیشن:"
            " <code>{session_id}</code>\n"
            "اس بوٹ پر کوئی API اسناد ترتیب نہیں دی گئیں، اس لیے OTP پیغامات"
            " ٹیلیگرام سے پڑھے نہیں جا سکتے۔"
        ),
        "logout_failed": (
            "🚪 <b>لاگ آؤٹ ناکام۔</b>\n\n📁 سیشن: <code>{session_id}</code>\n"
            "سیشن لاگ آؤٹ نہیں ہو سکا (کوئی API اسناد نہیں، غیر مجاز سیشن، یا"
            " کنکشن خرابی)۔"
        ),
    },
    "ar": {
        "account_header": (
            "👤 <b>الحساب {current}/{total}</b>\n\n📁 الجلسة:"
            " <code>{session_id}</code>\n⬇️ اضغط <b>فحص</b> لقراءة رموز OTP."
        ),
        "account_details": (
            "👤 <b>الحساب {current}/{total}</b>\n\n👤 المستخدم:"
            " <b>{user}</b>\n📱 الرقم: <code>{phone}</code>\n🔖 اسم المستخدم:"
            " <b>{username}</b>\n\n🧩 <b>رموز OTP (خلال الساعتين"
            " الماضيتين):</b>\n{otp_content}"
        ),
        "account_details_again": (
            "👤 <b>الحساب {current}/{total}</b>\n\n👤 المستخدم:"
            " <b>{user}</b>\n📱 الرقم: <code>{phone}</code>\n🔖 اسم المستخدم:"
            " <b>{username}</b>\n\n🧩 <b>رموز OTP (خلال الساعتين"
            " الماضيتين):</b>\n{otp_content}"
        ),
        "no_otps_2h": ("<i>لم يتم العثور على رموز OTP في الساعتين الماضيتين.</i>"),
        "no_otps_since": ("<i>لم يتم العثور على رموز OTP في الساعتين الماضيتين.</i>"),
        "logged_out": "🚪 تم تسجيل الخروج من الجلسة بنجاح.",
        "skipped_one": "⏭️ <i>تم تخطي {count}.</i>",
        "no_sessions": "لم يتم العثور على ملفات .session صالحة.",
        "all_processed": "✅ <b>تمت معالجة جميع الحسابات الـ {total}!</b>",
        "btn_check": "✅ فحص",
        "btn_skip": "⏭️ تخطي",
        "btn_check_again": "🔄 فحص مجدداً",
        "btn_logout": "🚪 تسجيل الخروج",
        "error_banned": (
            "🚫 <b>الحساب محظور/معطل.</b>\n\n📁 الجلسة: <code>{session_id}</code>"
            "تم حظر أو تعطيل هذا الحساب من تيليجرام، لذا لا يمكن قراءة رموز OTP. تخطّه."
        ),
        "error_2fa": (
            "🔐 <b>مطلوب التحقق بخطوتين.</b>\n\n📁 الجلسة: <code>{session_id}</code>"
            "التحقق محمي بكلمة مرور؛ لا يمكن قراءة الرموز بدونها."
        ),
        "error_invalid": (
            "❌ <b>جلسة غير صالحة/تالفة.</b>\n\n📁 الجلسة: <code>{session_id}</code>"
            "قاعدة بيانات الجلسة تالفة."
        ),
        "error_inconclusive": (
            "⚠️ <b>تعذر قراءة OTP.</b>\n\n📁 الجلسة: <code>{session_id}</code>"
            "حدث خطأ في الاتصال."
        ),
        "no_api_credentials": (
            "⚠️ <b>تعذر قراءة OTP.</b>\n\n📁 الجلسة:"
            " <code>{session_id}</code>\n"
            "لا توجد بيانات اعتماد API مُهيأة على هذا البوت، لذا لا يمكن قراءة"
            " رسائل OTP من تيليجرام."
        ),
        "logout_failed": (
            "🚪 <b>فشل تسجيل الخروج.</b>\n\n📁 الجلسة:"
            " <code>{session_id}</code>\n"
            "تعذر تسجيل الخروج من الجلسة (لا توجد بيانات اعتماد API، أو جلسة"
            " غير مصرح بها، أو خطأ اتصال)."
        ),
    },
    "zh": {
        "account_header": (
            "👤 <b>账户 {current}/{total}</b>\n\n📁 会话:"
            " <code>{session_id}</code>\n⬇️ 按 <b>检查</b> 读取 OTP 验证码。"
        ),
        "account_details": (
            "👤 <b>账户 {current}/{total}</b>\n\n👤 用户: <b>{user}</b>\n📱"
            " 手机号: <code>{phone}</code>\n🔖 用户名: <b>{username}</b>\n\n🧩"
            " <b>OTP 验证码 (最近 2 小时):</b>\n{otp_content}"
        ),
        "account_details_again": (
            "👤 <b>账户 {current}/{total}</b>\n\n👤 用户: <b>{user}</b>\n📱"
            " 手机号: <code>{phone}</code>\n🔖 用户名: <b>{username}</b>\n\n🧩"
            " <b>OTP 验证码 (最近 2 小时):</b>\n{otp_content}"
        ),
        "no_otps_2h": "<i>过去 2 小时内未找到 OTP 验证码。</i>",
        "no_otps_since": "<i>过去 2 小时内未找到 OTP 验证码。</i>",
        "logged_out": "🚪 会话已成功登出。",
        "skipped_one": "⏭️ <i>已跳过 {count} 个。</i>",
        "no_sessions": "未找到有效的 .session 文件。",
        "all_processed": "✅ <b>所有 {total} 个账户已处理完毕！</b>",
        "btn_check": "✅ 检查",
        "btn_skip": "⏭️ 跳过",
        "btn_check_again": "🔄 再次检查",
        "btn_logout": "登出",
        "error_banned": (
            "🚫 <b>账户已被封禁/停用。</b>\n\n📁 会话: <code>{session_id}</code>"
            "该账户已被 Telegram 封禁或停用，无法读取 OTP。请跳过。"
        ),
        "error_2fa": (
            "🔐 <b>需要两步验证。</b>\n\n📁 会话: <code>{session_id}</code>"
            "登录受两步密码保护，无法读取 OTP。"
        ),
        "error_invalid": (
            "❌ <b>无效/损坏的会话。</b>\n\n📁 会话: <code>{session_id}</code>"
            "会话数据库损坏，无法读取 OTP。"
        ),
        "error_inconclusive": (
            "⚠️ <b>无法读取 OTP。</b>\n\n📁 会话: <code>{session_id}</code>"
            "发生连接错误（网络超时或凭据问题）。"
        ),
        "no_api_credentials": (
            "⚠️ <b>无法读取 OTP。</b>\n\n📁 会话:"
            " <code>{session_id}</code>\n"
            "该机器人未配置任何 API 凭据，因此无法从 Telegram 读取 OTP 消息。"
        ),
        "logout_failed": (
            "🚪 <b>登出失败。</b>\n\n📁 会话: <code>{session_id}</code>\n"
            "无法登出会话（未配置 API 凭据、会话未授权或连接错误）。"
        ),
    },
}

CHECK_CONTACTS_PROMPTS = {
    "bn": "📋 <b>কন্টাক্ট দেখুন</b>\n\nএকটি .session ফাইল বা .zip পাঠান।",
    "en": "📋 <b>Check Contacts</b>\n\nSend a .session file or .zip.",
    "hi": "📋 <b>कॉन्ट्रैक्ट्स जांचें</b>\n\nएक .session फ़ाइल या .zip भेजें।",
    "ur": "📋 <b>رابطے چیک کریں</b>\n\nایک .session فائل یا .zip بھیجیں۔",
    "ar": "📋 <b>فحص جهات الاتصال</b>\n\nأرسل ملف .session أو .zip.",
    "zh": "📋 <b>检查联系人</b>\n\n发送 .session 文件或 .zip。",
}

CHECK_CONTACTS_MESSAGES = {
    "bn": {
        "checking": "⏳ কন্টাক্ট পরীক্ষা চলছে...",
        "cancelled": "কন্টাক্ট পরীক্ষা বাতিল করা হয়েছে।",
    },
    "en": {
        "checking": "⏳ Checking contacts...",
        "cancelled": "Contact check cancelled.",
    },
    "hi": {
        "checking": "⏳ कॉन्ट्रैक्ट्स जांच हो रही है...",
        "cancelled": "कॉन्ट्रैक्ट्स जांच रद्द कर दी गई।",
    },
    "ur": {
        "checking": "⏳ رابطوں کی جانچ ہو رہی ہے...",
        "cancelled": "رابطوں کی جانچ منسوخ کر دی گئی۔",
    },
    "ar": {
        "checking": "⏳ جارٍ فحص جهات الاتصال...",
        "cancelled": "تم إلغاء فحص جهات الاتصال.",
    },
    "zh": {
        "checking": "⏳ 正在检查联系人...",
        "cancelled": "联系人检查已取消。",
    },
}

SESSION_TO_TDATA_PROMPTS = {
    "en": (
        "🔄 <b>Session → Tdata</b>\n\nSend a <code>.session</code> file or"
        " <code>.zip</code>."
    ),
    "bn": (
        "🔄 <b>সেশন → Tdata</b>\n\nএকটি <code>.session</code> ফাইল অথবা"
        " <code>.zip</code> পাঠান।"
    ),
    "hi": (
        "🔄 <b>सेशन → Tdata</b>\n\nएक <code>.session</code> फ़ाइल या"
        " <code>.zip</code> भेजें।"
    ),
    "ur": (
        "🔄 <b>سیشن → Tdata</b>\n\nایک <code>.session</code> فائل یا"
        " <code>.zip</code> بھیجیں۔"
    ),
    "ar": (
        "🔄 <b>الجلسة → Tdata</b>\n\nأرسل ملف <code>.session</code> أو"
        " <code>.zip</code>."
    ),
    "zh": (
        "🔄 <b>会话 → Tdata</b>\n\n请发送 <code>.session</code> 文件或"
        " <code>.zip</code>。"
    ),
}

SESSION_TO_TDATA_MESSAGES = {
    "en": {
        "converting": "⏳ Converting session to Tdata...",
        "done": ("✅ <b>Conversion completed!</b>\n\nConverted: {converted}/{total}"),
        "no_valid_sessions": "❌ No valid .session files found for conversion.",
        "title": "🎯 <b>Session → Tdata Report</b>",
        "summary": "📦 Total: {total} | ✅ Converted: {converted} | ❌ Failed: {failed}",
        "stats": (
            "🎊 <b>Conversion complete!</b>\n\n"
            "📊 <b>Conversion Stats</b>\n"
            "· Total: {total}\n"
            "· ✅ Success: {converted} ({pct_converted}%)\n"
            "· ❌ Failed: {failed} ({pct_failed}%)\n"
            "· ⏱️ Duration: {duration}\n"
            "· 🚀 Avg speed: {speed}/sec"
        ),
        "stats_unverified": (
            "⚠️ <b>Unverified:</b> no API credentials configured — this result is"
            " based on local file processing only, not live Telegram verification."
        ),
        "btn_total": "Total",
        "btn_converted": "Converted",
        "btn_failed": "Failed",
        "btn_retry": "Run Again",
        "btn_home": "Home",
        "caption": "🎯 Converted Tdata",
        "cancelled": "🚫 Conversion cancelled.",
        "more": "\n<i>... and {count} more</i>",
    },
    "bn": {
        "converting": "⏳ সেশন Tdata তে রূপান্তর করা হচ্ছে...",
        "done": ("✅ <b>রূপান্তর সম্পূর্ণ হয়েছে!</b>\n\nরূপান্তরিত: {converted}/{total}"),
        "no_valid_sessions": ("❌ রূপান্তরের জন্য কোনো বৈধ .session ফাইল পাওয়া যায়নি।"),
        "title": "🎯 <b>সেশন → Tdata রিপোর্ট</b>",
        "summary": "📦 মোট: {total} | ✅ রূপান্তরিত: {converted} | ❌ ব্যর্থ: {failed}",
        "stats": (
            "🎉 <b>রূপান্তর সম্পূর্ণ হয়েছে!</b>\n\n"
            "📊 <b>রূপান্তর পরিসংখ্যান</b>\n"
            "· মোট: {total}\n"
            "· ✅ সফল: {converted} ({pct_converted}%)\n"
            "· ❌ ব্যর্থ: {failed} ({pct_failed}%)\n"
            "· ⏱️ সময়: {duration}\n"
            "· 🚀 গতি: {speed}/সেকেন্ড"
        ),
        "stats_unverified": (
            "⚠️ <b>অযাচাই:</b> কোনো API ক্রেডেনশিয়াল কনফিগার করা নেই — এই ফলাফল কেবল"
            " স্থানীয় ফাইল প্রসেসিংয়ের ভিত্তিতে, লাইভ টেলিগ্রাম যাচাই নয়।"
        ),
        "btn_total": "মোট",
        "btn_converted": "রূপান্তরিত",
        "btn_failed": "ব্যর্থ",
        "btn_retry": "আবার চালান",
        "btn_home": "হোম",
        "caption": "🎯 রূপান্তরিত Tdata",
        "cancelled": "🚫 রূপান্তর বাতিল করা হয়েছে।",
        "more": "\n<i>... এবং আরও {count}টি</i>",
    },
    "hi": {
        "converting": "⏳ सेशन Tdata में बदला जा रहा है...",
        "done": ("✅ <b>रूपांतरण पूरा हुआ!</b>\n\nरूपांतरित: {converted}/{total}"),
        "no_valid_sessions": ("❌ रूपांतरण के लिए कोई मान्य .session फ़ाइल नहीं मिली।"),
        "title": "🎯 <b>सेशन → Tdata रिपोर्ट</b>",
        "summary": "📦 कुल: {total} | ✅ रूपांतरित: {converted} | ❌ विफल: {failed}",
        "stats": (
            "🎉 <b>रूपांतरण पूरा हुआ!</b>\n\n"
            "📊 <b>रूपांतरण आँकड़े</b>\n"
            "· कुल: {total}\n"
            "· ✅ सफल: {converted} ({pct_converted}%)\n"
            "· ❌ विफल: {failed} ({pct_failed}%)\n"
            "· ⏱️ अवधि: {duration}\n"
            "· 🚀 औसत गति: {speed}/सेकंड"
        ),
        "stats_unverified": (
            "⚠️ <b>असत्यापित:</b> कोई API क्रेडेंशियल कॉन्फ़िगर नहीं है — यह परिणाम केवल"
            " स्थानीय फ़ाइल प्रोसेसिंग पर आधारित है, लाइव Telegram सत्यापन नहीं।"
        ),
        "btn_total": "कुल",
        "btn_converted": "रूपांतरित",
        "btn_failed": "विफल",
        "btn_retry": "फिर चलाएँ",
        "btn_home": "होम",
        "caption": "🎯 रूपांतरित Tdata",
        "cancelled": "🚫 रूपांतरण रद्द कर दिया गया।",
        "more": "\n<i>... और {count} और</i>",
    },
    "ur": {
        "converting": "⏳ سیشن Tdata میں تبدیل ہو رہا ہے...",
        "done": ("✅ <b>تبدیلی مکمل ہو گئی!</b>\n\nتبدیل شدہ: {converted}/{total}"),
        "no_valid_sessions": ("❌ تبدیلی کے لیے کوئی درست .session فائل نہیں ملی۔"),
        "title": "🎯 <b>سیشن → Tdata رپورٹ</b>",
        "summary": "📦 کل: {total} | ✅ تبدیل شدہ: {converted} | ❌ ناکام: {failed}",
        "stats": (
            "🎉 <b>تبدیلی مکمل ہو گئی!</b>\n\n"
            "📊 <b>تبدیلی کے اعداد و شمار</b>\n"
            "· کل: {total}\n"
            "· ✅ کامیاب: {converted} ({pct_converted}%)\n"
            "· ❌ ناکام: {failed} ({pct_failed}%)\n"
            "· ⏱️ دورانیہ: {duration}\n"
            "· 🚀 اوسط رفتار: {speed}/سیکنڈ"
        ),
        "stats_unverified": (
            "⚠️ <b>غیر تصدیق شدہ:</b> کوئی API اسناد ترتیب نہیں دی گئیں — یہ نتیجہ صرف"
            " مقامی فائل پروسیسنگ پر مبنی ہے، لائیو ٹیلیگرام تصدیق نہیں۔"
        ),
        "btn_total": "کل",
        "btn_converted": "تبدیل شدہ",
        "btn_failed": "ناکام",
        "btn_retry": "دوبارہ چلائیں",
        "btn_home": "ہوم",
        "caption": "🎯 تبدیل شدہ Tdata",
        "cancelled": "🚫 تبدیلی منسوخ کر دی گئی۔",
        "more": "\n<i>... اور مزید {count}</i>",
    },
    "ar": {
        "converting": "⏳ جاري تحويل الجلسة إلى Tdata...",
        "done": ("✅ <b>اكتمل التحويل!</b>\n\nتم تحويل: {converted}/{total}"),
        "no_valid_sessions": ("❌ لم يتم العثور على ملفات .session صالحة للتحويل."),
        "title": "🎯 <b>تقرير الجلسة → Tdata</b>",
        "summary": "📦 الإجمالي: {total} | ✅ محوّل: {converted} | ❌ فشل: {failed}",
        "stats": (
            "🎉 <b>اكتمل التحويل!</b>\n\n"
            "📊 <b>إحصائيات التحويل</b>\n"
            "· الإجمالي: {total}\n"
            "· ✅ ناجح: {converted} ({pct_converted}%)\n"
            "· ❌ فشل: {failed} ({pct_failed}%)\n"
            "· ⏱️ المدة: {duration}\n"
            "· 🚀 متوسط السرعة: {speed}/ثانية"
        ),
        "stats_unverified": (
            "⚠️ <b>غير مُتحقق:</b> لا توجد بيانات اعتماد API مُهيأة — هذه النتيجة مبنية"
            " على المعالجة المحلية للملفات فقط، وليست تحققًا مباشرًا من تيليجرام."
        ),
        "btn_total": "الإجمالي",
        "btn_converted": "محوّل",
        "btn_failed": "فشل",
        "btn_retry": "إعادة تشغيل",
        "btn_home": "الرئيسية",
        "caption": "🎯 Tdata المحوّل",
        "cancelled": "🚫 تم إلغاء التحويل.",
        "more": "\n<i>... و {count} أخرى</i>",
    },
    "zh": {
        "converting": "⏳ 正在将会话转换为 Tdata...",
        "done": ("✅ <b>转换完成！</b>\n\n已转换：{converted}/{total}"),
        "no_valid_sessions": ("❌ 未找到可用于转换的有效 .session 文件。"),
        "title": "🎯 <b>会话 → Tdata 报告</b>",
        "summary": "📦 总计: {total} | ✅ 已转换: {converted} | ❌ 失败: {failed}",
        "stats": (
            "🎉 <b>转换完成！</b>\n\n"
            "📊 <b>转换统计</b>\n"
            "· 总计: {total}\n"
            "· ✅ 成功: {converted} ({pct_converted}%)\n"
            "· ❌ 失败: {failed} ({pct_failed}%)\n"
            "· ⏱️ 耗时: {duration}\n"
            "· 🚀 平均速度: {speed}/秒"
        ),
        "stats_unverified": (
            "⚠️ <b>未验证：</b>未配置任何 API 凭据 — 此结果仅基于本地文件处理，"
            "并非实时 Telegram 验证。"
        ),
        "btn_total": "总计",
        "btn_converted": "已转换",
        "btn_failed": "失败",
        "btn_retry": "再次运行",
        "btn_home": "首页",
        "caption": "🎯 已转换的 Tdata",
        "cancelled": "🚫 转换已取消。",
        "more": "\n<i>... 还有 {count} 个</i>",
    },
}

TDATA_TO_SESSION_PROMPTS = {
    "en": (
        "🔄 <b>Tdata → Session</b>\n\nSend a <code>.zip</code> file containing a"
        " tdata folder."
    ),
    "bn": (
        "🔄 <b>Tdata → সেশন</b>\n\ntdata ফোল্ডার সম্বলিত একটি <code>.zip</code> ফাইল পাঠান।"
    ),
    "hi": ("🔄 <b>Tdata → सेशन</b>\n\ntdata फ़ोल्डर वाली एक <code>.zip</code> फ़ाइल भेजें।"),
    "ur": (
        "🔄 <b>Tdata → سیشن</b>\n\ntdata فولڈر والی ایک <code>.zip</code> فائل بھیجیں۔"
    ),
    "ar": (
        "🔄 <b>Tdata → الجلسة</b>\n\nأرسل ملف <code>.zip</code> يحتوي على مجلد tdata."
    ),
    "zh": (
        "🔄 <b>Tdata → 会话</b>\n\n请发送包含 tdata 文件夹的 <code>.zip</code> 文件。"
    ),
}

TDATA_TO_SESSION_MESSAGES = {
    "en": {
        "converting": "⏳ Converting Tdata to session...",
        "done": ("✅ <b>Conversion completed!</b>\n\nConverted: {converted}/{total}"),
        "no_valid_tdata": "❌ No valid tdata folders found for conversion.",
        "title": "🔄 <b>Tdata → Session Report</b>",
        "summary": "📦 Total: {total} | ✅ Converted: {converted} | ❌ Failed: {failed}",
        "stats": (
            "🎉 <b>Conversion complete!</b>\n\n"
            "📊 <b>Conversion Stats</b>\n"
            "· Total: {total}\n"
            "· ✅ Success: {converted} ({pct_converted}%)\n"
            "· ❌ Failed: {failed} ({pct_failed}%)\n"
            "· ⏱️ Duration: {duration}\n"
            "· 🚀 Avg speed: {speed}/sec"
        ),
        "stats_unverified": (
            "⚠️ <b>Unverified:</b> no API credentials configured — this result is"
            " based on local file processing only, not live Telegram verification."
        ),
        "btn_total": "Total",
        "btn_converted": "Converted",
        "btn_failed": "Failed",
        "btn_retry": "Run Again",
        "btn_home": "Home",
        "caption": "🔄 Converted Sessions",
        "cancelled": "🚫 Conversion cancelled.",
        "more": "\n<i>... and {count} more</i>",
    },
    "bn": {
        "converting": "⏳ Tdata সেশনে রূপান্তর করা হচ্ছে...",
        "done": ("✅ <b>রূপান্তর সম্পূর্ণ হয়েছে!</b>\n\nরূপান্তরিত: {converted}/{total}"),
        "no_valid_tdata": ("❌ রূপান্তরের জন্য কোনো বৈধ tdata ফোল্ডার পাওয়া যায়নি।"),
        "title": "🔄 <b>Tdata → সেশন রিপোর্ট</b>",
        "summary": "📦 মোট: {total} | ✅ রূপান্তরিত: {converted} | ❌ ব্যর্থ: {failed}",
        "stats": (
            "🎉 <b>রূপান্তর সম্পূর্ণ হয়েছে!</b>\n\n"
            "📊 <b>রূপান্তর পরিসংখ্যান</b>\n"
            "· মোট: {total}\n"
            "· ✅ সফল: {converted} ({pct_converted}%)\n"
            "· ❌ ব্যর্থ: {failed} ({pct_failed}%)\n"
            "· ⏱️ সময়: {duration}\n"
            "· 🚀 গতি: {speed}/সেকেন্ড"
        ),
        "stats_unverified": (
            "⚠️ <b>অযাচাই:</b> কোনো API ক্রেডেনশিয়াল কনফিগার করা নেই — এই ফলাফল কেবল"
            " স্থানীয় ফাইল প্রসেসিংয়ের ভিত্তিতে, লাইভ টেলিগ্রাম যাচাই নয়।"
        ),
        "btn_total": "মোট",
        "btn_converted": "রূপান্তরিত",
        "btn_failed": "ব্যর্থ",
        "btn_retry": "আবার চালান",
        "btn_home": "হোম",
        "caption": "🔄 রূপান্তরিত সেশন",
        "cancelled": "🚫 রূপান্তর বাতিল করা হয়েছে।",
        "more": "\n<i>... এবং আরও {count}টি</i>",
    },
    "hi": {
        "converting": "⏳ Tdata सेशन में बदला जा रहा है...",
        "done": ("✅ <b>रूपांतरण पूरा हुआ!</b>\n\nरूपांतरित: {converted}/{total}"),
        "no_valid_tdata": ("❌ रूपांतरण के लिए कोई मान्य tdata फ़ोल्डर नहीं मिला।"),
        "title": "🔄 <b>Tdata → सेशन रिपोर्ट</b>",
        "summary": "📦 कुल: {total} | ✅ रूपांतरित: {converted} | ❌ विफल: {failed}",
        "stats": (
            "🎉 <b>रूपांतरण पूरा हुआ!</b>\n\n"
            "📊 <b>रूपांतरण आँकड़े</b>\n"
            "· कुल: {total}\n"
            "· ✅ सफल: {converted} ({pct_converted}%)\n"
            "· ❌ विफल: {failed} ({pct_failed}%)\n"
            "· ⏱️ अवधि: {duration}\n"
            "· 🚀 औसत गति: {speed}/सेकंड"
        ),
        "stats_unverified": (
            "⚠️ <b>असत्यापित:</b> कोई API क्रेडेंशियल कॉन्फ़िगर नहीं है — यह परिणाम केवल"
            " स्थानीय फ़ाइल प्रोसेसिंग पर आधारित है, लाइव Telegram सत्यापन नहीं।"
        ),
        "btn_total": "कुल",
        "btn_converted": "रूपांतरित",
        "btn_failed": "विफल",
        "btn_retry": "फिर चलाएँ",
        "btn_home": "होम",
        "caption": "🔄 रूपांतरित सेशन",
        "cancelled": "🚫 रूपांतरण रद्द कर दिया गया।",
        "more": "\n<i>... और {count} और</i>",
    },
    "ur": {
        "converting": "⏳ Tdata سیشن میں تبدیل ہو رہا ہے...",
        "done": ("✅ <b>تبدیلی مکمل ہو گئی!</b>\n\nتبدیل شدہ: {converted}/{total}"),
        "no_valid_tdata": ("❌ تبدیلی کے لیے کوئی درست tdata فولڈر نہیں ملا۔"),
        "title": "🔄 <b>Tdata → سیشن رپورٹ</b>",
        "summary": "📦 کل: {total} | ✅ تبدیل شدہ: {converted} | ❌ ناکام: {failed}",
        "stats": (
            "🎉 <b>تبدیلی مکمل ہو گئی!</b>\n\n"
            "📊 <b>تبدیلی کے اعداد و شمار</b>\n"
            "· کل: {total}\n"
            "· ✅ کامیاب: {converted} ({pct_converted}%)\n"
            "· ❌ ناکام: {failed} ({pct_failed}%)\n"
            "· ⏱️ دورانیہ: {duration}\n"
            "· 🚀 اوسط رفتار: {speed}/سیکنڈ"
        ),
        "stats_unverified": (
            "⚠️ <b>غیر تصدیق شدہ:</b> کوئی API اسناد ترتیب نہیں دی گئیں — یہ نتیجہ صرف"
            " مقامی فائل پروسیسنگ پر مبنی ہے، لائیو ٹیلیگرام تصدیق نہیں۔"
        ),
        "btn_total": "کل",
        "btn_converted": "تبدیل شدہ",
        "btn_failed": "ناکام",
        "btn_retry": "دوبارہ چلائیں",
        "btn_home": "ہوم",
        "caption": "🔄 تبدیل شدہ سیشن",
        "cancelled": "🚫 تبدیلی منسوخ کر دی گئی۔",
        "more": "\n<i>... اور مزید {count}</i>",
    },
    "ar": {
        "converting": "⏳ جاري تحويل Tdata إلى جلسة...",
        "done": ("✅ <b>اكتمل التحويل!</b>\n\nتم تحويل: {converted}/{total}"),
        "no_valid_tdata": ("❌ لم يتم العثور على مجلدات tdata صالحة للتحويل."),
        "title": "🔄 <b>تقرير Tdata → الجلسة</b>",
        "summary": "📦 الإجمالي: {total} | ✅ محوّل: {converted} | ❌ فشل: {failed}",
        "stats": (
            "🎉 <b>اكتمل التحويل!</b>\n\n"
            "📊 <b>إحصائيات التحويل</b>\n"
            "· الإجمالي: {total}\n"
            "· ✅ ناجح: {converted} ({pct_converted}%)\n"
            "· ❌ فشل: {failed} ({pct_failed}%)\n"
            "· ⏱️ المدة: {duration}\n"
            "· 🚀 متوسط السرعة: {speed}/ثانية"
        ),
        "stats_unverified": (
            "⚠️ <b>غير مُتحقق:</b> لا توجد بيانات اعتماد API مُهيأة — هذه النتيجة مبنية"
            " على المعالجة المحلية للملفات فقط، وليست تحققًا مباشرًا من تيليجرام."
        ),
        "btn_total": "الإجمالي",
        "btn_converted": "محوّل",
        "btn_failed": "فشل",
        "btn_retry": "إعادة تشغيل",
        "btn_home": "الرئيسية",
        "caption": "🔄 الجلسات المحوّلة",
        "cancelled": "🚫 تم إلغاء التحويل.",
        "more": "\n<i>... و {count} أخرى</i>",
    },
    "zh": {
        "converting": "⏳ 正在将 Tdata 转换为会话...",
        "done": ("✅ <b>转换完成！</b>\n\n已转换：{converted}/{total}"),
        "no_valid_tdata": "❌ 未找到可用于转换的有效 tdata 文件夹。",
        "title": "🔄 <b>Tdata → 会话 报告</b>",
        "summary": "📦 总计: {total} | ✅ 已转换: {converted} | ❌ 失败: {failed}",
        "stats": (
            "🎉 <b>转换完成！</b>\n\n"
            "📊 <b>转换统计</b>\n"
            "· 总计: {total}\n"
            "· ✅ 成功: {converted} ({pct_converted}%)\n"
            "· ❌ 失败: {failed} ({pct_failed}%)\n"
            "· ⏱️ 耗时: {duration}\n"
            "· 🚀 平均速度: {speed}/秒"
        ),
        "stats_unverified": (
            "⚠️ <b>未验证：</b>未配置任何 API 凭据 — 此结果仅基于本地文件处理，"
            "并非实时 Telegram 验证。"
        ),
        "btn_total": "总计",
        "btn_converted": "已转换",
        "btn_failed": "失败",
        "btn_retry": "再次运行",
        "btn_home": "首页",
        "caption": "🔄 已转换的会话",
        "cancelled": "🚫 转换已取消。",
        "more": "\n<i>... 还有 {count} 个</i>",
    },
}

ACCOUNT_TO_TXT_PROMPTS = {
    "en": "📄 <b>Account → Txt</b>\n\nSend a <code>.session</code> file or <code>.zip</code>.",
    "bn": "📄 <b>অ্যাকাউন্ট → Txt</b>\n\nএকটি <code>.session</code> ফাইল অথবা <code>.zip</code> পাঠান।",
    "hi": "📄 <b>अकाउंट → Txt</b>\n\nएक <code>.session</code> फ़ाइल या <code>.zip</code> भेजें।",
    "ur": "📄 <b>اکاؤنٹ → Txt</b>\n\nایک <code>.session</code> فائل یا <code>.zip</code> بھیجیں۔",
    "ar": "📄 <b>الحساب → Txt</b>\n\nأرسل ملف <code>.session</code> أو <code>.zip</code>.",
    "zh": "📄 <b>账户 → Txt</b>\n\n请发送 <code>.session</code> 文件或 <code>.zip</code>。",
}

ACCOUNT_TO_TXT_MESSAGES = {
    "en": {
        "converting": "⏳ Creating account TXT files...",
        "title": "📄 <b>Account → Txt Report</b>",
        "summary": "📦 Total: {total} | ✅ Active: {active} | ⚠️ Invalid(converted): {invalid} | ❌ Failed: {failed}",
        "no_output": "❌ No account TXT files could be created.",
        "btn_total": "Total",
        "btn_converted": "Converted",
        "btn_failed": "Failed",
        "btn_retry": "Run Again",
        "btn_home": "Home",
        "caption": "📄 Account TXT Files",
        "cancelled": "🚫 Conversion cancelled.",
        "more": "\n<i>... and {count} more</i>",
    },
    "bn": {
        "converting": "⏳ অ্যাকাউন্ট TXT ফাইল তৈরি হচ্ছে...",
        "title": "📄 <b>অ্যাকাউন্ট → Txt রিপোর্ট</b>",
        "summary": "📦 মোট: {total} | ✅ সক্রিয়: {active} | ⚠️ অবৈধ(রূপান্তরিত): {invalid} | ❌ ব্যর্থ: {failed}",
        "no_output": "❌ কোনো অ্যাকাউন্ট TXT ফাইল তৈরি করা যায়নি।",
        "btn_total": "মোট",
        "btn_converted": "রূপান্তরিত",
        "btn_failed": "ব্যর্থ",
        "btn_retry": "আবার চালান",
        "btn_home": "হোম",
        "caption": "📄 অ্যাকাউন্ট TXT ফাইল",
        "cancelled": "🚫 রূপান্তর বাতিল করা হয়েছে।",
        "more": "\n<i>... এবং আরও {count}টি</i>",
    },
    "hi": {
        "converting": "⏳ अकाउंट TXT फ़ाइलें बनाई जा रही हैं...",
        "title": "📄 <b>अकाउंट → Txt रिपोर्ट</b>",
        "summary": "📦 कुल: {total} | ✅ सक्रिय: {active} | ⚠️ अमान्य(परिवर्तित): {invalid} | ❌ विफल: {failed}",
        "no_output": "❌ कोई अकाउंट TXT फ़ाइल नहीं बनाई जा सकी।",
        "btn_total": "कुल",
        "btn_converted": "परिवर्तित",
        "btn_failed": "विफल",
        "btn_retry": "फिर चलाएँ",
        "btn_home": "होम",
        "caption": "📄 अकाउंट TXT फ़ाइलें",
        "cancelled": "🚫 रूपांतरण रद्द कर दिया गया।",
        "more": "\n<i>... और {count} और</i>",
    },
    "ur": {
        "converting": "⏳ اکاؤنٹ TXT فائلیں بن رہی ہیں...",
        "title": "📄 <b>اکاؤنٹ → Txt رپورٹ</b>",
        "summary": "📦 کل: {total} | ✅ فعال: {active} | ⚠️ غلط(تبدیل شدہ): {invalid} | ❌ ناکام: {failed}",
        "no_output": "❌ کوئی اکاؤنٹ TXT فائل نہیں بن سکی۔",
        "btn_total": "کل",
        "btn_converted": "تبدیل شدہ",
        "btn_failed": "ناکام",
        "btn_retry": "دوبارہ چلائیں",
        "btn_home": "ہوم",
        "caption": "📄 اکاؤنٹ TXT فائلیں",
        "cancelled": "🚫 تبدیلی منسوخ کر دی گئی۔",
        "more": "\n<i>... اور مزید {count}</i>",
    },
    "ar": {
        "converting": "⏳ جارٍ إنشاء ملفات TXT للحسابات...",
        "title": "📄 <b>تقرير الحساب → Txt</b>",
        "summary": "📦 الإجمالي: {total} | ✅ نشط: {active} | ⚠️ غير صالح(محوّل): {invalid} | ❌ فشل: {failed}",
        "no_output": "❌ تعذر إنشاء أي ملفات TXT للحسابات.",
        "btn_total": "الإجمالي",
        "btn_converted": "محوّل",
        "btn_failed": "فشل",
        "btn_retry": "إعادة تشغيل",
        "btn_home": "الرئيسية",
        "caption": "📄 ملفات TXT للحسابات",
        "cancelled": "🚫 تم إلغاء التحويل.",
        "more": "\n<i>... و {count} أخرى</i>",
    },
    "zh": {
        "converting": "⏳ 正在创建账户 TXT 文件...",
        "title": "📄 <b>账户 → Txt 报告</b>",
        "summary": "📦 总计: {total} | ✅ 活跃: {active} | ⚠️ 无效(已转换): {invalid} | ❌ 失败: {failed}",
        "no_output": "❌ 无法创建账户 TXT 文件。",
        "btn_total": "总计",
        "btn_converted": "已转换",
        "btn_failed": "失败",
        "btn_retry": "再次运行",
        "btn_home": "首页",
        "caption": "📄 账户 TXT 文件",
        "cancelled": "🚫 转换已取消。",
        "more": "\n<i>... 还有 {count} 个</i>",
    },
}

SESSION_TO_JSON_PROMPTS = {
    "en": "📝 <b>Session → Json</b>\n\nSend a <code>.session</code> file or <code>.zip</code>.",
    "bn": "📝 <b>সেশন → Json</b>\n\nএকটি <code>.session</code> ফাইল অথবা <code>.zip</code> পাঠান।",
    "hi": "📝 <b>सेशन → Json</b>\n\nएक <code>.session</code> फ़ाइल या <code>.zip</code> भेजें।",
    "ur": "📝 <b>سیشن → Json</b>\n\nایک <code>.session</code> فائل یا <code>.zip</code> بھیجیں۔",
    "ar": "📝 <b>الجلسة → Json</b>\n\nأرسل ملف <code>.session</code> أو <code>.zip</code>.",
    "zh": "📝 <b>会话 → Json</b>\n\n请发送 <code>.session</code> 文件或 <code>.zip</code>。",
}

SESSION_TO_JSON_MESSAGES = {
    "en": {
        "converting": "⏳ Creating session JSON files...",
        "title": "📝 <b>Session → Json Report</b>",
        "summary": "📦 Total: {total} | ✅ Active: {active} | ⚠️ Invalid(converted): {invalid} | ❌ Failed: {failed}",
        "no_output": "❌ No session JSON files could be created.",
        "btn_total": "Total",
        "btn_converted": "Converted",
        "btn_failed": "Failed",
        "btn_retry": "Run Again",
        "btn_home": "Home",
        "caption": "📝 Session JSON Files",
        "cancelled": "🚫 Conversion cancelled.",
        "more": "\n<i>... and {count} more</i>",
    },
    "bn": {
        "converting": "⏳ সেশন JSON ফাইল তৈরি হচ্ছে...",
        "title": "📝 <b>সেশন → Json রিপোর্ট</b>",
        "summary": "📦 মোট: {total} | ✅ সক্রিয়: {active} | ⚠️ অবৈধ(রূপান্তরিত): {invalid} | ❌ ব্যর্থ: {failed}",
        "no_output": "❌ কোনো সেশন JSON ফাইল তৈরি করা যায়নি।",
        "btn_total": "মোট",
        "btn_converted": "রূপান্তরিত",
        "btn_failed": "ব্যর্থ",
        "btn_retry": "আবার চালান",
        "btn_home": "হোম",
        "caption": "📝 সেশন JSON ফাইল",
        "cancelled": "🚫 রূপান্তর বাতিল করা হয়েছে।",
        "more": "\n<i>... এবং আরও {count}টি</i>",
    },
    "hi": {
        "converting": "⏳ सेशन JSON फ़ाइलें बनाई जा रही हैं...",
        "title": "📝 <b>सेशन → Json रिपोर्ट</b>",
        "summary": "📦 कुल: {total} | ✅ सक्रिय: {active} | ⚠️ अमान्य(परिवर्तित): {invalid} | ❌ विफल: {failed}",
        "no_output": "❌ कोई सेशन JSON फ़ाइल नहीं बनाई जा सकी।",
        "btn_total": "कुल",
        "btn_converted": "परिवर्तित",
        "btn_failed": "विफल",
        "btn_retry": "फिर चलाएँ",
        "btn_home": "होम",
        "caption": "📝 सेशन JSON फ़ाइलें",
        "cancelled": "🚫 रूपांतरण रद्द कर दिया गया।",
        "more": "\n<i>... और {count} और</i>",
    },
    "ur": {
        "converting": "⏳ سیشن JSON فائلیں بن رہی ہیں...",
        "title": "📝 <b>سیشن → Json رپورٹ</b>",
        "summary": "📦 کل: {total} | ✅ فعال: {active} | ⚠️ غلط(تبدیل شدہ): {invalid} | ❌ ناکام: {failed}",
        "no_output": "❌ کوئی سیشن JSON فائل نہیں بن سکی۔",
        "btn_total": "کل",
        "btn_converted": "تبدیل شدہ",
        "btn_failed": "ناکام",
        "btn_retry": "دوبارہ چلائیں",
        "btn_home": "ہوم",
        "caption": "📝 سیشن JSON فائلیں",
        "cancelled": "🚫 تبدیلی منسوخ کر دی گئی۔",
        "more": "\n<i>... اور مزید {count}</i>",
    },
    "ar": {
        "converting": "⏳ جارٍ إنشاء ملفات JSON للجلسات...",
        "title": "📝 <b>تقرير الجلسة → Json</b>",
        "summary": "📦 الإجمالي: {total} | ✅ نشط: {active} | ⚠️ غير صالح(محوّل): {invalid} | ❌ فشل: {failed}",
        "no_output": "❌ تعذر إنشاء أي ملفات JSON للجلسات.",
        "btn_total": "الإجمالي",
        "btn_converted": "محوّل",
        "btn_failed": "فشل",
        "btn_retry": "إعادة تشغيل",
        "btn_home": "الرئيسية",
        "caption": "📝 ملفات JSON للجلسات",
        "cancelled": "🚫 تم إلغاء التحويل.",
        "more": "\n<i>... و {count} أخرى</i>",
    },
    "zh": {
        "converting": "⏳ 正在创建会话 JSON 文件...",
        "title": "📝 <b>会话 → Json 报告</b>",
        "summary": "📦 总计: {total} | ✅ 活跃: {active} | ⚠️ 无效(已转换): {invalid} | ❌ 失败: {failed}",
        "no_output": "❌ 无法创建会话 JSON 文件。",
        "btn_total": "总计",
        "btn_converted": "已转换",
        "btn_failed": "失败",
        "btn_retry": "再次运行",
        "btn_home": "首页",
        "caption": "📝 会话 JSON 文件",
        "cancelled": "🚫 转换已取消。",
        "more": "\n<i>... 还有 {count} 个</i>",
    },
}

FILE_MERGE_PROMPTS = {
    "en": (
        "🔀 <b>File Merge</b>\n\n"
        "Send a <code>.session</code> file or <code>.zip</code>."
    ),
    "bn": (
        "🔀 <b>ফাইল একত্রীকরণ</b>\n\n"
        "একটি <code>.session</code> ফাইল বা <code>.zip</code> পাঠান।"
    ),
    "hi": (
        "🔀 <b>फ़ाइल विलय (Merge)</b>\n\n"
        "एक <code>.session</code> फ़ाइल या <code>.zip</code> भेजें।"
    ),
    "ur": (
        "🔀 <b>فائل ضم (Merge)</b>\n\n"
        "ایک <code>.session</code> فائل یا <code>.zip</code> بھیجیں۔"
    ),
    "ar": (
        "🔀 <b>دمج الملفات</b>\n\nأرسل ملف <code>.session</code> أو <code>.zip</code>."
    ),
    "zh": (
        "🔀 <b>文件合并</b>\n\n发送 <code>.session</code> 文件或 <code>.zip</code>。"
    ),
}

FILE_MERGE_MESSAGES = {
    "en": {
        "choose_type": "🔀 <b>Choose file merge type</b>\n\n📦 Found <b>{count}</b> sessions",
        "btn_multi_type": "Merge Multi-Type",
        "btn_session_json_tdata": "Merge Session+Json+Tdata",
        "btn_cancel": "Cancel",
        "multi_type_done": "✅ <b>Merge complete!</b>\n\n📦 Merged <code>{merged}</code> sessions",
        "session_json_tdata_done": "📦 <b>Merge Session+Json+Tdata Report</b>\n\n✅ Success: {success} ❌ Failed: {failed}",
        "caption_multi_type": "🔀 Merged Sessions",
        "caption_session_json_tdata": "📦 Session+Json+Tdata",
        "no_sessions": "❌ No valid session or tdata files found.",
        "processing": "⏳ Processing file merge...",
        "btn_total": "Total",
        "btn_merged": "Merged",
        "btn_error": "Error",
    },
    "bn": {
        "choose_type": "🔀 <b>ফাইল একত্রীকরণের ধরন চয়ন করুন</b>\n\n📦 পাওয়া গেছে <b>{count}</b> সেশন",
        "btn_multi_type": "Merge Multi-Type",
        "btn_session_json_tdata": "Merge Session+Json+Tdata",
        "btn_cancel": "বাতিল",
        "multi_type_done": "✅ <b>একত্রীকরণ সম্পন্ন!</b>\n\n📦 একত্রীভূত <code>{merged}</code> সেশন",
        "session_json_tdata_done": "📦 <b>Merge Session+Json+Tdata রিপোর্ট</b>\n\n✅ সফল: {success} ❌ ব্যর্থ: {failed}",
        "caption_multi_type": "🔀 Merged Sessions",
        "caption_session_json_tdata": "📦 Session+Json+Tdata",
        "no_sessions": "❌ কোনো বৈধ সেশন বা tdata ফাইল পাওয়া যায়নি।",
        "processing": "⏳ ফাইল একত্রীকরণ প্রক্রিয়াকরণ চলছে...",
        "btn_total": "মোট",
        "btn_merged": "একত্রীভূত",
        "btn_error": "ত্রুটি",
    },
    "hi": {
        "choose_type": "🔀 <b>फ़ाइल विलय प्रकार चुनें</b>\n\n📦 मिले <b>{count}</b> सेशन",
        "btn_multi_type": "Merge Multi-Type",
        "btn_session_json_tdata": "Merge Session+Json+Tdata",
        "btn_cancel": "रद्द करें",
        "multi_type_done": "✅ <b>विलय पूर्ण!</b>\n\n📦 विलीन <code>{merged}</code> सेशन",
        "session_json_tdata_done": "📦 <b>Merge Session+Json+Tdata रिपोर्ट</b>\n\n✅ सफल: {success} ❌ विफल: {failed}",
        "caption_multi_type": "🔀 Merged Sessions",
        "caption_session_json_tdata": "📦 Session+Json+Tdata",
        "no_sessions": "❌ कोई वैध सेशन या tdata फ़ाइल नहीं मिली।",
        "processing": "⏳ फ़ाइल विलय संसाधित हो रहा है...",
        "btn_total": "कुल",
        "btn_merged": "विलीन",
        "btn_error": "त्रुटि",
    },
    "ur": {
        "choose_type": "🔀 <b>فائل ضم کی قسم منتخب کریں</b>\n\n📦 مل گئے <b>{count}</b> سیشن",
        "btn_multi_type": "Merge Multi-Type",
        "btn_session_json_tdata": "Merge Session+Json+Tdata",
        "btn_cancel": "منسوخ کریں",
        "multi_type_done": "✅ <b>ضم مکمل!</b>\n\n📦 ضم شدہ <code>{merged}</code> سیشن",
        "session_json_tdata_done": "📦 <b>Merge Session+Json+Tdata رپورٹ</b>\n\n✅ کامیاب: {success} ❌ ناکام: {failed}",
        "caption_multi_type": "🔀 Merged Sessions",
        "caption_session_json_tdata": "📦 Session+Json+Tdata",
        "no_sessions": "❌ کوئی بھی درست سیشن یا tdata فائل نہیں ملی۔",
        "processing": "⏳ فائل ضم عمل جاری ہے...",
        "btn_total": "کل",
        "btn_merged": "ضم شدہ",
        "btn_error": "خرابی",
    },
    "ar": {
        "choose_type": "🔀 <b>اختر نوع دمج الملفات</b>\n\n📦 تم العثور على <b>{count}</b> جلسة",
        "btn_multi_type": "Merge Multi-Type",
        "btn_session_json_tdata": "Merge Session+Json+Tdata",
        "btn_cancel": "إلغاء",
        "multi_type_done": "✅ <b>اكتمل الدمج!</b>\n\n📦 تم دمج <code>{merged}</code> جلسات",
        "session_json_tdata_done": "📦 <b>تقرير Merge Session+Json+Tdata</b>\n\n✅ نجاح: {success} ❌ فشل: {failed}",
        "caption_multi_type": "🔀 Merged Sessions",
        "caption_session_json_tdata": "📦 Session+Json+Tdata",
        "no_sessions": "❌ لم يتم العثور على ملفات جلسات أو tdata صالحة.",
        "processing": "⏳ جارٍ معالجة دمج الملفات...",
        "btn_total": "الإجمالي",
        "btn_merged": "المدمجة",
        "btn_error": "الخطأ",
    },
    "zh": {
        "choose_type": "🔀 <b>选择文件合并类型</b>\n\n📦 找到 <b>{count}</b> 个会话",
        "btn_multi_type": "Merge Multi-Type",
        "btn_session_json_tdata": "Merge Session+Json+Tdata",
        "btn_cancel": "取消",
        "multi_type_done": "✅ <b>合并完成！</b>\n\n📦 已合并 <code>{merged}</code> 个会话",
        "session_json_tdata_done": "📦 <b>Merge Session+Json+Tdata 报告</b>\n\n✅ 成功: {success} ❌ 失败: {failed}",
        "caption_multi_type": "🔀 Merged Sessions",
        "caption_session_json_tdata": "📦 Session+Json+Tdata",
        "no_sessions": "❌ 未找到有效的会话或 tdata 文件。",
        "processing": "⏳ 正在处理文件合并...",
        "btn_total": "总计",
        "btn_merged": "已合并",
        "btn_error": "错误",
    },
}


MASS_MESSAGE_PROMPTS = {
    "en": (
        "📨 <b>Mass Message Tool</b>\n\n"
        "Send a <code>.session</code> file or <code>.zip</code> containing your Telegram accounts."
    ),
    "bn": (
        "📨 <b>গণ বার্তা সরঞ্জাম (Mass Message)</b>\n\n"
        "আপনার টেলিগ্রাম অ্যাকাউন্ট সম্বলিত <code>.session</code> বা <code>.zip</code> ফাইল পাঠান।"
    ),
    "hi": (
        "📨 <b>सामूहिक संदेश उपकरण (Mass Message)</b>\n\n"
        "अपने टेलीग्राम खातों वाली <code>.session</code> या <code>.zip</code> फ़ाइल भेजें।"
    ),
    "ur": (
        "📨 <b>ماس میسج ٹول (Mass Message)</b>\n\n"
        "اپنے ٹیلی گرام اکاؤنٹس پر مشتمل <code>.session</code> یا <code>.zip</code> فائل بھیجیں۔"
    ),
    "ar": (
        "📨 <b>أداة إرسال الرسائل الجماعية (Mass Message)</b>\n\n"
        "أرسل ملف <code>.session</code> أو <code>.zip</code> يحتوي على حسابات التليجرام الخاصة بك."
    ),
    "zh": (
        "📨 <b>群发消息工具 (Mass Message)</b>\n\n"
        "发送包含您 Telegram 账户的 <code>.session</code> 或 <code>.zip</code> 文件。"
    ),
}

MASS_MESSAGE_MESSAGES = {
    "en": {
        "upload_recipients": "👥 <b>Choose Recipients Source</b>\n\nSend a TXT or CSV file containing usernames, user IDs, or phone numbers, or select saved contacts.",
        "btn_use_contacts": "📇 Use Account Contacts",
        "btn_cancel": "❌ Cancel",
        "enter_content": "📝 <b>Enter Message Content</b>\n\nSend text message, photo, video, or document (with optional caption).",
        "select_delay": "⏱ <b>Select Message Delay Range</b>\n\nChoose safety interval between sent messages:",
        "btn_delay_fast": "⚡ 10 - 20 sec",
        "btn_delay_balanced": "⚖️ 20 - 60 sec (Recommended)",
        "btn_delay_safe": "🛡️ 60 - 120 sec (Safest)",
        "preview_title": "📋 <b>Mass Message Preview & Confirmation</b>\n\n📱 Sessions: <b>{sessions}</b>\n👥 Recipients: <b>{recipients}</b>\n⏱ Delay Range: <b>{delay}</b>\n\nReady to start sending?",
        "btn_start": "🚀 Start Mass Message",
        "live_progress": (
            "📨 <b>Mass Message Execution</b>\n\n"
            "Progress: <b>{progress} / {total}</b> ({percentage}%)\n"
            "✅ Sent: <b>{sent}</b>\n"
            "❌ Failed: <b>{failed}</b>\n"
            "⏭ Skipped: <b>{skipped}</b>\n"
            "⏳ Remaining: <b>{remaining}</b>\n\n"
            "Status: <b>{status_text}</b>"
        ),
        "btn_pause": "⏸ Pause",
        "btn_resume": "▶️ Resume",
        "btn_stop": "⛔ Stop",
        "status_running": "🟢 Running",
        "status_paused": "🟡 Paused",
        "status_pausing": "🟡 Pausing after current message...",
        "status_stopped": "🔴 Stopped",
        "status_completed": "✅ Completed",
        "no_sessions": "❌ No valid session files found.",
        "no_recipients": "❌ No valid recipients found in the file or contacts.",
        "export_caption": "📊 Mass Message Summary Report",
        "already_active": "⚠️ You already have an active mass messaging job running.",
        "not_paused": "❌ This job is not paused anymore.",
        "sessions_missing": "❌ Session files are missing; the job remains paused.",
    },
    "bn": {
        "upload_recipients": "👥 <b>প্রাপকদের উৎস নির্বাচন করুন</b>\n\nব্যবহারকারীর নাম, আইডি বা ফোন নম্বর সম্বলিত TXT বা CSV ফাইল পাঠান বা পরিচিতি নির্বাচন করুন।",
        "btn_use_contacts": "📇 অ্যাকাউন্টের পরিচিতি ব্যবহার করুন",
        "btn_cancel": "❌ বাতিল",
        "enter_content": "📝 <b>বার্তা বিষয়বস্তু লিখুন</b>\n\nটেক্সট, ফটো, ভিডিও বা ডকুমেন্ট পাঠান।",
        "select_delay": "⏱ <b>বার্তার বিলম্ব পরিসীমা বেছে নিন</b>",
        "btn_delay_fast": "⚡ ১০ - ২০ সেকেন্ড",
        "btn_delay_balanced": "⚖️ ২০ - ৬০ সেকেন্ড (সুপারিশকৃত)",
        "btn_delay_safe": "🛡️ ৬০ - ১২০ সেকেন্ড (নিরাপদ)",
        "preview_title": "📋 <b>গণ বার্তার পূর্বরূপ ও নিশ্চিতকরণ</b>\n\n📱 সেশন: <b>{sessions}</b>\n👥 প্রাপক: <b>{recipients}</b>\n⏱ বিলম্ব: <b>{delay}</b>",
        "btn_start": "🚀 বার্তা পাঠানো শুরু করুন",
        "live_progress": (
            "📨 <b>গণ বার্তা সম্পাদন</b>\n\n"
            "অগ্রগতি: <b>{progress} / {total}</b> ({percentage}%)\n"
            "✅ পাঠানো হয়েছে: <b>{sent}</b>\n"
            "❌ ব্যর্থ: <b>{failed}</b>\n"
            "⏭ এড়িয়ে গেছে: <b>{skipped}</b>\n"
            "⏳ অবশিষ্ট: <b>{remaining}</b>\n\n"
            "অবস্থা: <b>{status_text}</b>"
        ),
        "btn_pause": "⏸ বিরতি",
        "btn_resume": "▶️ পুনরায় শুরু",
        "btn_stop": "⛔ থামান",
        "status_running": "🟢 চলছে",
        "status_paused": "🟡 স্থগিত",
        "status_pausing": "🟡 বর্তমান বার্তার পর স্থগিত করা হচ্ছে...",
        "status_stopped": "🔴 থামানো হয়েছে",
        "status_completed": "✅ সম্পন্ন",
        "no_sessions": "❌ কোনো বৈধ সেশন ফাইল পাওয়া যায়নি।",
        "no_recipients": "❌ কোনো বৈধ প্রাপক পাওয়া যায়নি।",
        "export_caption": "📊 গণ বার্তার সারাংশ রিপোর্ট",
        "already_active": "⚠️ আপনার একটি সক্রিয় গণ বার্তা কাজ চলছে।",
        "not_paused": "❌ এই কাজটি আর স্থগিত নেই।",
        "sessions_missing": "❌ সেশন ফাইল পাওয়া যায়নি; কাজটি স্থগিত থাকবে।",
    },
    "hi": {
        "upload_recipients": "👥 <b>प्राप्तकर्ता स्रोत चुनें</b>\n\nउपयोगकर्ता नाम, आईडी या फोन नंबर वाली TXT या CSV फ़ाइल भेजें या सहेजे गए संपर्कों को चुनें।",
        "btn_use_contacts": "📇 खाता संपर्कों का उपयोग करें",
        "btn_cancel": "❌ रद्द करें",
        "enter_content": "📝 <b>संदेश सामग्री दर्ज करें</b>\n\nपाठ संदेश, फ़ोटो, वीडियो या दस्तावेज़ भेजें।",
        "select_delay": "⏱ <b>संदेश विलंब सीमा चुनें</b>",
        "btn_delay_fast": "⚡ 10 - 20 सेकंड",
        "btn_delay_balanced": "⚖️ 20 - 60 सेकंड (अनुशंसित)",
        "btn_delay_safe": "🛡️ 60 - 120 सेकंड (सुरक्षित)",
        "preview_title": "📋 <b>सामूहिक संदेश पूर्वावलोकन और पुष्टि</b>\n\n📱 सत्र: <b>{sessions}</b>\n👥 प्राप्तकर्ता: <b>{recipients}</b>\n⏱ विलंब: <b>{delay}</b>",
        "btn_start": "🚀 संदेश भेजना शुरू करें",
        "live_progress": (
            "📨 <b>सामूहिक संदेश निष्पादन</b>\n\n"
            "प्रगति: <b>{progress} / {total}</b> ({percentage}%)\n"
            "✅ भेजा गया: <b>{sent}</b>\n"
            "❌ विफल: <b>{failed}</b>\n"
            "⏭ छोड़ दिया: <b>{skipped}</b>\n"
            "⏳ शेष: <b>{remaining}</b>\n\n"
            "स्थिति: <b>{status_text}</b>"
        ),
        "btn_pause": "⏸ रोकें",
        "btn_resume": "▶️ फिर शुरू करें",
        "btn_stop": "⛔ बंद करें",
        "status_running": "🟢 जारी है",
        "status_paused": "🟡 रुका हुआ",
        "status_pausing": "🟡 वर्तमान संदेश के बाद रोका जा रहा है...",
        "status_stopped": "🔴 रोक दिया गया",
        "status_completed": "✅ पूरा हुआ",
        "no_sessions": "❌ कोई वैध सत्र फ़ाइल नहीं मिली।",
        "no_recipients": "❌ कोई वैध प्राप्तकर्ता नहीं मिला।",
        "export_caption": "📊 सामूहिक संदेश सारांश रिपोर्ट",
        "already_active": "⚠️ आपके पास पहले से ही एक सक्रिय कार्य चल रहा है।",
        "not_paused": "❌ यह कार्य अब रुका हुआ नहीं है।",
        "sessions_missing": "❌ सत्र फ़ाइलें नहीं मिलीं; कार्य रुका रहेगा।",
    },
    "ur": {
        "upload_recipients": "👥 <b>وصول کنندگان کا ذریعہ منتخب کریں</b>\n\nیوزر نیم، آئی ڈی یا فون نمبر والی TXT یا CSV فائل بھیجیں یا محفوظ شدہ رابطے منتخب کریں۔",
        "btn_use_contacts": "📇 اکاؤنٹ کے رابطے استعمال کریں",
        "btn_cancel": "❌ منسوخ کریں",
        "enter_content": "📝 <b>پیغام کا مواد درج کریں</b>\n\nمتن، تصویر، ویڈیو یا فائل بھیجیں۔",
        "select_delay": "⏱ <b>پیغام تاخیر کی حد منتخب کریں</b>",
        "btn_delay_fast": "⚡ 10 - 20 سیکنڈ",
        "btn_delay_balanced": "⚖️ 20 - 60 سیکنڈ (تجویز کردہ)",
        "btn_delay_safe": "🛡️ 60 - 120 سیکنڈ (محفوظ ترین)",
        "preview_title": "📋 <b>ماس میسج پیش نظارہ اور تصدیق</b>\n\n📱 سیشنز: <b>{sessions}</b>\n👥 وصول کنندگان: <b>{recipients}</b>\n⏱ تاخیر: <b>{delay}</b>",
        "btn_start": "🚀 پیغام بھیجنا شروع کریں",
        "live_progress": (
            "📨 <b>ماس میسج پروسیسنگ</b>\n\n"
            "پیش رفت: <b>{progress} / {total}</b> ({percentage}%)\n"
            "✅ بھیج دیا: <b>{sent}</b>\n"
            "❌ ناکام: <b>{failed}</b>\n"
            "⏭ چھوڑ دیا: <b>{skipped}</b>\n"
            "⏳ باقی: <b>{remaining}</b>\n\n"
            "حالت: <b>{status_text}</b>"
        ),
        "btn_pause": "⏸ وقفہ",
        "btn_resume": "▶️ دوبارہ شروع کریں",
        "btn_stop": "⛔ روک دیں",
        "status_running": "🟢 جاری ہے",
        "status_paused": "🟡 روکا گیا",
        "status_pausing": "🟡 موجودہ پیغام کے بعد روکا جا رہا ہے...",
        "status_stopped": "🔴 روک دیا گیا",
        "status_completed": "✅ مکمل",
        "no_sessions": "❌ کوئی درست سیشن فائل نہیں ملی۔",
        "no_recipients": "❌ کوئی درست وصول کنندہ نہیں ملا۔",
        "export_caption": "📊 ماس میسج خلاصہ رپورٹ",
        "already_active": "⚠️ آپ کا ایک فعال کام پہلے سے چل رہا ہے۔",
        "not_paused": "❌ یہ کام اب روکا ہوا نہیں ہے۔",
        "sessions_missing": "❌ سیشن فائلیں نہیں ملیں؛ کام روکا رہے گا۔",
    },
    "ar": {
        "upload_recipients": "👥 <b>اختر مصدر المستلمين</b>\n\nأرسل ملف TXT أو CSV يحتوي على أسماء المستخدمين أو المعرفات أو أرقام الهواتف.",
        "btn_use_contacts": "📇 استخدام جهات اتصال الحساب",
        "btn_cancel": "❌ إلغاء",
        "enter_content": "📝 <b>أدخل محتوى الرسالة</b>\n\nأرسل نصًا أو صورة أو فيديو أو مستندًا.",
        "select_delay": "⏱ <b>حدد نطاق التأخير</b>",
        "btn_delay_fast": "⚡ 10 - 20 ثانية",
        "btn_delay_balanced": "⚖️ 20 - 60 ثانية (موصى به)",
        "btn_delay_safe": "🛡️ 60 - 120 ثانية (الأكثر أمانًا)",
        "preview_title": "📋 <b>معاينة وتأكيد الرسائل الجماعية</b>\n\n📱 الجلسات: <b>{sessions}</b>\n👥 المستلمون: <b>{recipients}</b>\n⏱ التأخير: <b>{delay}</b>",
        "btn_start": "🚀 بدء إرسال الرسائل الجماعية",
        "live_progress": (
            "📨 <b>تنفيذ الرسائل الجماعية</b>\n\n"
            "التقدم: <b>{progress} / {total}</b> ({percentage}%)\n"
            "✅ تم الإرسال: <b>{sent}</b>\n"
            "❌ فشل: <b>{failed}</b>\n"
            "⏭ تم التخطي: <b>{skipped}</b>\n"
            "⏳ المتبقي: <b>{remaining}</b>\n\n"
            "الحالة: <b>{status_text}</b>"
        ),
        "btn_pause": "⏸ إيقاف مؤقت",
        "btn_resume": "▶️ استئناف",
        "btn_stop": "⛔ إيقاف",
        "status_running": "🟢 قيد التشغيل",
        "status_paused": "🟡 متوقف مؤقتًا",
        "status_pausing": "🟡 جارٍ الإيقاف المؤقت بعد الرسالة الحالية...",
        "status_stopped": "🔴 متوقف",
        "status_completed": "✅ مكتمل",
        "no_sessions": "❌ لم يتم العثور على ملفات جلسات صالحة.",
        "no_recipients": "❌ لم يتم العثور على مستلمين صالحين.",
        "export_caption": "📊 تقرير ملخص الرسائل الجماعية",
        "already_active": "⚠️ لديك مهمة نشطة قيد التشغيل بالفعل.",
        "not_paused": "❌ هذه المهمة لم تعد متوقفة.",
        "sessions_missing": "❌ ملفات الجلسة مفقودة؛ ستبقى المهمة متوقفة.",
    },
    "zh": {
        "upload_recipients": "👥 <b>选择接收者来源</b>\n\n发送包含用户名、用户 ID 或电话号码的 TXT 或 CSV 文件，或选择保存的联系人。",
        "btn_use_contacts": "📇 使用账户联系人",
        "btn_cancel": "❌ 取消",
        "enter_content": "📝 <b>输入消息内容</b>\n\n发送文本消息、照片、视频或文档。",
        "select_delay": "⏱ <b>选择消息延迟范围</b>",
        "btn_delay_fast": "⚡ 10 - 20 秒",
        "btn_delay_balanced": "⚖️ 20 - 60 秒（推荐）",
        "btn_delay_safe": "🛡️ 60 - 120 秒（最安全）",
        "preview_title": "📋 <b>群发消息预览与确认</b>\n\n📱 会话: <b>{sessions}</b>\n👥 接收者: <b>{recipients}</b>\n⏱ 延迟范围: <b>{delay}</b>",
        "btn_start": "🚀 开始群发消息",
        "live_progress": (
            "📨 <b>群发消息执行</b>\n\n"
            "进度: <b>{progress} / {total}</b> ({percentage}%)\n"
            "✅ 已发送: <b>{sent}</b>\n"
            "❌ 失败: <b>{failed}</b>\n"
            "⏭ 已跳过: <b>{skipped}</b>\n"
            "⏳ 剩余: <b>{remaining}</b>\n\n"
            "状态: <b>{status_text}</b>"
        ),
        "btn_pause": "⏸ 暂停",
        "btn_resume": "▶️ 恢复",
        "btn_stop": "⛔ 停止",
        "status_running": "🟢 运行中",
        "status_paused": "🟡 已暂停",
        "status_pausing": "🟡 当前消息发送后将暂停...",
        "status_stopped": "🔴 已停止",
        "status_completed": "✅ 已完成",
        "no_sessions": "❌ 未找到有效的会话文件。",
        "no_recipients": "❌ 未找到有效的接收者。",
        "export_caption": "📊 群发消息摘要报告",
        "already_active": "⚠️ 您已有一个运行中的任务。",
        "not_paused": "❌ 该任务不再处于暂停状态。",
        "sessions_missing": "❌ 会话文件缺失；任务保持暂停。",
    },
}


def get_locale(lang: str) -> Locale:
    return LANGUAGES.get(lang, LANGUAGES["en"])


def menu_labels(lang: str) -> tuple[str, ...]:
    return MENU_LABELS.get(lang, MENU_LABELS["en"])


def action_message(lang: str, idx: int) -> str:
    msgs = ACTION_MESSAGES.get(lang, ACTION_MESSAGES["en"])
    if 0 <= idx < len(msgs):
        return msgs[idx]
    return msgs[0]


VIP_RESTRICTED_MESSAGES = {
    "en": (
        "🔒 <b>VIP Access Required</b>\n\n"
        "This feature is restricted to VIP members.\n"
        "Please select a subscription plan below to upgrade your account:"
    ),
    "bn": (
        "🔒 <b>VIP অ্যাক্সেস প্রয়োজন</b>\n\n"
        "এই সুবিধাটি শুধুমাত্র VIP সদস্যদের জন্য সংরক্ষিত।\n"
        "আপনার অ্যাকাউন্ট আপগ্রেড করতে নিচে একটি প্ল্যান নির্বাচন করুন:"
    ),
    "hi": (
        "🔒 <b>VIP एक्सेस आवश्यक</b>\n\n"
        "यह सुविधा केवल VIP सदस्यों के लिए सीमित है।\n"
        "अपने खाते को अपग्रेड करने के लिए नीचे दिए गए प्लान का चयन करें:"
    ),
    "ur": (
        "🔒 <b>VIP رسائی درکار ہے</b>\n\n"
        "یہ خصوصیت صرف VIP اراکین کے لیے مخصوص ہے۔\n"
        "اپنے اکاؤنٹ کو اپ گریڈ کرنے کے لیے نیچے دیے گئے پلان کو منتخب کریں:"
    ),
    "ar": (
        "🔒 <b>مطلوب اشتراك VIP</b>\n\n"
        "هذه الميزة مقتصرة على أعضاء VIP.\n"
        "يرجى اختيار إحدى الخطط أدناه لترقية حسابك:"
    ),
    "zh": (
        "🔒 <b>需要 VIP 权限</b>\n\n"
        "此功能仅限 VIP 会员使用。\n"
        "请在下方选择一个方案以升级您的账户："
    ),
}

FEATURE_DISABLED_MESSAGES = {
    "en": "⚠️ <b>Feature Disabled</b>\n\nThis tool is currently disabled by administrator.",
    "bn": "⚠️ <b>ফিচারটি নিষ্ক্রিয়</b>\n\nএই টুলটি বর্তমানে এডমিন দ্বারা নিষ্ক্রিয় করা হয়েছে।",
    "hi": "⚠️ <b>सुविधा निष्क्रिय</b>\n\nयह टूल वर्तमान में एडमिन द्वारा निष्क्रिय किया गया है।",
    "ur": "⚠️ <b>خصوصیت غیر فعال ہے</b>\n\nیہ ٹول فی الحال ایڈمن کی طرف سے غیر فعال کر دیا گیا ہے۔",
    "ar": "⚠️ <b>الميزة معطلة</b>\n\nهذه الأداة معطلة حالياً من قبل المشرف。",
    "zh": "⚠️ <b>功能已禁用</b>\n\n该工具目前已被管理员禁用。",
}

VIP_STATUS_LABELS = {
    "en": {"vip": "💎 Active VIP Member", "free": "⚪ Free Plan"},
    "bn": {"vip": "💎 সক্রিয় VIP সদস্য", "free": "⚪ ফ্রি প্ল্যান"},
    "hi": {"vip": "💎 सक्रिय VIP सदस्य", "free": "⚪ मुफ़्त प्लान"},
    "ur": {"vip": "💎 فعال VIP ممبر", "free": "⚪ مفت پلان"},
    "ar": {"vip": "💎 عضو VIP نشط", "free": "⚪ خطة مجانية"},
    "zh": {"vip": "💎 VIP 尊享会员", "free": "⚪ 免费版"},
}

VIP_CENTER_MESSAGES = {
    "en": (
        "💎 <b>VIP Subscription Center</b>\n\n"
        "Current Status: <b>{status}</b>\n\n"
        "<b>VIP Benefits:</b>\n"
        "• Unlimited Fast File Conversions\n"
        "• High Priority Server Queue\n"
        "• Advanced Telethon Features\n\n"
        "Select a subscription plan below to upgrade:"
    ),
    "bn": (
        "💎 <b>VIP সাবস্ক্রিপশন সেন্টার</b>\n\n"
        "বর্তমান স্ট্যাটাস: <b>{status}</b>\n\n"
        "<b>VIP সুবিধাসমূহ:</b>\n"
        "• আনলিমিটেড দ্রুত ফাইল কনভার্সন\n"
        "• হাই প্রায়োরিটি সার্ভার কিউ\n"
        "• অ্যাডভান্সড Telethon ফিচারস\n\n"
        "আপগ্রেড করতে নিচে একটি সাবস্ক্রিপশন প্ল্যান নির্বাচন করুন:"
    ),
    "hi": (
        "💎 <b>VIP सब्सक्रिप्शन सेंटर</b>\n\n"
        "वर्तमान स्थिति: <b>{status}</b>\n\n"
        "<b>VIP लाभ:</b>\n"
        "• असीमित तेज़ फ़ाइल रूपांतरण\n"
        "• उच्च प्राथमिकता सर्वर कतार\n"
        "• उन्नत Telethon सुविधाएँ\n\n"
        "अपग्रेड करने के लिए नीचे एक सदस्यता योजना चुनें:"
    ),
    "ur": (
        "💎 <b>VIP سبسکرپشن سینٹر</b>\n\n"
        "موجودہ حیثیت: <b>{status}</b>\n\n"
        "<b>VIP فوائد:</b>\n"
        "• لامحدود تیز فائل کی تبدیلیاں\n"
        "• اعلی ترجیحی سرور قطار\n"
        "• اعلی درجے کی Telethon خصوصیات\n\n"
        "اپ گریڈ کرنے کے لیے نیچے دیے گئے پلان کا انتخاب کریں:"
    ),
    "ar": (
        "💎 <b>مركز اشتراك VIP</b>\n\n"
        "الحالة الحالية: <b>{status}</b>\n\n"
        "<b>مزايا VIP:</b>\n"
        "• تحويلات ملفات سريعة غير محدودة\n"
        "• قائمة انتظار سيرفر ذات أولوية عالية\n"
        "• ميزات Telethon متقدمة\n\n"
        "اختر خطة الاشتراك أدناه للترقية:"
    ),
    "zh": (
        "💎 <b>VIP 订阅中心</b>\n\n"
        "当前状态：<b>{status}</b>\n\n"
        "<b>VIP 权益：</b>\n"
        "• 无限快速文件转换\n"
        "• 高优先级服务器队列\n"
        "• 高级 Telethon 功能\n\n"
        "请在下方选择订阅方案以升级："
    ),
}

VIP_CHECKOUT_MESSAGES = {
    "en": (
        "💳 <b>Checkout — {name}</b>\n\n"
        "<b>Amount:</b> <code>{price} {currency}</code>\n"
        "<b>Duration:</b> <code>{months} Month(s)</code>\n\n"
        "<b>Available Payment Methods:</b>\n"
        "• <b>TRC20 USDT:</b> <code>{trc20}</code>\n"
        "• <b>BEP20 USDT:</b> <code>{bep20}</code>\n"
        "• <b>Binance Pay ID:</b> <code>{binance}</code>\n\n"
        "📥 <b>Next Step:</b> Transfer exact amount to any address above, then send your <b>Transaction Hash / Photo Receipt</b> here:"
    ),
    "bn": (
        "💳 <b>চেকআউট — {name}</b>\n\n"
        "<b>পরিমাণ:</b> <code>{price} {currency}</code>\n"
        "<b>মেয়াদ:</b> <code>{months} মাস</code>\n\n"
        "<b>উপলব্ধ পেমেন্ট পদ্ধতি:</b>\n"
        "• <b>TRC20 USDT:</b> <code>{trc20}</code>\n"
        "• <b>BEP20 USDT:</b> <code>{bep20}</code>\n"
        "• <b>Binance Pay ID:</b> <code>{binance}</code>\n\n"
        "📥 <b>পরবর্তী পদক্ষেপ:</b> উপরের যেকোনো ঠিকানায় সঠিক পরিমাণ অর্থ পাঠান, তারপর আপনার <b>ট্রানজিশন হ্যাশ / ফটো রসিদ</b> এখানে পাঠান:"
    ),
    "hi": (
        "💳 <b>चेकआउट — {name}</b>\n\n"
        "<b>राशि:</b> <code>{price} {currency}</code>\n"
        "<b>अवधि:</b> <code>{months} महीने</code>\n\n"
        "<b>उपलब्ध भुगतान विधियाँ:</b>\n"
        "• <b>TRC20 USDT:</b> <code>{trc20}</code>\n"
        "• <b>BEP20 USDT:</b> <code>{bep20}</code>\n"
        "• <b>Binance Pay ID:</b> <code>{binance}</code>\n\n"
        "📥 <b>अगला कदम:</b> ऊपर दिए गए किसी भी पते पर सटीक राशि स्थानांतरित करें, फिर अपना <b>लेनदेन हैश / रसीद की फोटो</b> यहाँ भेजें:"
    ),
    "ur": (
        "💳 <b>چیک آؤٹ — {name}</b>\n\n"
        "<b>رقم:</b> <code>{price} {currency}</code>\n"
        "<b>مدت:</b> <code>{months} ماہ</code>\n\n"
        "<b>دستیاب ادائیگی کے طریقے:</b>\n"
        "• <b>TRC20 USDT:</b> <code>{trc20}</code>\n"
        "• <b>BEP20 USDT:</b> <code>{bep20}</code>\n"
        "• <b>Binance Pay ID:</b> <code>{binance}</code>\n\n"
        "📥 <b>اگلا قدم:</b> اوپر دیے گئے کسی بھی پتے پر دقیق رقم منتقل کریں، پھر اپنی <b>رست کی تصویر / ٹرانزیکشن ہیش</b> یہاں بھیجیں:"
    ),
    "ar": (
        "💳 <b>الدفع — {name}</b>\n\n"
        "<b>المبلغ:</b> <code>{price} {currency}</code>\n"
        "<b>المدة:</b> <code>{months} شهر</code>\n\n"
        "<b>طرق الدفع المتاحة:</b>\n"
        "• <b>TRC20 USDT:</b> <code>{trc20}</code>\n"
        "• <b>BEP20 USDT:</b> <code>{bep20}</code>\n"
        "• <b>Binance Pay ID:</b> <code>{binance}</code>\n\n"
        "📥 <b>الخطوة التالية:</b> قم بتحويل المبلغ المحدد إلى أي عنوان أعلاه، ثم أرسل <b>رمز المعاملة (TX Hash) / صورة الإيصال</b> هنا:"
    ),
    "zh": (
        "💳 <b>结账 — {name}</b>\n\n"
        "<b>金额：</b> <code>{price} {currency}</code>\n"
        "<b>时长：</b> <code>{months} 个月</code>\n\n"
        "<b>可选支付方式：</b>\n"
        "• <b>TRC20 USDT：</b> <code>{trc20}</code>\n"
        "• <b>BEP20 USDT：</b> <code>{bep20}</code>\n"
        "• <b>Binance Pay ID：</b> <code>{binance}</code>\n\n"
        "📥 <b>下一步：</b> 转账准确金额至上述任意地址，然后在此发送您的<b>交易哈希 / 转账截图</b>："
    ),
}

VIP_PAYMENT_SUBMITTED_MESSAGES = {
    "en": (
        "✅ <b>Payment Order #{id} Submitted!</b>\n\n"
        "Our administrative team is reviewing your transaction. You will be notified immediately upon approval."
    ),
    "bn": (
        "✅ <b>পেমেন্ট অর্ডার #{id} জমাদান সম্পন্ন হয়েছে!</b>\n\n"
        "আমাদের অ্যাডমিন টিম আপনার ট্রানজিশন পর্যালোচনা করছে। অনুমোদিত হওয়া মাত্র আপনাকে জানানো হবে।"
    ),
    "hi": (
        "✅ <b>भुगतान आदेश #{id} प्रस्तुत किया गया!</b>\n\n"
        "हमारी प्रशासनिक टीम आपके लेन-देन की समीक्षा कर रही है। स्वीकृति मिलने पर आपको तुरंत सूचित किया जाएगा।"
    ),
    "ur": (
        "✅ <b>ادائیگی کا آرڈر #{id} جمع کر دیا گیا!</b>\n\n"
        "ہماری انتظامی ٹیم آپ کی ٹرانزیکشن کا جائزہ لے رہی ہے۔ منظوری کے فوراً بعد آپ کو مطلع کر دیا جائے گا۔"
    ),
    "ar": (
        "✅ <b>تم تقديم طلب الدفع رقم #{id} بنجاح!</b>\n\n"
        "فريق الإدارة يقوم بمراجعة معاملتك حالياً。سيتم إخطارك فور الموافقة عليها。"
    ),
    "zh": (
        "✅ <b>支付订单 #{id} 已提交！</b>\n\n"
        "我们的管理团队正在审核您的交易。一旦批准，您将立即收到通知。"
    ),
}

VIP_PAYMENT_METHOD_MESSAGES = {
    "en": (
        "💳 💰 <b>Make Payment</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📦 <b>Package:</b> {name}\n"
        "💵 <b>Amount:</b> {price} {currency} $\n\n"
        "👇 <b>Choose your payment method:</b>"
    ),
    "bn": (
        "💳 💰 <b>পেমেন্ট করুন</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📦 <b>প্যাকেজ:</b> {name}\n"
        "💵 <b>পরিমাণ:</b> {price} {currency} $\n\n"
        "👇 <b>আপনার পেমেন্ট পদ্ধতি বেছে নিন:</b>"
    ),
    "hi": (
        "💳 💰 <b>भुगतान करें</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📦 <b>पैकेज:</b> {name}\n"
        "💵 <b>राशि:</b> {price} {currency} $\n\n"
        "👇 <b>अपना भुगतान तरीका चुनें:</b>"
    ),
    "ur": (
        "💳 💰 <b>ادائیگی کریں</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📦 <b>پیکیج:</b> {name}\n"
        "💵 <b>رقم:</b> {price} {currency} $\n\n"
        "👇 <b>اپنے ادائیگی کا طریقہ منتخب کریں:</b>"
    ),
    "ar": (
        "💳 💰 <b>إجراء الدفع</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📦 <b>الباقة:</b> {name}\n"
        "💵 <b>المبلغ:</b> {price} {currency} $\n\n"
        "👇 <b>اختر طريقة الدفع الخاصة بك:</b>"
    ),
    "zh": (
        "💳 💰 <b>立即付款</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📦 <b>套餐：</b> {name}\n"
        "💵 <b>金额：</b> {price} {currency} $\n\n"
        "👇 <b>请选择您的支付方式：</b>"
    ),
}

PAYMENT_FLOW_LABELS = {
    "en": {
        "manual": "💳 Manual Payment",
        "auto": "🤖 Auto Payment",
        "send_screenshot": "📸 Send Screenshot",
        "check_payment": "🔄 Check Payment",
        "chain_trc20": "Auto TRC20 USDT",
        "chain_bep20": "Auto BEP20 USDT (BSC)",
    },
    "bn": {
        "manual": "💳 ম্যানুয়াল পেমেন্ট",
        "auto": "🤖 অটো পেমেন্ট",
        "send_screenshot": "📸 স্ক্রিনশট পাঠান",
        "check_payment": "🔄 পেমেন্ট চেক করুন",
        "chain_trc20": "অটো TRC20 USDT",
        "chain_bep20": "অটো BEP20 USDT (BSC)",
    },
    "hi": {
        "manual": "💳 मैनुअल भुगतान",
        "auto": "🤖 ऑटो भुगतान",
        "send_screenshot": "📸 स्क्रीनशॉट भेजें",
        "check_payment": "🔄 भुगतान जांचें",
        "chain_trc20": "ऑटो TRC20 USDT",
        "chain_bep20": "ऑटो BEP20 USDT (BSC)",
    },
    "ur": {
        "manual": "💳 دستی ادائیگی",
        "auto": "🤖 آٹو ادائیگی",
        "send_screenshot": "📸 اسکرین شاٹ بھیجیں",
        "check_payment": "🔄 ادائیگی چیک کریں",
        "chain_trc20": "آٹو TRC20 USDT",
        "chain_bep20": "آٹو BEP20 USDT (BSC)",
    },
    "ar": {
        "manual": "💳 دفع يدوي",
        "auto": "🤖 دفع تلقائي",
        "send_screenshot": "📸 إرسال لقطة شاشة",
        "check_payment": "🔄 التحقق من الدفع",
        "chain_trc20": "TRC20 USDT تلقائي",
        "chain_bep20": "BEP20 USDT تلقائي (BSC)",
    },
    "zh": {
        "manual": "💳 手动支付",
        "auto": "🤖 自动支付",
        "send_screenshot": "📸 发送截图",
        "check_payment": "🔄 检查付款",
        "chain_trc20": "自动 TRC20 USDT",
        "chain_bep20": "自动 BEP20 USDT (BSC)",
    },
}

MANUAL_PAYMENT_MESSAGES = {
    "en": (
        "💳 💰 <b>Make Payment</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📦 <b>Package:</b> {name}\n"
        "💵 <b>Amount:</b> {price} {currency} $\n\n"
        "╔══ 📋 MANUAL PAYMENT ══╗\n\n"
        "💳 <b>Binance ID:</b>\n"
        "<code>{binance}</code>\n\n"
        "💳 <b>TRC20</b> | <code>{trc20}</code>\n\n"
        "💳 <b>BEP20</b> | <code>{bep20}</code>\n\n"
        "After payment, click the button below.\n"
        "╚══════════════════════╝\n\n"
        "📸 <b>Send Screenshot</b>\n\n"
        "Please send your payment screenshot.\n\n"
        "⚠️ Only send a Photo — text messages are not accepted.\n\n"
        "📦 Package: {name}\n\n"
        "cancel."
    ),
    "bn": (
        "💳 💰 <b>পেমেন্ট করুন</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📦 <b>প্যাকেজ:</b> {name}\n"
        "💵 <b>পরিমাণ:</b> {price} {currency} $\n\n"
        "╔══ 📋 ম্যানুয়াল পেমেন্ট ══╗\n\n"
        "💳 <b>Binance ID:</b>\n"
        "<code>{binance}</code>\n\n"
        "💳 <b>TRC20</b> | <code>{trc20}</code>\n\n"
        "💳 <b>BEP20</b> | <code>{bep20}</code>\n\n"
        "পেমেন্টের পর নিচের বাটনে ক্লিক করুন।\n"
        "╚══════════════════════╝\n\n"
        "📸 <b>স্ক্রিনশট পাঠান</b>\n\n"
        "আপনার পেমেন্ট স্ক্রিনশট পাঠান।\n\n"
        "⚠️ শুধুমাত্র একটি ছবি পাঠান — টেক্সট মেসেজ গ্রহণ করা হয় না।\n\n"
        "📦 প্যাকেজ: {name}\n\n"
        "বাতিল।"
    ),
    "hi": (
        "💳 💰 <b>भुगतान करें</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📦 <b>पैकेज:</b> {name}\n"
        "💵 <b>राशि:</b> {price} {currency} $\n\n"
        "╔══ 📋 मैनुअल भुगतान ══╗\n\n"
        "💳 <b>Binance ID:</b>\n"
        "<code>{binance}</code>\n\n"
        "💳 <b>TRC20</b> | <code>{trc20}</code>\n\n"
        "💳 <b>BEP20</b> | <code>{bep20}</code>\n\n"
        "भुगतान के बाद नीचे बटन पर क्लिक करें।\n"
        "╚══════════════════════╝\n\n"
        "📸 <b>स्क्रीनशॉट भेजें</b>\n\n"
        "कृपया अपना भुगतान स्क्रीनशॉट भेजें।\n\n"
        "⚠️ केवल एक फोटो भेजें — टेक्स्ट संदेश स्वीकार नहीं किए जाते।\n\n"
        "📦 पैकेज: {name}\n\n"
        "रद्द करें।"
    ),
    "ur": (
        "💳 💰 <b>ادائیگی کریں</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📦 <b>پیکیج:</b> {name}\n"
        "💵 <b>رقم:</b> {price} {currency} $\n\n"
        "╔══ 📋 دستی ادائیگی ══╗\n\n"
        "💳 <b>Binance ID:</b>\n"
        "<code>{binance}</code>\n\n"
        "💳 <b>TRC20</b> | <code>{trc20}</code>\n\n"
        "💳 <b>BEP20</b> | <code>{bep20}</code>\n\n"
        "ادائیگی کے بعد نیچے بٹن پر کلک کریں۔\n"
        "╚══════════════════════╝\n\n"
        "📸 <b>اسکرین شاٹ بھیجیں</b>\n\n"
        "براہ کرم اپنی ادائیگی کا اسکرین شاٹ بھیجیں۔\n\n"
        "⚠️ صرف ایک تصویر بھیجیں — ٹیکسٹ میسج قبول نہیں کئے جاتے۔\n\n"
        "📦 پیکیج: {name}\n\n"
        "منسوخ کریں۔"
    ),
    "ar": (
        "💳 💰 <b>إجراء الدفع</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📦 <b>الباقة:</b> {name}\n"
        "💵 <b>المبلغ:</b> {price} {currency} $\n\n"
        "╔══ 📋 دفع يدوي ══╗\n\n"
        "💳 <b>Binance ID:</b>\n"
        "<code>{binance}</code>\n\n"
        "💳 <b>TRC20</b> | <code>{trc20}</code>\n\n"
        "💳 <b>BEP20</b> | <code>{bep20}</code>\n\n"
        "بعد الدفع، انقر على الزر أدناه.\n"
        "╚══════════════════════╝\n\n"
        "📸 <b>إرسال لقطة شاشة</b>\n\n"
        "يرجى إرسال لقطة شاشة الدفع الخاصة بك.\n\n"
        "⚠️ أرسل صورة فقط — لا يتم قبول الرسائل النصية.\n\n"
        "📦 الباقة: {name}\n\n"
        "إلغاء."
    ),
    "zh": (
        "💳 💰 <b>立即付款</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📦 <b>套餐：</b> {name}\n"
        "💵 <b>金额：</b> {price} {currency} $\n\n"
        "╔══ 📋 手动支付 ══╗\n\n"
        "💳 <b>Binance ID：</b>\n"
        "<code>{binance}</code>\n\n"
        "💳 <b>TRC20</b> | <code>{trc20}</code>\n\n"
        "💳 <b>BEP20</b> | <code>{bep20}</code>\n\n"
        "付款后，请点击下方按钮。\n"
        "╚══════════════════════╝\n\n"
        "📸 <b>发送截图</b>\n\n"
        "请发送您的付款截图。\n\n"
        "⚠️ 仅发送照片 — 文字消息不被接受。\n\n"
        "📦 套餐：{name}\n\n"
        "取消。"
    ),
}

RECEIPT_PROMPT_MESSAGES = {
    "en": (
        "📸 <b>Send Screenshot</b>\n\n"
        "Please send your payment screenshot.\n\n"
        "⚠️ Only send a <b>Photo</b> — text messages are not accepted.\n\n"
        "📦 Package: {name}\n\n"
        "cancel."
    ),
    "bn": (
        "📸 <b>স্ক্রিনশট পাঠান</b>\n\n"
        "আপনার পেমেন্ট স্ক্রিনশট পাঠান।\n\n"
        "⚠️ শুধুমাত্র একটি <b>ছবি</b> পাঠান — টেক্সট মেসেজ গ্রহণ করা হয় না।\n\n"
        "📦 প্যাকেজ: {name}\n\n"
        "বাতিল।"
    ),
    "hi": (
        "📸 <b>स्क्रीनशॉट भेजें</b>\n\n"
        "कृपया अपना भुगतान स्क्रीनशॉट भेजें।\n\n"
        "⚠️ केवल एक <b>फोटो</b> भेजें — टेक्स्ट संदेश स्वीकार नहीं किए जाते।\n\n"
        "📦 पैकेज: {name}\n\n"
        "रद्द करें।"
    ),
    "ur": (
        "📸 <b>اسکرین شاٹ بھیجیں</b>\n\n"
        "براہ کرم اپنی ادائیگی کا اسکرین شاٹ بھیجیں۔\n\n"
        "⚠️ صرف ایک <b>تصویر</b> بھیجیں — ٹیکسٹ میسج قبول نہیں کئے جاتے۔\n\n"
        "📦 پیکیج: {name}\n\n"
        "منسوخ کریں۔"
    ),
    "ar": (
        "📸 <b>إرسال لقطة شاشة</b>\n\n"
        "يرجى إرسال لقطة شاشة الدفع الخاصة بك.\n\n"
        "⚠️ أرسل <b>صورة</b> فقط — لا يتم قبول الرسائل النصية.\n\n"
        "📦 الباقة: {name}\n\n"
        "إلغاء."
    ),
    "zh": (
        "📸 <b>发送截图</b>\n\n"
        "请发送您的付款截图。\n\n"
        "⚠️ 仅发送<b>照片</b> — 不接受文字消息。\n\n"
        "📦 套餐：{name}\n\n"
        "取消。"
    ),
}

RECEIPT_INVALID_MESSAGES = {
    "en": (
        "⚠️ Only a <b>Photo</b> is accepted for payment confirmation.\n\n"
        "Please send your payment screenshot as an image — text messages are not accepted."
    ),
    "bn": (
        "⚠️ পেমেন্ট নিশ্চিত করার জন্য শুধুমাত্র একটি <b>ছবি</b> গ্রহণ করা হয়।\n\n"
        "আপনার পেমেন্ট স্ক্রিনশট ছবি হিসেবে পাঠান — টেক্সট মেসেজ গ্রহণ করা হয় না।"
    ),
    "hi": (
        "⚠️ भुगतान की पुष्टि के लिए केवल एक <b>फोटो</b> स्वीकार की जाती है।\n\n"
        "कृपया अपना भुगतान स्क्रीनशॉट छवि के रूप में भेजें — टेक्स्ट संदेश स्वीकार नहीं किए जाते।"
    ),
    "ur": (
        "⚠️ ادائیگی کی تصدیق کے لیے صرف ایک <b>تصویر</b> قبول کی جاتی ہے۔\n\n"
        "براہ کرم اپنی ادائیگی کا اسکرین شاٹ تصویر کے طور پر بھیجیں — ٹیکسٹ میسج قبول نہیں کئے جاتے۔"
    ),
    "ar": (
        "⚠️ يتم قبول <b>صورة</b> فقط للتأكد من الدفع.\n\n"
        "يرجى إرسال لقطة شاشة الدفع كصورة — لا يتم قبول الرسائل النصية."
    ),
    "zh": (
        "⚠️ 仅接受<b>照片</b>作为付款确认。\n\n"
        "请以图片形式发送您的付款截图 — 不接受文字消息。"
    ),
}

AUTO_PAYMENT_HEADER_MESSAGES = {
    "en": (
        "🤖 💰 <b>Make Payment</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📦 <b>Package:</b> {name}\n"
        "💵 <b>Base price:</b> {price} {currency} $\n"
        "⚠️ Send the <b>exact chain amount</b> shown below — the base price alone may not match\n\n"
        "╔══ 🤖 AUTO PAY SYSTEM ══╗\n"
        "{chains}"
        "╚═══════════════════════╝"
    ),
    "bn": (
        "🤖 💰 <b>পেমেন্ট করুন</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📦 <b>প্যাকেজ:</b> {name}\n"
        "💵 <b>ভিত্তি মূল্য:</b> {price} {currency} $\n"
        "👆 নীচে দেখানো <b>সঠিক চেইন পরিমাণ</b> পাঠান — শুধু ভিত্তি মূল্য মিলবে না\n\n"
        "╔══ 🤖 অটো পেমেন্ট সিস্টেম ══╗\n"
        "{chains}"
        "╚═══════════════════════╝"
    ),
    "hi": (
        "🤖 💰 <b>भुगतान करें</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📦 <b>पैकेज:</b> {name}\n"
        "💵 <b>आधार मूल्य:</b> {price} {currency} $\n"
        "👉 नीचे दिखाई गई <b>सटीक चेन राशि</b> भेजें — सिर्फ़ आधार मूल्य मेल नहीं खाएगा\n\n"
        "╔══ 🤖 ऑटो भुगतान प्रणाली ══╗\n"
        "{chains}"
        "╚═══════════════════════╝"
    ),
    "ur": (
        "🤖 💰 <b>ادائیگی کریں</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📦 <b>پیکیج:</b> {name}\n"
        "💵 <b>بنیادی قیمت:</b> {price} {currency} $\n"
        "👉 نیچے دی گئی <b>صحیح چین رقم</b> بھیجیں – صرف بنیادی قیمت مماثل نہیں ہوگی\n\n"
        "╔══ 🤖 آٹو ادائیگی نظام ══╗\n"
        "{chains}"
        "╚═══════════════════════╝"
    ),
    "ar": (
        "🤖 💰 <b>إجراء الدفع</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📦 <b>الباقة:</b> {name}\n"
        "💵 <b>السعر الأساسي:</b> {price} {currency} $\n"
        "👈 أرسل <b>المبلغ الدقيق للسلسلة</b> الموضح أدناه — السعر الأساسي وحده لن يطابق\n\n"
        "╔══ 🤖 نظام الدفع التلقائي ══╗\n"
        "{chains}"
        "╚═══════════════════════╝"
    ),
    "zh": (
        "🤖 💰 <b>立即付款</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📦 <b>套餐：</b> {name}\n"
        "💵 <b>基础价格：</b> {price} {currency} $\n"
        "👇 请发送下方显示的<b>准确链上金额</b>——仅基础价格不匹配\n\n"
        "╔══ 🤖 自动支付系统 ══╗\n"
        "{chains}"
        "╚═══════════════════════╝"
    ),
}

AUTO_PAYMENT_CHAIN_MESSAGES = {
    "en": (
        "🔵 {chain}\n"
        "📋 <b>Wallet:</b>\n"
        "<code>{wallet}</code>\n\n"
        "💵 Send EXACTLY: <code>{amount} USDT</code>\n"
        "⚡ Bot auto-detects within 30 seconds!\n"
        "🔖 Order: <code>{order}</code> | ⏰ {hours} hours"
    ),
    "bn": (
        "🔵 {chain}\n"
        "📋 <b>ওয়ালেট:</b>\n"
        "<code>{wallet}</code>\n\n"
        "💵 ঠিকভাবে পাঠান: <code>{amount} USDT</code>\n"
        "⚡ বট ৩০ সেকেন্ডের মধ্যে অটো-ডিটেক্ট করবে!\n"
        "🔖 অর্ডার: <code>{order}</code> | ⏰ {hours} ঘণ্টা"
    ),
    "hi": (
        "🔵 {chain}\n"
        "📋 <b>वॉलेट:</b>\n"
        "<code>{wallet}</code>\n\n"
        "💵 बिल्कुल इतना भेजें: <code>{amount} USDT</code>\n"
        "⚡ बॉट 30 सेकंड के भीतर स्वतः पहचान लेगा!\n"
        "🔖 ऑर्डर: <code>{order}</code> | ⏰ {hours} घंटे"
    ),
    "ur": (
        "🔵 {chain}\n"
        "📋 <b>والیٹ:</b>\n"
        "<code>{wallet}</code>\n\n"
        "💵 بالکل اتنے بھیجیں: <code>{amount} USDT</code>\n"
        "⚡ بوٹ 30 سیکنڈ کے اندر خود بخود پہچان لے گا!\n"
        "🔖 آرڈر: <code>{order}</code> | ⏰ {hours} گھنٹے"
    ),
    "ar": (
        "🔵 {chain}\n"
        "📋 <b>المحفظة:</b>\n"
        "<code>{wallet}</code>\n\n"
        "💵 أرسل المبلغ المحدد بالضبط: <code>{amount} USDT</code>\n"
        "⚡ يكتشف البوت تلقائياً خلال 30 ثانية!\n"
        "🔖 الطلب: <code>{order}</code> | ⏰ {hours} ساعة"
    ),
    "zh": (
        "🔵 {chain}\n"
        "📋 <b>钱包：</b>\n"
        "<code>{wallet}</code>\n\n"
        "💵 请发送准确的金额：<code>{amount} USDT</code>\n"
        "⚡ 机器人会在30秒内自动检测！\n"
        "🔖 订单：<code>{order}</code> | ⏰ {hours} 小时"
    ),
}

PAYMENT_CONFIRMED_MESSAGES = {
    "en": (
        "✅ <b>Payment Received!</b>\n\n"
        "💎 VIP activated!\n"
        "📦 Plan: {plan}\n"
        "⏳ Expires: {date}\n\n"
        "Thank you for your purchase! 🎉"
    ),
    "bn": (
        "✅ <b>পেমেন্ট প্রাপ্ত হয়েছে!</b>\n\n"
        "💎 VIP সক্রিয় হয়েছে!\n"
        "📦 প্ল্যান: {plan}\n"
        "⏳ মেয়াদ শেষ: {date}\n\n"
        "আপনার কেনাকাটার জন্য ধন্যবাদ! 🎉"
    ),
    "hi": (
        "✅ <b>भुगतान प्राप्त हुआ!</b>\n\n"
        "💎 VIP सक्रिय हो गया!\n"
        "📦 प्लान: {plan}\n"
        "⏳ समाप्ति: {date}\n\n"
        "आपकी खरीदारी के लिए धन्यवाद! 🎉"
    ),
    "ur": (
        "✅ <b>ادائیگی موصول ہوگئی!</b>\n\n"
        "💎 VIP فعال ہو گیا!\n"
        "📦 پلان: {plan}\n"
        "⏳ ختم ہونے کی تاریخ: {date}\n\n"
        "آپ کی خریداری کے لیے شکریہ! 🎉"
    ),
    "ar": (
        "✅ <b>تم استلام الدفع!</b>\n\n"
        "💎 تم تفعيل VIP!\n"
        "📦 الخطة: {plan}\n"
        "⏳ تنتهي في: {date}\n\n"
        "شكراً لشرائك! 🎉"
    ),
    "zh": (
        "✅ <b>已收到付款！</b>\n\n"
        "💎 VIP 已激活！\n"
        "📦 套餐：{plan}\n"
        "⏳ 到期时间：{date}\n\n"
        "感谢您的购买！🎉"
    ),
}

PAYMENT_NOT_DETECTED_MESSAGES = {
    "en": (
        "⏳ Payment not detected yet. Double-check the amount and wallet address, then press the button again in a moment."
    ),
    "bn": (
        "⏳ পেমেন্ট এখনো শনাক্ত হয়নি। পরিমাণ এবং ওয়ালেট ঠিকানা আবার যাচাই করুন, তারপর একটু পরে আবার বাটনটি চাপুন।"
    ),
    "hi": (
        "⏳ अभी तक भुगतान का पता नहीं चला। राशि और वॉलेट पता दोबारा जाँचें, फिर कुछ देर बाद फिर से बटन दबाएँ।"
    ),
    "ur": (
        "⏳ ابھی تک ادائیگی کا پتہ نہیں چلا۔ رقم اور والیٹ پتہ دوبارہ چیک کریں، پھر ایک لمحے کے بعد دوبارہ بٹن دبائیں۔"
    ),
    "ar": (
        "⏳ لم يتم اكتشف الدفع بعد. تأكد من المبلغ وعنوان المحفظة، ثم اضغط على الزر مرة أخرى بعد قليل."
    ),
    "zh": (
        "⏳ 尚未检测到付款。请再次核对金额和钱包地址，稍后再按一次按钮。"
    ),
}

PAYMENT_METHOD_UNAVAILABLE_MESSAGES = {
    "en": (
        "❌ This payment method is currently unavailable. Please choose another one."
    ),
    "bn": (
        "❌ এই পেমেন্ট পদ্ধতিটি বর্তমানে অনুপলব্ধ। অনুগ্রহ করে অন্য একটি বেছে নিন।"
    ),
    "hi": (
        "❌ यह भुगतान विधि अभी उपलब्ध नहीं है। कृपया कोई दूसरी विधि चुनें।"
    ),
    "ur": (
        "❌ ادائیگی کا یہ طریقہ فی الحال دستیاب نہیں ہے۔ براہ کرم کوئی اور طریقہ منتخب کریں۔"
    ),
    "ar": (
        "❌ هذه طريقة الدفع غير متاحة حالياً. يرجى اختيار طريقة أخرى."
    ),
    "zh": (
        "❌ 该支付方式当前不可用。请选择其他方式。"
    ),
}
