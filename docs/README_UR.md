# 📘 FastTGConvert — مکمل تکنیکی دستاویزات (اردو)

FastTGConvert کے سرکاری تکنیکی دستاویزات میں خوش آمدید۔ یہ ٹیلیگرام سیشنز کی منتقلی اور تبدیلی کا ایک جدید پلیٹ فارم ہے۔

---

## 📋 فہرست عنوانات

1. [منصوبے کا جائزہ](#1-منصوبے-کا-جائزہ)
2. [سسٹم کی ساخت (Architecture)](#2-سسٹم-کی-ساخت-architecture)
3. [اہم خصوصیات](#3-اہم-خصوصیات)
4. [ڈیٹا بیس](#4-ڈیٹا-بیس)
5. [سیکیورٹی](#5-سیکیورٹی)
6. [انسٹالیشن اور ڈیپلائمنٹ](#6-انسٹالیشن-اور-ڈیپلائمنٹ)

---

## 1. منصوبے کا جائزہ

FastTGConvert ایک Python (Aiogram 3.x, Telethon, SQLAlchemy 2.0) پر مبنی نظام ہے جو سیشن فائلز کو محفوظ طریقے سے کنورٹ کرنے کے لیے بنایا گیا ہے۔

### اہم خصوصیات
- **سیشن کنورژن**: `.session` ↔ `TData` (Telegram Desktop zip)، `.json` اور `.txt` کی دو طرفہ تبدیلی۔
- **سیکیورٹی ٹولز**: 2FA پاس ورڈ کی تبدیلی/ریسیٹ، @SpamBot چیٹ سیکیورٹی چیک، چیٹ کلینر۔
- **ایڈمن پینل**: تمام ایڈمن افعال کے لیے مکمل Inline Keyboard اور RBAC پر مبنی رسائی کنٹرول۔

---

## 2. انسٹالیشن

```bash
git clone https://github.com/mrVXBoT/FastTGConvert_bot.git
cd FastTGConvert_bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python3 -m app
```

---

## 3. ٹیسٹنگ

- **کامیاب ٹیسٹس**: 296 (`296 passed`)
- **ٹیسٹ کمانڈ**: `.venv/bin/pytest`
