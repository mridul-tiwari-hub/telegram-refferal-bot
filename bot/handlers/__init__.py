"""Handlers package registering all routers."""
from aiogram import Dispatcher
from bot.handlers.admin import admin_router
from bot.handlers.referral import referral_router
from bot.handlers.members import members_router
from bot.handlers.commands import commands_router
from bot.handlers.moderation import moderation_router
from bot.handlers.moderation_extra import moderation_extra_router
from bot.handlers.staff import staff_router
from bot.handlers.filters import filters_router
from bot.handlers.locks import locks_router
from bot.handlers.activity import activity_router
from bot.handlers.security_extra import security_extra_router
from bot.handlers.goodbye import goodbye_router
from bot.handlers.pin import pin_router
from bot.handlers.message_mgmt import message_mgmt_router
from bot.handlers.welcome import welcome_router


def register_all_routers(dp: Dispatcher) -> None:
    """Registers all handler routers to dispatcher."""
    dp.include_router(admin_router)
    dp.include_router(commands_router)
    dp.include_router(moderation_router)
    dp.include_router(moderation_extra_router)
    dp.include_router(staff_router)
    dp.include_router(filters_router)
    dp.include_router(locks_router)
    dp.include_router(activity_router)
    dp.include_router(security_extra_router)
    dp.include_router(goodbye_router)
    dp.include_router(pin_router)
    dp.include_router(message_mgmt_router)
    dp.include_router(welcome_router)
    dp.include_router(referral_router)
    dp.include_router(members_router)
