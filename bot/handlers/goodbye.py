"""Goodbye Message Handlers and Events."""
from aiogram import Router
from aiogram.types import Message, ChatMemberUpdated
from aiogram.filters import Command, ChatMemberUpdatedFilter, KICKED, LEFT
from aiogram.enums import ChatType
from sqlalchemy.ext.asyncio import AsyncSession
from database.repositories.group_repo import GroupRepository
from services.permission_service import PermissionService
from utils.logging import get_logger

logger = get_logger(__name__)
goodbye_router = Router(name="goodbye_router")


@goodbye_router.message(Command("goodbye"))
async def handle_goodbye_status(message: Message, session: AsyncSession) -> None:
    """Displays current goodbye message configuration."""
    if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return

    group_repo = GroupRepository(session)
    group = await group_repo.get_or_create_group(message.chat.id, message.chat.title or "Group")
    settings = await group_repo.get_settings(group.id)

    text = (
        f"👋 <b>GOODBYE MESSAGE SETTINGS — {group.group_name}</b>\n\n"
        f"• Status: <b>{'ENABLED' if settings.goodbye_enabled else 'DISABLED'}</b>\n"
        f"• Current Message:\n<i>{settings.goodbye_message}</i>\n\n"
        f"Commands:\n"
        f"• <code>/setgoodbye &lt;message&gt;</code> (Supports variables: <code>{{first_name}}</code>, <code>{{username}}</code>, <code>{{group}}</code>)\n"
        f"• <code>/togglegoodbye</code> to turn on/off."
    )
    await message.answer(text, parse_mode="HTML")


@goodbye_router.message(Command("togglegoodbye"))
async def handle_togglegoodbye(message: Message, session: AsyncSession) -> None:
    """Toggles goodbye messages on or off."""
    if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return

    group_repo = GroupRepository(session)
    perm_service = PermissionService(session, message.bot)

    group = await group_repo.get_or_create_group(message.chat.id, message.chat.title or "Group")
    can_act, reason = await perm_service.can_perform_action(
        chat_id=message.chat.id,
        actor_tg_id=message.from_user.id,
        required_permission="welcome",
        group_db_id=group.id
    )
    if not can_act:
        await message.answer(f"❌ {reason}", parse_mode="HTML")
        return

    settings = await group_repo.get_settings(group.id)
    new_status = not settings.goodbye_enabled
    await group_repo.update_settings(group.id, goodbye_enabled=new_status)
    await message.answer(f"✅ Goodbye messages are now <b>{'ENABLED' if new_status else 'DISABLED'}</b>.", parse_mode="HTML")


@goodbye_router.message(Command("setgoodbye"))
async def handle_setgoodbye(message: Message, session: AsyncSession) -> None:
    """Updates the goodbye message template."""
    if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return

    group_repo = GroupRepository(session)
    perm_service = PermissionService(session, message.bot)

    group = await group_repo.get_or_create_group(message.chat.id, message.chat.title or "Group")
    can_act, reason = await perm_service.can_perform_action(
        chat_id=message.chat.id,
        actor_tg_id=message.from_user.id,
        required_permission="welcome",
        group_db_id=group.id
    )
    if not can_act:
        await message.answer(f"❌ {reason}", parse_mode="HTML")
        return

    tokens = message.text.split(maxsplit=1)
    if len(tokens) < 2:
        await message.answer(
            "Usage: <code>/setgoodbye &lt;message&gt;</code>\n"
            "Supported tags: <code>{first_name}</code>, <code>{last_name}</code>, <code>{username}</code>, <code>{group}</code>",
            parse_mode="HTML"
        )
        return

    new_msg = tokens[1]
    await group_repo.update_settings(group.id, goodbye_message=new_msg, goodbye_enabled=True)
    await message.answer("✅ Goodbye message updated and enabled!", parse_mode="HTML")


@goodbye_router.chat_member(ChatMemberUpdatedFilter(member_status_changed=(KICKED | LEFT)))
async def on_member_leave_or_kicked(event: ChatMemberUpdated, session: AsyncSession) -> None:
    """Sends goodbye message when a member leaves or is removed."""
    if event.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return

    group_repo = GroupRepository(session)
    group = await group_repo.get_by_telegram_id(event.chat.id)
    if not group:
        return

    settings = await group_repo.get_settings(group.id)
    if not settings.goodbye_enabled or not settings.goodbye_message:
        return

    user = event.old_chat_member.user
    text = settings.goodbye_message.format(
        first_name=user.first_name,
        last_name=user.last_name or "",
        username=f"@{user.username}" if user.username else user.first_name,
        user_id=user.id,
        group=event.chat.title or "our group"
    )

    try:
        await event.bot.send_message(chat_id=event.chat.id, text=text)
    except Exception as e:
        logger.debug(f"Failed to send goodbye message: {e}")
