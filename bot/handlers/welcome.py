"""Welcome Configuration Handlers."""
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ChatType
from sqlalchemy.ext.asyncio import AsyncSession
from database.repositories.group_repo import GroupRepository
from bot.filters.admin_filter import IsAdminFilter
from services.permission_service import PermissionService

welcome_router = Router(name="welcome_router")
welcome_router.message.filter(IsAdminFilter())


@welcome_router.message(Command("welcome"))
async def handle_welcome_status(message: Message, session: AsyncSession) -> None:
    """Displays current welcome message configuration."""
    if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return

    group_repo = GroupRepository(session)
    group = await group_repo.get_or_create_group(message.chat.id, message.chat.title or "Group")
    settings = await group_repo.get_settings(group.id)

    text = (
        f"👋 <b>WELCOME MESSAGE SETTINGS — {group.group_name}</b>\n\n"
        f"• Status: <b>{'ENABLED' if settings.welcome_enabled else 'DISABLED'}</b>\n"
        f"• Current Template:\n<i>{settings.welcome_message}</i>\n\n"
        f"Commands:\n"
        f"• <code>/setwelcome &lt;message&gt;</code>\n"
        f"• <code>/togglewelcome</code> to toggle on/off"
    )
    await message.answer(text, parse_mode="HTML")


@welcome_router.message(Command("togglewelcome"))
async def handle_togglewelcome(message: Message, session: AsyncSession) -> None:
    """Toggles welcome message on/off."""
    if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return

    group_repo = GroupRepository(session)
    group = await group_repo.get_or_create_group(message.chat.id, message.chat.title or "Group")
    settings = await group_repo.get_settings(group.id)
    new_val = not settings.welcome_enabled
    await group_repo.update_settings(group.id, welcome_enabled=new_val)
    await message.answer(f"✅ Welcome messages are now <b>{'ENABLED' if new_val else 'DISABLED'}</b>.", parse_mode="HTML")


@welcome_router.message(Command("setwelcome"))
async def handle_setwelcome(message: Message, session: AsyncSession) -> None:
    """Sets custom welcome message for the group."""
    if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        await message.answer("Please use this command inside the group.")
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        help_text = (
            "<b>Usage:</b> <code>/setwelcome &lt;your message&gt;</code>\n\n"
            "Supported placeholders:\n"
            "• <code>{first_name}</code> - Member's first name\n"
            "• <code>{username}</code> - Member's username\n"
            "• <code>{group_name}</code> - Group title\n"
            "• <code>{required_referrals}</code> - Required referral count\n"
            "• <code>{deadline_hours}</code> - Referral deadline in hours\n\n"
            "<i>Example:</i>\n"
            "<code>/setwelcome Hello {first_name}! Welcome to {group_name}. Invite {required_referrals} friends in {deadline_hours}h to stay!</code>"
        )
        await message.answer(help_text, parse_mode="HTML")
        return

    welcome_template = args[1]
    group_repo = GroupRepository(session)
    group = await group_repo.get_or_create_group(
        telegram_group_id=message.chat.id,
        group_name=message.chat.title or "Group"
    )
    await group_repo.update_settings(group.id, welcome_message=welcome_template, welcome_enabled=True)

    await message.answer("✅ <b>Welcome message updated and enabled successfully!</b>", parse_mode="HTML")
