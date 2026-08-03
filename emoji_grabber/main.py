"""
Telegram Custom Emoji Finder (Userbot)
--------------------------------------
Log into your Telegram account, send any Premium Custom Emoji to "Saved Messages" (me),
and this script will instantly print its 19-digit Custom Emoji ID in the terminal.
"""

import asyncio
import os
import sys

from telethon import TelegramClient, events  # type: ignore[import-untyped]
from telethon.tl.types import MessageEntityCustomEmoji  # type: ignore[import-untyped]

API_ID = os.environ.get("TELEGRAM_API_ID")
API_HASH = os.environ.get("TELEGRAM_API_HASH")


def get_credentials() -> tuple[int, str]:
    api_id_val = API_ID
    api_hash_val = API_HASH

    final_api_id: int = 0
    final_api_hash: str = ""

    if not api_id_val or not api_hash_val:
        print("📌 Enter your Telegram API credentials (from https://my.telegram.org):")
        try:
            if not api_id_val:
                api_id_input = input("API ID: ").strip()
                final_api_id = int(api_id_input)
            else:
                final_api_id = int(api_id_val)
            if not api_hash_val:
                final_api_hash = input("API HASH: ").strip()
            else:
                final_api_hash = api_hash_val
        except ValueError as err:
            print(f"❌ Invalid credentials: {err}")
            sys.exit(1)
    else:
        final_api_id = int(api_id_val)
        final_api_hash = api_hash_val

    return final_api_id, final_api_hash


async def main() -> None:
    api_id, api_hash = get_credentials()
    session_name = "emoji_finder_session"
    client = TelegramClient(session_name, api_id, api_hash)

    @client.on(events.NewMessage(chats="me"))
    async def handle_saved_messages(event: events.NewMessage.Event) -> None:
        msg = event.message
        if not msg or not msg.entities:
            return

        for entity in msg.entities:
            if isinstance(entity, MessageEntityCustomEmoji):
                emoji_text = (
                    msg.text[entity.offset : entity.offset + entity.length]
                    if msg.text
                    else "✨"
                )
                emoji_id = entity.document_id

                print("\n" + "=" * 55)
                print("✨ NEW PREMIUM CUSTOM EMOJI DETECTED!")
                print(f"📌 Emoji Symbol   : {emoji_text}")
                print(f"🆔 Custom Emoji ID : {emoji_id}")
                print(f"📝 Format for .env : CUSTOM_EMOJI_KEY={emoji_id}")
                print("=" * 55 + "\n")

    print("🚀 Starting Telegram Custom Emoji Finder Userbot...")
    await client.start()
    me = await client.get_me()
    print(f"✅ Logged in as: {me.first_name} (@{me.username or me.id})")
    print("📩 Send any Custom Emoji to your Saved Messages ('Saved Messages').")
    print("Press Ctrl+C to exit.\n")
    await client.run_until_disconnected()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Userbot stopped.")
