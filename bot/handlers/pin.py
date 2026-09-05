"""Message Pin and Unpin Handlers."""
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ChatType
from sqlalchemy.ext.asyncio import AsyncSession
from database.repositories.group_repo import GroupRepository
from services.permission_service import PermissionService
from utils.logging import get_logger

logger = get_logger(__name__)
pin_router = Router(name="pin_router")


@pin_router.message(Command("pin"))
async def handle_pin(message: Message, session: AsyncSession) -> None:
    """Pins a replied message in the group."""
    if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return

    if not message.reply_to_message:
        await message.answer("Please reply to the message you want to pin with <code>/pin</code>.", parse_mode="HTML")
        return

    group_repo = GroupRepository(session)
    perm_service = PermissionService(session, message.bot)

    group = await group_repo.get_or_create_group(message.chat.id, message.chat.title or "Group")
    can_act, reason = await perm_service.can_perform_action(
        chat_id=message.chat.id,
        actor_tg_id=message.from_user.id,
        required_permission="settings",
        group_db_id=group.id
    )
    if not can_act:
        await message.answer(f"❌ {reason}", parse_mode="HTML")
        return

    try:
        await message.bot.pin_chat_message(
            chat_id=message.chat.id,
            message_id=message.reply_to_message.message_id
        )
        await message.answer("📌 Message pinned successfully!")
    except Exception as e:
        await message.answer(f"Failed to pin message: {e}")


@pin_router.message(Command("unpin"))
async def handle_unpin(message: Message, session: AsyncSession) -> None:
    """Unpins a message in the group."""
    if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return

    group_repo = GroupRepository(session)
    perm_service = PermissionService(session, message.bot)

    group = await group_repo.get_or_create_group(message.chat.id, message.chat.title or "Group")
    can_act, reason = await perm_service.can_perform_action(
        chat_id=message.chat.id,
        actor_tg_id=message.from_user.id,
        required_permission="settings",
        group_db_id=group.id
    )
    if not can_act:
        await message.answer(f"❌ {reason}", parse_mode="HTML")
        return

    try:
        msg_id = message.reply_to_message.message_id if message.reply_to_message else None
        await message.bot.unpin_chat_message(
            chat_id=message.chat.id,
            message_id=msg_id
        )
        await message.answer("🔓 Message unpinned.")
    except Exception as e:
        await message.answer(f"Failed to unpin message: {e}")
