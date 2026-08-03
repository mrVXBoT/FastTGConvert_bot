"""app/admin/handlers/__init__.py — Admin Panel master router builder."""

from aiogram import Router

from app.admin.handlers import (
    admins,
    broadcast,
    force_join,
    language,
    panel,
    stats,
    support,
    users,
    vip,
)
from app.admin.middlewares import AdminPermissionMiddleware

admin_router = Router()
admin_router.message.middleware(AdminPermissionMiddleware())
admin_router.callback_query.middleware(AdminPermissionMiddleware())

admin_router.include_routers(
    panel.router,
    stats.router,
    users.router,
    broadcast.router,
    admins.router,
    force_join.router,
    support.router,
    vip.router,
    language.router,
)
