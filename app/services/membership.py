from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramAPIError

ALLOWED_STATUSES = {
    ChatMemberStatus.CREATOR,
    ChatMemberStatus.ADMINISTRATOR,
    ChatMemberStatus.MEMBER,
    ChatMemberStatus.RESTRICTED,
}


async def missing_memberships(
    bot: Bot, user_id: int, channels: tuple[str, ...]
) -> list[str]:
    missing: list[str] = []
    for channel in channels:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
        except TelegramAPIError:
            # A bad channel configuration must not silently grant access.
            missing.append(channel)
            continue
        if member.status not in ALLOWED_STATUSES:
            missing.append(channel)
    return missing
