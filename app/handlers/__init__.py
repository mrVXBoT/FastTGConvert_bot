from aiogram import Router

from app.handlers import files, otp, start


def build_router() -> Router:
    router = Router(name="root")
    router.include_routers(start.router, files.router, otp.router)
    return router
