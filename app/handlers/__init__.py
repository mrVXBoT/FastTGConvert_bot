"""app/handlers/__init__.py — Master root router builder for user-facing handlers."""

from aiogram import Router

from app.handlers import files, otp, start, vip
from app.middlewares import UserStatusMiddleware


def build_router() -> Router:
    router = Router(name="root")
    router.message.middleware(UserStatusMiddleware())
    router.callback_query.middleware(UserStatusMiddleware())
    router.inline_query.middleware(UserStatusMiddleware())
    router.include_routers(start.router, vip.router, files.router, otp.router)
    return router
