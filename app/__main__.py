import asyncio
import contextlib
import logging

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
    setup_logging(log_level="INFO", json_format=True)
    settings = get_settings()
    settings.storage_dir.mkdir(parents=True, exist_ok=True)

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

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.update.outer_middleware(TracingMiddleware())
    
    from app.admin.handlers import admin_router
    dispatcher.include_router(admin_router)
    dispatcher.include_router(build_router())
    cleanup_task = asyncio.create_task(cleanup_loop(session_factory))

    metrics_server = None
    if settings.metrics_enabled:
        from app.core.metrics_server import start_metrics_server

        metrics_server = await start_metrics_server(
            host=settings.metrics_host,
            port=settings.metrics_port,
            auth_token=settings.metrics_auth_token,
        )

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
        await bot.session.close()
        
        # Graceful Shutdown Database Backup
        from app.db.backup import perform_database_backup

        perform_database_backup()
        engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
