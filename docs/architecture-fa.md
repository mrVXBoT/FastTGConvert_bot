# سند طراحی ربات مدیریت و تبدیل فایل تلگرام

نسخه سند: 0.1 — مرداد ۱۴۰۵ / اوت ۲۰۲۶

## 1. هدف محصول

این پروژه یک ربات تلگرام مبتنی بر پایتون برای دریافت، اعتبارسنجی، تحلیل و
تبدیل **امن فایل‌های متعلق به خود کاربر** است. تجربه کاربری از منوی مشاهده‌شده
در `@FastTGConvert_bot` الهام می‌گیرد، ولی معماری و منطق Backend مستقل، شفاف و
امن طراحی می‌شود.

نسخه اول این قابلیت‌ها را ارائه می‌دهد:

- منوی چندزبانه و راهنمای کاربر؛
- بررسی عضویت در کانال‌های الزامی، بدون استفاده از حساب کاربری کاربر؛
- دریافت کنترل‌شده فایل و ZIP؛
- تشخیص نوع، اندازه، hash و ساختار فایل؛
- تبدیل‌کننده‌های افزونه‌پذیر (Converter Plugin)؛
- Split و Merge فایل‌های عمومی؛
- صف پردازش، نمایش پیشرفت و امکان لغو؛
- سهمیه رایگان و پلن VIP؛
- ثبت رویداد، گزارش خطا و پنل مدیریتی محدود؛
- حذف خودکار فایل‌های موقت.

این موارد عمداً خارج از محدوده هستند:

- ورود به حساب تلگرام با Session بارگذاری‌شده؛
- خواندن OTP، تغییر یا حذف 2FA و بستن نشست‌های حساب؛
- حذف مخاطب، گفتگو یا اطلاعات حساب؛
- ارسال انبوه یا خودکار پیام؛
- نگهداری Session، رمز عبور، کد ورود یا کلیدهای احراز هویت کاربران.

فایل Session در حکم کلید دسترسی حساب است. اگر در آینده فرمت‌هایی مانند
Session یا TData پشتیبانی شوند، پردازش فقط باید به‌صورت آفلاین و بدون اتصال
به حساب انجام شود؛ خروجی نیز فقط به همان کاربری تحویل داده شود که فایل را
ارسال کرده است.

## 2. انتخاب فناوری

### پشته پیشنهادی

| بخش | انتخاب | دلیل |
|---|---|---|
| Python | 3.12 یا 3.13 | پشتیبانی مناسب از asyncio و type hint |
| Telegram framework | `aiogram ~= 3.30` | async، Router، FSM، middleware و Bot API جدید |
| ORM | `SQLAlchemy ~= 2.0` | مدل‌سازی و تراکنش async |
| SQLite driver | `aiosqlite` | اتصال غیرهمزمان SQLAlchemy به SQLite |
| Migration | `Alembic` | تغییر نسخه‌پذیر schema |
| Validation/config | `pydantic` و `pydantic-settings` | اعتبارسنجی تنظیمات و داده‌ها |
| File type detection | `python-magic` | تشخیص محتوا به‌جای اعتماد به پسوند |
| Archive | کتابخانه استاندارد `zipfile` | کنترل کامل روی استخراج امن ZIP |
| Testing | `pytest`, `pytest-asyncio` | تست واحد و async |
| Quality | `ruff`, `mypy` | lint، format و بررسی نوع |

`aiogram` فقط ارتباط با Telegram Bot API، دریافت Update و مدیریت منو/FSM را
انجام می‌دهد. تبدیل Session، TData، JSON یا فایل‌های دیگر قابلیت داخلی آن نیست
و باید در لایه جداگانه `services/converters` پیاده‌سازی شود.

نسخه‌های پیشنهادی اولیه:

```text
aiogram>=3.30,<4
SQLAlchemy>=2.0.51,<2.1
aiosqlite>=0.20,<1
alembic>=1.16,<2
pydantic>=2.11,<3
pydantic-settings>=2.10,<3
python-magic>=0.4.27,<1
```

نسخه‌ها پیش از lock نهایی با Python انتخاب‌شده و سیستم‌عامل سرور آزمایش و در
فایل lock ثابت شوند. مستندات رسمی: [aiogram 3.x](https://docs.aiogram.dev/en/dev-3.x/)،
[SQLAlchemy asyncio](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)،
[SQLite در پایتون](https://docs.python.org/3/library/sqlite3.html) و
[Alembic](https://alembic.sqlalchemy.org/en/latest/).

## 3. معماری کلان

```text
Telegram
   │ Update / File
   ▼
aiogram Router ── Middleware (DB, locale, rate limit, access)
   │
   ├── Menu handlers
   ├── Upload/FSM handlers
   ├── Membership handlers
   └── Admin handlers
           │
           ▼
       Use cases / Services
           │
      ┌────┴───────────────┐
      ▼                    ▼
SQLite repositories    Job runner
                           │
                           ▼
                  Validators / Converters
                           │
                           ▼
                    Temporary storage
```

Handler نباید منطق تبدیل، query خام یا عملیات مستقیم فایل داشته باشد. Handler
ورودی را اعتبارسنجی اولیه می‌کند، یک Use Case را صدا می‌زند و نتیجه را برای
کاربر نمایش می‌دهد.

برای توسعه محلی از long polling استفاده می‌شود. در production می‌توان به
webhook با HTTPS و `secret_token` مهاجرت کرد. long polling و webhook هم‌زمان
قابل استفاده نیستند.

## 4. ساختار پیشنهادی پروژه

```text
app/
├── __main__.py
├── config.py
├── bot.py
├── handlers/
│   ├── start.py
│   ├── files.py
│   ├── converters.py
│   ├── membership.py
│   ├── billing.py
│   └── admin.py
├── keyboards/
├── middlewares/
│   ├── database.py
│   ├── rate_limit.py
│   └── access.py
├── states/
├── services/
│   ├── file_service.py
│   ├── job_service.py
│   ├── membership_service.py
│   ├── quota_service.py
│   └── converters/
│       ├── base.py
│       ├── registry.py
│       ├── metadata.py
│       ├── split.py
│       └── merge.py
├── db/
│   ├── models.py
│   ├── session.py
│   └── repositories/
├── workers/
│   └── job_runner.py
└── utils/
tests/
alembic/
data/
├── inbox/
├── work/
└── output/
```

## 5. مدل داده SQLite

تمام timestampها به UTC ذخیره شوند. شناسه Telegram از نوع `BIGINT` است.

### `users`

| ستون | نوع | توضیح |
|---|---|---|
| id | INTEGER PK | شناسه داخلی |
| telegram_id | BIGINT UNIQUE | شناسه کاربر |
| username | TEXT NULL | نام کاربری اخیر |
| language | TEXT | پیش‌فرض `fa` یا انتخاب کاربر |
| status | TEXT | `active`, `blocked` |
| created_at | DATETIME | زمان ایجاد |
| last_seen_at | DATETIME | آخرین فعالیت |

### `plans` و `subscriptions`

`plans`: کد پلن، نام، مدت، قیمت، ارز، سقف روزانه، اندازه مجاز فایل و وضعیت.

`subscriptions`: کاربر، پلن، زمان شروع/پایان، وضعیت و مرجع پرداخت. وضعیت‌ها:
`pending`, `active`, `expired`, `cancelled`.

### `required_channels`

شناسه یا username کانال، عنوان، ترتیب و وضعیت فعال. ربات فقط از طریق
`getChatMember` عضویت را بررسی می‌کند؛ خود Bot API نمی‌تواند کاربر را به زور
عضو کانال کند.

### `files`

| ستون | نوع | توضیح |
|---|---|---|
| id | TEXT PK | UUID |
| user_id | FK | مالک فایل |
| telegram_file_id | TEXT NULL | شناسه دانلود Telegram |
| original_name | TEXT | نام پاک‌سازی‌شده |
| media_type | TEXT | MIME تشخیص‌داده‌شده |
| size_bytes | INTEGER | اندازه |
| sha256 | TEXT | hash محتوا |
| storage_path | TEXT | مسیر نسبی، نه absolute |
| purpose | TEXT | input/output |
| expires_at | DATETIME | موعد حذف |
| created_at | DATETIME | زمان ثبت |

روی `(user_id, sha256)` index ایجاد شود. مسیر کامل و محتوای فایل وارد log نشود.

### `jobs`

| ستون | نوع | توضیح |
|---|---|---|
| id | TEXT PK | UUID |
| user_id | FK | مالک job |
| operation | TEXT | نام converter |
| input_file_id | FK | ورودی |
| output_file_id | FK NULL | خروجی |
| status | TEXT | وضعیت state machine |
| progress | INTEGER | صفر تا صد |
| options_json | JSON/TEXT | گزینه‌های غیرحساس |
| error_code | TEXT NULL | کد قابل پشتیبانی |
| created_at/started_at/finished_at | DATETIME | زمان‌ها |

چرخه وضعیت:

```text
queued → validating → running → completed
   │          │           │
   └──────────┴───────────┴→ failed
                    └──────→ cancelled
```

### `payments`, `audit_events`, `daily_usage`

- `payments`: مبلغ، ارز، provider، شناسه یکتای provider و وضعیت؛
- `audit_events`: actor، action، target و metadata پاک‌سازی‌شده؛
- `daily_usage`: تعداد job و مجموع bytes برای اعمال سهمیه اتمیک.

هیچ جدول یا ستونی برای OTP، رمز 2FA یا Session قابل استفاده جهت ورود وجود
نداشته باشد.

### تنظیم اتصال SQLite

- `PRAGMA foreign_keys=ON`؛
- حالت WAL برای هم‌زمانی بهتر خواندن/نوشتن؛
- `busy_timeout` برای برخورد کنترل‌شده با lock؛
- تراکنش کوتاه؛ تبدیل فایل داخل transaction اجرا نشود؛
- یک `AsyncSession` مستقل برای هر Update یا job؛ Session بین taskها share نشود.

SQLite برای MVP و یک worker مناسب است. اگر چند instance یا worker هم‌زمان لازم
شد، مهاجرت به PostgreSQL و یک صف مستقل مانند Redis/RQ یا Celery بررسی شود.

## 6. فلوهای Backend

### 6.1 شروع و عضویت اجباری

```text
/start
  → upsert user
  → انتخاب/خواندن زبان
  → getChatMember برای کانال‌های فعال
  → اگر ناقص: نمایش لینک‌ها + دکمه «بررسی مجدد»
  → اگر کامل: نمایش منوی اصلی
```

نتیجه عضویت برای ۳۰ تا ۶۰ ثانیه cache شود تا فشار API کم شود. فقط شناسه و
وضعیت عضویت ذخیره شود.

### 6.2 پردازش یک فایل

```text
انتخاب ابزار
  → ثبت state در FSM
  → دریافت Document
  → کنترل quota و اندازه
  → دانلود با نام تصادفی
  → محاسبه SHA-256 و تشخیص MIME
  → اعتبارسنجی ساختار، بدون اجرای محتوا
  → ایجاد file و job در یک transaction
  → worker: validating → running
  → تولید خروجی در مسیر جدا
  → ثبت output + completed
  → ارسال نتیجه به همان telegram_id
  → زمان‌بندی حذف input/output
```

اگر کاربر `/cancel` بفرستد، FSM پاک و job در صورت شروع‌نشدن `cancelled` شود.

### 6.3 Split

ورودی: فایل و اندازه هر قطعه. ابتدا سقف قطعات محاسبه و تأیید گرفته شود. فایل
به chunkهای باینری با نام‌های ترتیبی تقسیم، سپس همراه manifest شامل نام، اندازه
و SHA-256 هر قطعه در ZIP خروجی قرار گیرد.

### 6.4 Merge

کاربر چند قطعه و manifest را می‌فرستد. Backend مالکیت، تعداد، ترتیب، اندازه و
hash هر قطعه را بررسی می‌کند؛ سپس در فایل جدید ادغام و hash نهایی را گزارش
می‌دهد. نام فایل از manifest مستقیماً به مسیر filesystem تبدیل نشود.

### 6.5 Converter Plugin

هر تبدیل‌کننده یک قرارداد مشترک دارد:

```python
class Converter(Protocol):
    name: str
    accepted_types: frozenset[str]

    async def validate(self, source: Path, options: dict) -> None: ...
    async def convert(self, source: Path, destination: Path, options: dict) -> None: ...
```

Registry بر اساس `operation` تبدیل‌کننده را انتخاب می‌کند. Handler هرگز نام
module یا command را از ورودی کاربر import/execute نمی‌کند.

### 6.6 پرداخت و VIP

در MVP ابتدا می‌توان فعال‌سازی دستی توسط ادمین داشت. فاز بعد از Telegram
Payments یا provider معتبر استفاده کند:

```text
create payment(pending)
  → ساخت invoice
  → pre-checkout validation
  → successful_payment/webhook معتبر
  → transaction: payment=paid + subscription=active
  → پاسخ idempotent
```

صرف مشاهده صفحه پرداخت یا ارسال screenshot نباید عضویت VIP را فعال کند.

## 7. منوی پیشنهادی محصول

```text
🏠 منوی اصلی
├── 🔍 تحلیل فایل
│   ├── مشخصات و SHA-256
│   └── بررسی ساختار ZIP
├── 🔄 تبدیل فایل
│   └── تبدیل‌کننده‌های نصب‌شده
├── 📁 ابزار فایل
│   ├── Split
│   └── Merge
├── 💎 اشتراک و سهمیه
├── 🌐 زبان
├── ❓ راهنما و حریم خصوصی
└── 👤 وضعیت حساب ربات
```

گزینه‌ای که هنوز converter آن پیاده نشده نمایش داده نشود. دکمه‌های عنوانی
مانند `━━ CHECK ━━` callback نداشته باشند تا Update بیهوده تولید نشود.

## 8. امنیت فایل

- سقف اندازه پیش از دانلود و پس از استخراج کنترل شود؛
- از نام UUID برای فایل روی دیسک استفاده شود؛
- `..`، مسیر absolute و symlink داخل ZIP رد شود (جلوگیری از Zip Slip)؛
- تعداد اعضا و نسبت فشرده‌سازی محدود شود (جلوگیری از Zip Bomb)؛
- extension ملاک اعتماد نباشد؛ MIME و magic bytes بررسی شود؛
- فایل executable، macro و محتوای ناشناخته اجرا نشود؛
- subprocess فقط با آرگومان‌های ثابت، timeout و sandbox اجرا شود؛
- فایل هر کاربر فقط با شرط `file.user_id == current_user.id` خوانده شود؛
- فایل‌های موقت حتی پس از exception در `finally` پاک شوند؛
- retention پیش‌فرض حداکثر یک ساعت و قابل تنظیم باشد؛
- Bot Token فقط در environment/secret manager نگهداری شود؛
- log شامل token، فایل، مسیر حساس یا داده احراز هویت نباشد.

در production بهتر است پردازش فایل در container/worker جدا با کاربر سیستم محدود،
بدون دسترسی شبکه و با محدودیت CPU، RAM و زمان انجام شود.

## 9. سهمیه، Rate Limit و خطا

- محدودیت کلی: مثلاً ۵ callback در ۱۰ ثانیه برای هر کاربر؛
- دانلود هم‌زمان: یک job فعال برای کاربر رایگان؛
- محدودیت روزانه با update اتمیک `daily_usage`؛
- callbackها سریع `answer()` شوند تا spinner تلگرام بسته شود؛
- Retry فقط برای خطاهای موقت Telegram و با backoff؛
- عملیات تبدیل idempotent باشد و job تکمیل‌شده دوباره اجرا نشود؛
- خطای کاربر با پیام فارسی و `error_code` نمایش داده شود؛ traceback فقط در log.

## 10. تست

حداقل تست‌های لازم:

- Router و callback data؛
- انتقال stateهای FSM و `/cancel`؛
- repositoryها روی SQLite موقت؛
- state machine مربوط به job؛
- quota و race condition؛
- فایل خالی، پسوند جعلی و ZIP خراب؛
- Zip Slip، Zip Bomb، symlink و نام Unicode؛
- قطع دانلود و timeout تبدیل؛
- عدم دسترسی کاربر A به فایل کاربر B؛
- idempotency پرداخت و webhook تکراری؛
- cleanup فایل منقضی‌شده.

## 11. مراحل اجرا

### فاز 1 — زیرساخت

پیکربندی، aiogram، Routerها، SQLAlchemy async، migration، `/start`، زبان، log و
health check.

### فاز 2 — فایل و job

دانلود امن، جدول files/jobs، صف تک‌worker، progress، cancel و cleanup.

### فاز 3 — ابزارهای MVP

تحلیل metadata و hash، Split، Merge و تست‌های امنیت فایل.

### فاز 4 — دسترسی و درآمد

عضویت اجباری، quota، پلن‌ها، فعال‌سازی VIP و سپس provider پرداخت معتبر.

### فاز 5 — production

Webhook امن، worker ایزوله، backup دیتابیس، مانیتورینگ، هشدار و سیاست حریم
خصوصی عمومی.

## 12. معیار پذیرش MVP

- کاربر بتواند زبان را انتخاب و منوی اصلی را ببیند؛
- عضویت کانال با Bot API بررسی شود؛
- فایل مجاز دریافت و بدون اعتماد به نام آن اعتبارسنجی شود؛
- job پس از restart از SQLite قابل بازیابی باشد؛
- Split و Merge با hash صحیح کار کنند؛
- فایل‌ها بعد از retention حذف شوند؛
- کاربر به فایل فرد دیگر دسترسی نداشته باشد؛
- هیچ Session، OTP یا رمز حساب برای ورود استفاده یا ذخیره نشود؛
- تست‌های امنیت ZIP و مالکیت فایل پاس شوند.

این طراحی عمداً از SQLite شروع می‌کند، ولی repository و serviceها را طوری جدا
می‌کند که مهاجرت آینده به PostgreSQL یا worker مستقل بدون بازنویسی Handlerها
ممکن باشد.
