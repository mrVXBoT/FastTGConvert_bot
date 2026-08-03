"""app/ui/entities.py — Custom Emoji MessageEntity helper functions for text formatting."""

from __future__ import annotations

from aiogram.types import MessageEntity

from app.ui.emojis import EmojiRegistry


def create_custom_emoji_entity(
    offset: int,
    length: int,
    custom_emoji_id: str,
) -> MessageEntity:
    """Construct a Telegram MessageEntity of type 'custom_emoji'."""
    return MessageEntity(
        type="custom_emoji",
        offset=offset,
        length=length,
        custom_emoji_id=custom_emoji_id,
    )


def format_text_with_custom_emojis(
    text: str,
    emoji_key: str,
) -> tuple[str, list[MessageEntity]]:
    """Format text prepended with emoji and return (formatted_text, entities_list).

    If custom_emoji_id is set for emoji_key, adds a MessageEntity for it;
    otherwise returns standard unicode emoji text with an empty entities list.
    """
    unicode_emoji, custom_id = EmojiRegistry.resolve_icon(emoji_key)
    full_text = f"{unicode_emoji} {text}"
    entities: list[MessageEntity] = []

    if custom_id:
        entities.append(
            create_custom_emoji_entity(
                offset=0,
                length=len(unicode_emoji),
                custom_emoji_id=custom_id,
            )
        )

    return full_text, entities
