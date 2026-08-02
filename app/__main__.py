import asyncio
import contextlib
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.cleanup import cleanup_loop
from app.config import get_settings
from app.db.session import build_engine, build_session_factory, create_schema
from app.handlers import build_router


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
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
    dispatcher.include_router(build_router())
    cleanup_task = asyncio.create_task(cleanup_loop(session_factory))

    try:
        await bot.delete_webhook(drop_pending_updates=False)
        await dispatcher.start_polling(
            bot,
            settings=settings,
            session_factory=session_factory,
            allowed_updates=dispatcher.resolve_used_update_types(),
        )
    finally:
        cleanup_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await cleanup_task
        await bot.session.close()
        engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
