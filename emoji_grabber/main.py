"""
Telegram Custom Emoji Finder (Userbot)
--------------------------------------
Log into your Telegram account, send any Premium Custom Emoji to "Saved Messages" (me),
and this script will instantly print its 19-digit Custom Emoji ID in the terminal.

PACK MODE:
Reply to any message in "Saved Messages" that contains a Premium Custom Emoji,
and the script will fetch the ENTIRE emoji pack and save every emoji + its ID to a file.
"""

import asyncio
import os
import sys
from datetime import datetime, timezone

UTC = timezone.utc  # noqa: UP017  (py<3.11 compat)
from pathlib import Path

from telethon import TelegramClient, events  # type: ignore[import-untyped]
from telethon.tl.functions.messages import (  # type: ignore[import-untyped]
    GetCustomEmojiDocumentsRequest,
    GetStickerSetRequest,
)
from telethon.tl.types import (  # type: ignore[import-untyped]
    DocumentAttributeCustomEmoji,
    MessageEntityCustomEmoji,
)

API_ID = os.environ.get("TELEGRAM_API_ID")
API_HASH = os.environ.get("TELEGRAM_API_HASH")

OUTPUT_DIR = Path(__file__).resolve().parent / "emoji_packs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


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


def _custom_emoji_ids(msg) -> list[int]:
    """Return all custom emoji document IDs found in a message."""
    if not msg or not msg.entities:
        return []
    return [
        entity.document_id
        for entity in msg.entities
        if isinstance(entity, MessageEntityCustomEmoji)
    ]


async def _resolve_pack(client, emoji_doc_id: int):
    """Resolve the sticker set (pack) that a custom emoji belongs to."""
    docs = await client(GetCustomEmojiDocumentsRequest(document_id=[emoji_doc_id]))
    if not docs:
        raise ValueError(f"❌ Could not resolve document {emoji_doc_id}")
    doc = docs[0]

    sticker_attr = next(
        (a for a in doc.attributes if isinstance(a, DocumentAttributeCustomEmoji)), None
    )
    if sticker_attr is None or sticker_attr.stickerset is None:
        raise ValueError(f"❌ No sticker set info for document {emoji_doc_id}")

    stickerset = sticker_attr.stickerset
    return await client(
        GetStickerSetRequest(stickerset=stickerset, hash=0)
    )


def _emoji_doc_map(pack) -> list[tuple[str, int]]:
    """Build (emoticon, document_id) pairs for every emoji in the pack."""
    pairs: list[tuple[str, int]] = []
    for sticker_pack in pack.packs:
        for doc_id in sticker_pack.documents:
            pairs.append((sticker_pack.emoticon, doc_id))
    return pairs


def _save_pack(pack, pairs: list[tuple[str, int]]) -> Path:
    """Save the whole pack to a file and return the file path."""
    set_info = pack.set
    set_name = set_info.short_name or str(set_info.id)
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    out_path = OUTPUT_DIR / f"{set_name}_{timestamp}.txt"

    lines = [
        f"# Pack: {set_info.title}",
        f"# Set ID: {set_info.id}",
        f"# Short name: {set_name}",
        f"# Emojis: {len(pairs)}",
        f"# Saved: {timestamp}",
    ]
    lines += [f"{emoticon}\t{doc_id}" for emoticon, doc_id in pairs]
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path


async def handle_reply(client, event: events.NewMessage.Event) -> None:
    """Reply mode: reply to a premium emoji -> dump the whole pack to a file."""
    replied = await event.message.get_reply_message()
    if replied is None:
        return

    emoji_ids = _custom_emoji_ids(replied)
    if not emoji_ids:
        print("\n⚠️  Replied message contains no Premium Custom Emoji.")
        return

    print("\n" + "=" * 55)
    print("🎁 PACK MODE: fetching emoji pack...")

    seen_packs: set[int] = set()
    for emoji_id in emoji_ids:
        try:
            pack = await _resolve_pack(client, emoji_id)
        except Exception as err:  # noqa: BLE001
            print(f"❌ Failed for emoji {emoji_id}: {err}")
            continue

        set_id = pack.set.id
        if set_id in seen_packs:
            continue
        seen_packs.add(set_id)

        pairs = _emoji_doc_map(pack)
        out_path = _save_pack(pack, pairs)

        print(f"📦 Pack      : {pack.set.title}")
        print(f"🆔 Set ID    : {set_id}")
        print(f"🔢 Emoji Count: {len(pairs)}")
        for emoticon, doc_id in pairs:
            print(f"   {emoticon}  ->  {doc_id}")
        print(f"💾 Saved to  : {out_path}")
        print("=" * 55 + "\n")

    if not seen_packs:
        print("❌ Could not resolve any pack.")
        print("=" * 55 + "\n")


async def main() -> None:
    api_id, api_hash = get_credentials()
    session_name = "emoji_finder_session"
    client = TelegramClient(session_name, api_id, api_hash)

    @client.on(events.NewMessage(chats="me"))
    async def handle_saved_messages(event: events.NewMessage.Event) -> None:
        msg = event.message
        if not msg:
            return

        if msg.reply_to is not None:
            await handle_reply(client, event)
            return

        if not msg.entities:
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
    print("🎁 Or REPLY to a Custom Emoji message to dump the whole pack to a file.")
    print("Press Ctrl+C to exit.\n")
    await client.run_until_disconnected()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Userbot stopped.")
