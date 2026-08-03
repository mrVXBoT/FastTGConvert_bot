# 🚀 FastTGConvert — Production Telegram Session & File Conversion Suite

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/framework-Aiogram%203.x-green.svg)](https://docs.aiogram.dev/)
[![Database](https://img.shields.io/badge/database-SQLAlchemy%202.0%20%7C%20SQLite-orange.svg)](https://www.sqlalchemy.org/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-296%20passed-brightgreen.svg)](tests/)

FastTGConvert is an enterprise-grade, asynchronous Telegram Bot engine designed for session management, file format conversion, security auditing, and account lifecycle utility execution. Built on Aiogram 3.x, Telethon, and SQLAlchemy 2.0, it features a complete inline-keyboard-driven Admin Panel with Role-Based Access Control (RBAC), multi-channel Force Join enforcement, dynamic VIP subscription management, automated file retention cleanup, and production observability via Prometheus metrics and structured JSON tracing.

---

## 🌐 Documentation Languages

Select your preferred language to read the complete technical documentation:

- 🇬🇧 **[English Documentation](docs/README_EN.md)**
- 🇧🇩 **[বাংলা নথি (Bengali)](docs/README_BN.md)**
- 🇮🇳 **[हिन्दी दस्तावेज़ (Hindi)](docs/README_HI.md)**
- 🇵🇰 **[اردو دستاویزات (Urdu)](docs/README_UR.md)**
- 🇸🇦 **[الوثائق بالعربية (Arabic)](docs/README_AR.md)**
- 🇨🇳 **[中文文档 (Chinese)](docs/README_ZH.md)**

---

## 📌 Executive Summary

### Main Features
- **Session & File Conversions**: Convert bidirectionally between `.session` (Telethon/Pyrogram) and `TData` (Telegram Desktop format), as well as `.json` exports and `.txt` account dumps.
- **Account Utilities**: Account Age Estimation, Session Health Checking, SpamBot Restriction Check, Chat Cleaner, 2FA Password Change/Disable/Reset, Contact List Cleaner, Mass Messaging.
- **Dynamic Feature Access Control (Feature Gates)**: Granular control over every bot capability (FREE vs VIP_ONLY) via database-driven toggles.
- **Role-Based Admin Panel**: Inline-keyboard UI for Owner, Super Admin, Admin, and Support roles. Includes User Search, Direct Messaging, VIP Granting, User Banning, Dynamic Plan Builder, Payment Gateways (TRC20, BEP20, Binance Pay), and Mass Broadcast Engine with queue recovery.
- **Security & Privacy Protection**: Fernet Base64 proxy encryption, UserStatusMiddleware ban enforcement, Telethon session isolation, sensitive data masking in logs, and automated ephemeral file retention purging.
- **Production Observability**: Built-in HTTP server for `/healthz`, `/readyz`, and `/metrics` (Prometheus exporter), structured JSON logging with request Trace IDs, and Grafana dashboard configurations.

---

## 🏛️ System Architecture

### High-Level Architecture

```mermaid
graph TD
    User[📱 Telegram User] -->|Update| Router[🤖 Aiogram 3 Master Router]
    Router --> Middleware[🛡️ Middleware Layer: Tracing & UserStatus]
    Middleware -->|Active User| Handlers[⚙️ Handler Layer: Files, OTP, Start, VIP]
    Middleware -->|Banned User| Block[🚫 Silent Reject / Block Message]
    Handlers --> Services[🧱 Service Layer: Session, Security, Converters]
    Services --> Telethon[⚡ Telethon Engine Pool]
    Services --> Repos[📦 Repository Layer]
    Repos --> DB[(🗄️ SQLite / SQLAlchemy 2.0)]
```

### Admin Panel Architecture

```mermaid
graph TD
    Admin[👮 Admin User] -->|CallbackQuery / Command| RBAC[🛡️ AdminPermissionMiddleware & RBAC]
    RBAC -->|Authorized| AdminRouter[🎛️ Admin Router]
    AdminRouter --> Stats[📊 Statistics Module]
    AdminRouter --> Users[👥 User Management]
    AdminRouter --> Broadcast[📢 Broadcast Queue Engine]
    AdminRouter --> AdminMgmt[👮 Admin & Role Mgmt]
    AdminRouter --> ForceJoin[📌 Force Join Channels]
    AdminRouter --> Support[🎧 Dynamic Support Settings]
    AdminRouter --> VIP[💎 VIP & Feature Gate Mgmt]
```

### VIP & Access Control Architecture

```mermaid
graph TD
    U[User Request Tool] --> FG{🔒 FeatureGate Check}
    FG -->|Access Level = FREE| Exec[✅ Execute Feature]
    FG -->|Access Level = VIP_ONLY| VIPCheck{💎 User VIP Status Check}
    VIPCheck -->|User is VIP & Active| Exec
    VIPCheck -->|User Not VIP| PayPrompt[💳 Prompt VIP Purchase Plan]
    PayPrompt --> SelectPlan[Choose Plan & Gateway]
    SelectPlan --> Payment[Record Payment & Submit Receipt]
    Payment --> AdminApprove[👮 Admin Approval Flow]
    AdminApprove --> GrantVIP[🎉 Activate Subscription & Reset Expiry]
```

### Broadcast Engine Architecture

```mermaid
graph TD
    AdminPrompt[👮 Admin Creates Broadcast] --> Preview[👁️ Render Interactive Preview]
    Preview --> Confirm[✅ Admin Confirms Dispatch]
    Confirm --> JobRecord[📝 Store BroadcastJobRecord in DB]
    JobRecord --> Worker[🔄 Background Broadcast Worker]
    Worker --> Batch[📦 Fetch Active Users Batch]
    Batch --> Send[📡 Send via Bot API with Rate Limit Delay]
    Send --> Progress[📊 Update Progress & Success/Fail Counter]
    Worker -->|Interrupted/Crash| Recover[🔄 Startup Recovery into PAUSED state]
```

---

## 🗄️ Database Entity-Relationship Diagram

```mermaid
erDiagram
    users ||--o{ files : owns
    users ||--o{ jobs : runs
    users ||--o{ statistic_events : triggers
    users ||--o{ payments : creates
    users ||--o{ user_vip_subscriptions : holds
    vip_plans ||--o{ payments : tier
    vip_plans ||--o{ user_vip_subscriptions : plan
    payments ||--o| user_vip_subscriptions : grants

    users {
        int id PK
        bigint telegram_id UK
        string username
        string language
        string status
        boolean is_vip
        datetime vip_expires_at
        datetime created_at
    }

    files {
        string id PK
        int user_id FK
        string media_type
        bigint size_bytes
        string sha256
        string storage_path
        datetime expires_at
    }

    jobs {
        string id PK
        string display_id UK
        int user_id FK
        string operation
        string status
        int progress
        datetime created_at
    }

    admin_users {
        int id PK
        bigint telegram_id UK
        string role
        datetime created_at
    }

    feature_gates {
        int id PK
        string feature_key UK
        string title
        string access_level
        boolean is_enabled
    }

    vip_plans {
        int id PK
        string name
        int months
        float price
        boolean is_active
    }

    payments {
        int id PK
        int user_id FK
        int plan_id FK
        float amount
        string payment_method
        string status
        string receipt_file_id
    }

    broadcast_jobs {
        string id PK
        string message_type
        string status
        int total_users
        int sent_count
        int failed_count
    }
```

---

## 🚀 Quick Deployment Guide

```bash
# 1. Clone the repository
git clone https://github.com/mrVXBoT/FastTGConvert_bot.git
cd FastTGConvert_bot

# 2. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy environment configuration
cp .env.example .env

# 5. Edit .env with your credentials (BOT_TOKEN, ADMIN_ID, API_CREDENTIALS)
nano .env

# 6. Run database migrations & seed defaults
python3 -m app.db.migration

# 7. Start the application
python3 -m app
```

For complete deployment details, systemd configuration, Prometheus alerting, and full multi-language documentation, visit **[docs/README_EN.md](docs/README_EN.md)**.

---

## 🧪 Testing & Code Quality

FastTGConvert enforces rigorous test coverage and static analysis:

```bash
# Run unit & integration test suite (296 tests)
.venv/bin/pytest

# Run static type checker
.venv/bin/mypy app

# Run linter & formatter
.venv/bin/ruff check
```

---

## 📜 License & Compliance

Distributed under the MIT License. See `LICENSE` for more information.
