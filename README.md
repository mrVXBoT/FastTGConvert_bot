# FastTGConvert Bot (safe MVP)

ربات پایتونی برای تحلیل امن فایل، محاسبه SHA-256 و تقسیم فایل به قطعات. این
پروژه از Session کاربران برای ورود استفاده نمی‌کند و قابلیت‌های OTP، تغییر 2FA،
حذف اطلاعات حساب یا ارسال انبوه ندارد.

## قابلیت‌های فعلی

- انتخاب زبان در شروع با پشتیبانی از بنگالی، انگلیسی، هندی، اردو، عربی و چینی؛
- ذخیره زبان انتخابی هر کاربر در SQLite؛
- رابط بخش‌بندی‌شده و دو‌ستونه مشابه نمونه تصویری؛
- نمایش تمام گزینه‌های منوی نمونه با تفکیک قابلیت فعال، در حال توسعه و محدود؛
- ثبت کاربران، فایل‌ها و Jobها در SQLite با SQLAlchemy 2؛
- عضویت اجباری اختیاری با `getChatMember`؛
- محدودیت حجم فایل؛
- نام‌گذاری تصادفی فایل‌های ذخیره‌شده؛
- تحلیل اندازه، MIME، SHA-256 و ساختار ZIP؛
- تشخیص مسیر ناامن و Zip Bomb؛
- Split همراه `manifest.json` و hash هر قطعه؛
- لغو عملیات و پاک‌سازی دوره‌ای فایل‌های منقضی‌شده.

## راه‌اندازی

Python 3.12 یا جدیدتر لازم است.

```bash
cd FastTGConvert_bot
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
```

از `@BotFather` یک Bot Token دریافت و در `.env` جایگزین کنید:

```dotenv
BOT_TOKEN=123456789:your_real_token
```

برای عضویت اجباری، ربات را در کانال‌ها admin کنید و usernameها را با کاما
وارد کنید. تنظیم پیش‌فرض مطابق ربات مرجع است:

```dotenv
REQUIRED_CHANNELS=@FastTGConvert
SUPPORT_ID=@your_support_username
```

اجرا:

```bash
python -m app
```

در اولین اجرا `data/bot.db` و پوشه‌های ذخیره‌سازی ساخته می‌شوند.

## تست

```bash
pytest
ruff check .
```

تست‌های سرویس فایل بدون dependencyهای پروژه نیز با این فرمان اجرا می‌شوند:

```bash
python -m unittest discover -s tests
```

## تنظیمات

| متغیر | پیش‌فرض | توضیح |
|---|---:|---|
| `BOT_TOKEN` | الزامی | توکن BotFather |
| `DATABASE_URL` | `sqlite:///data/bot.db` | اتصال دیتابیس |
| `STORAGE_DIR` | `data/storage` | فایل‌های موقت |
| `MAX_UPLOAD_MB` | `20` | سقف ورودی |
| `RETENTION_MINUTES` | `60` | زمان نگهداری ورودی |
| `REQUIRED_CHANNELS` | `@FastTGConvert` | کانال‌های الزامی با کاما |
| `SUPPORT_ID` | خالی | نام کاربری، لینک `t.me` یا شناسه عددی ادمین پشتیبانی |

## ساختار

```text
app/
├── handlers/       # مسیرهای Telegram و FSM
├── services/       # منطق فایل، عضویت و Job
├── db/             # مدل‌ها، repository و اتصال async
├── cleanup.py      # حذف فایل‌های منقضی
├── config.py       # تنظیمات محیطی
└── __main__.py     # اجرای long polling
tests/
```

سند معماری کامل پروژه در `../docs/architecture-fa.md` قرار دارد.

## محدودیت MVP

- FSM فعلاً در حافظه است؛ restart عملیات نیمه‌کاره تعاملی را پاک می‌کند، ولی
  رکوردهای SQLite باقی می‌مانند.
- Merge، پرداخت، ترجمه کامل تمام زیرمنوها، migrationهای Alembic و worker مستقل در
  فازهای بعدی اضافه می‌شوند.
- SQLite برای یک process/worker طراحی شده است.
