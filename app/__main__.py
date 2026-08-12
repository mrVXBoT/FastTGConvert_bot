import asyncio
import contextlib
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeDefault

from app.cleanup import cleanup_loop
from app.config import get_settings
from app.core import setup_logging
from app.db.session import build_engine, build_session_factory, create_schema
from app.handlers import build_router
from app.middlewares import TracingMiddleware


async def setup_bot_commands(bot: Bot) -> None:
    commands = [
        BotCommand(command="start", description="restart 🚀"),
        BotCommand(command="referral", description="your referral link 🔗"),
        BotCommand(command="proxy", description="Set your proxy 🎯"),
        BotCommand(command="language", description="Change your language 🌍"),
    ]
    await bot.set_my_commands(commands=commands, scope=BotCommandScopeDefault())


async def main() -> None:
    setup_logging(log_level=os.getenv("LOG_LEVEL", "INFO"), json_format=True)
    settings = get_settings()
    settings.storage_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(__name__)
    if not settings.proxy_encryption_key:
        logger.warning(
            "PROXY_ENCRYPTION_KEY is not set. Proxy passwords supplied by users "
            "will NOT be encrypted (stored in plaintext). Authenticated proxies "
            "require this key — set it to a Fernet-compatible secret before "
            "going to production."
        )
    if settings.metrics_enabled and not settings.metrics_auth_token:
        logger.warning(
            "METRICS_AUTH_TOKEN is not set while metrics are enabled. The "
            "Prometheus /metrics endpoint is exposed WITHOUT authentication — "
            "keep metrics_host bound to 127.0.0.1.",
        )

    engine = build_engine(settings.database_url)
    session_factory = build_session_factory(engine)
    create_schema(engine)

    from app.services.mass_message import recover_interrupted_mass_message_jobs

    recovered_jobs = recover_interrupted_mass_message_jobs(session_factory)
    if recovered_jobs:
        logger = logging.getLogger(__name__)
        logger.info(
            "Recovered %d interrupted mass-message jobs into paused state",
            len(recovered_jobs),
        )

    from app.services.broadcast import BROADCAST_WORKER

    with session_factory() as broadcast_session:
        restored_broadcasts = await BROADCAST_WORKER.restore_unprocessed_jobs(
            broadcast_session
        )
    if restored_broadcasts:
        logger = logging.getLogger(__name__)
        logger.info(
            "Restored %d unfinished broadcast jobs from database",
            len(restored_broadcasts),
        )

    # Auto-register the system owner (ADMIN_ID from .env) with SUPER_ADMIN role if not already present
    if settings.admin_id:
        from app.db.repositories import add_admin_user, get_admin_role

        logger = logging.getLogger(__name__)
        with session_factory() as session:
            existing_role = get_admin_role(session, settings.admin_id)
            if not existing_role or existing_role not in ("OWNER", "SUPER_ADMIN"):
                add_admin_user(session, settings.admin_id, role="SUPER_ADMIN")
                logger.info("System owner %d registered with SUPER_ADMIN role.", settings.admin_id)

    from app.ui import EmojiRegistry
    EmojiRegistry.load_from_settings(settings)
    with session_factory() as session:
        EmojiRegistry.load_from_db(session)

    proxy_url = settings.bot_proxy or os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY") or os.getenv("all_proxy")
    if proxy_url:
        from aiogram.client.session.aiohttp import AiohttpSession

        bot_session = AiohttpSession(proxy=proxy_url)
        bot = Bot(
            token=settings.bot_token,
            session=bot_session,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
    else:
        bot = Bot(
            token=settings.bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )

    from aiogram.methods import (
        EditMessageCaption,
        EditMessageText,
        SendDocument,
        SendMessage,
        SendPhoto,
    )

    @bot.session.middleware
    async def emoji_enrich_middleware(make_request, b_inst, method):
        if isinstance(method, (SendMessage, EditMessageText)) and method.text:
            method.text = EmojiRegistry.enrich_flags(EmojiRegistry.enrich_text(method.text))
        elif isinstance(method, (SendDocument, SendPhoto, EditMessageCaption)) and method.caption:
            method.caption = EmojiRegistry.enrich_flags(EmojiRegistry.enrich_text(method.caption))
        return await make_request(b_inst, method)

    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.update.outer_middleware(TracingMiddleware())
    
    from app.admin.handlers import admin_router
    dispatcher.include_router(admin_router)
    dispatcher.include_router(build_router())
    cleanup_task = asyncio.create_task(
        cleanup_loop(
            session_factory,
            payment_expiry_grace_seconds=settings.payment_expiry_grace_seconds,
            storage_dir=settings.storage_dir,
            staged_session_max_age_minutes=max(settings.retention_minutes, 360),
        )
    )

    from app.services.payments import payment_polling_loop

    payment_task = asyncio.create_task(
        payment_polling_loop(session_factory, bot, settings)
    )

    metrics_server = None
    if settings.metrics_enabled:
        from app.core.metrics_server import start_metrics_server

        try:
            metrics_server = await start_metrics_server(
                host=settings.metrics_host,
                port=settings.metrics_port,
                auth_token=settings.metrics_auth_token,
            )
        except OSError as exc:
            logger.warning(
                "Metrics server could not bind to %s:%d (%s). Continuing "
                "without metrics — the bot itself is unaffected.",
                settings.metrics_host,
                settings.metrics_port,
                exc,
            )
            metrics_server = None

    try:
        await bot.delete_webhook(drop_pending_updates=False)
        await setup_bot_commands(bot)
        await dispatcher.start_polling(
            bot,
            settings=settings,
            session_factory=session_factory,
            allowed_updates=dispatcher.resolve_used_update_types(),
        )
    finally:
        if metrics_server:
            metrics_server.close()
            await metrics_server.wait_closed()
        cleanup_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await cleanup_task
        payment_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await payment_task
        await bot.session.close()
        
        # Graceful Shutdown Database Backup
        from app.db.backup import perform_database_backup, sqlite_db_path_from_url

        perform_database_backup(db_path=sqlite_db_path_from_url(settings.database_url))
        engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
