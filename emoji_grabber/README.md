# 🔍 Telegram Custom Emoji Finder (Userbot)

اسکریپت یوزر‌بات جهت استخراج و پیدا کردن سریع آیدی‌های ۱۹ رقمی **Telegram Premium Custom Emoji**.

---

### 🚀 نحوه اجرا:

1. **اجرای اسکریپت**:
   ```bash
   .venv/bin/python emoji_grabber/main.py
   ```

2. **ورود به حساب**:
   در بار اول اجرای اسکریپت، از شما `API_ID` و `API_HASH` دریافت می‌کند (می‌توانید آن‌ها را از [my.telegram.org](https://my.telegram.org) دریافت کرده یا در فایل `.env` تعریف کنید):
   ```env
   TELEGRAM_API_ID=123456
   TELEGRAM_API_HASH=your_api_hash_here
   ```
   سپس شماره تلفن و کد تایید تلگرام را وارد کنید.

3. **دریافت آیدی ایموجی**:
   کافیست در تلگرام وارد بخش **Saved Messages** (پیام‌های ذخیره‌شده) شوید و هر **Custom Emoji** که می‌خواهید را بفرستید. 
   اسکریپت بلافاصله آیدی ۱۹ رقمی آن را به همراه فرمت آماده برای قرار دادن در `.env` در ترمینال چاپ می‌کند:

   ```text
   =======================================================
   ✨ NEW PREMIUM CUSTOM EMOJI DETECTED!
   📌 Emoji Symbol   : 💎
   🆔 Custom Emoji ID : 5413351005779672594
   📝 Format for .env : CUSTOM_EMOJI_VIP=5413351005779672594
   =======================================================
   ```
