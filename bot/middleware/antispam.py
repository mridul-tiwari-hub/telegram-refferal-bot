"""Anti-Spam middleware for inspecting messages in groups."""
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject
from aiogram.enums import ChatType, ChatMemberStatus
from services.spam_service import spam_service
from database.repositories.group_repo import GroupRepository
from utils.logging import get_logger

logger = get_logger(__name__)


class AntiSpamMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        if not isinstance(event, Message):
            return await handler(event, data)

        message: Message = event
        if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP] or not message.from_user:
            return await handler(event, data)

        # Ignore bot itself or anonymous admin
        if message.from_user.is_bot:
            return await handler(event, data)

        # Check if user is admin - skip anti-spam for admins
        try:
            member = await message.chat.get_member(message.from_user.id)
            if member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
                return await handler(event, data)
        except Exception:
            pass

        # Check if anti-spam is enabled for this group
        session = data.get("session")
        if session:
            group_repo = GroupRepository(session)
            group = await group_repo.get_by_telegram_id(message.chat.id)
            if group:
                settings = await group_repo.get_settings(group.id)
                if not settings.anti_spam_enabled:
                    return await handler(event, data)

        text = message.text or message.caption or ""
        is_spam, reason = await spam_service.check_message_spam(
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            text=text
        )

        if is_spam:
            logger.warning(
                f"Anti-spam triggered for user {message.from_user.id} in chat {message.chat.id}: {reason}"
            )
            try:
                # Delete the spam message
                await message.delete()
                # Send temporary warning notice to user in chat
                warn_msg = await message.answer(
                    f"⚠️ <b>{message.from_user.first_name}</b>, your message was deleted.\nReason: <i>{reason}</i>",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.debug(f"Failed to delete spam message: {e}")

            # Do not propagate event to handlers
            return

        return await handler(event, data)
