"""Handlers package."""
from aiogram import Dispatcher
from bot.handlers.admin import admin_router
from bot.handlers.referral import referral_router
from bot.handlers.members import members_router
from bot.handlers.commands import commands_router
from bot.handlers.moderation import moderation_router
from bot.handlers.welcome import welcome_router


def register_all_routers(dp: Dispatcher) -> None:
    """Registers all handler routers to dispatcher."""
    dp.include_router(admin_router)
    dp.include_router(commands_router)
    dp.include_router(moderation_router)
    dp.include_router(welcome_router)
    dp.include_router(referral_router)
    dp.include_router(members_router)
