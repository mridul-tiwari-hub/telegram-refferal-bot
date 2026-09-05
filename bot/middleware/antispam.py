"""Comprehensive Content Moderation & Anti-Spam Middleware."""
from datetime import datetime, timezone, timedelta
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject
from aiogram.enums import ChatType, ChatMemberStatus
from services.spam_service import spam_service
from services.lock_service import LockService
from services.content_filter_service import ContentFilterService
from services.activity_service import ActivityService
from database.repositories.group_repo import GroupRepository
from database.repositories.admin_repo import AdminRepository
from database.repositories.user_repo import UserRepository
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

        # Ignore bot itself
        if message.from_user.is_bot:
            return await handler(event, data)

        session = data.get("session")
        if not session:
            return await handler(event, data)

        group_repo = GroupRepository(session)
        user_repo = UserRepository(session)
        admin_repo = AdminRepository(session)

        group = await group_repo.get_or_create_group(
            telegram_group_id=message.chat.id,
            group_name=message.chat.title or "Group"
        )
        user = await user_repo.get_or_create_user(
            telegram_user_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name
        )

        # 1. Record Member Activity for leaderboard / stats
        act_service = ActivityService(session, message.bot)
        await act_service.record_activity(group.id, user.id)

        # Check if user is an Administrator or Creator - skip restrictions for admins
        is_admin = False
        try:
            member = await message.chat.get_member(message.from_user.id)
            if member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
                is_admin = True
        except Exception:
            pass

        if is_admin:
            return await handler(event, data)

        # Check if configured as bot staff
        staff = await admin_repo.get_staff(group.id, user.id)
        if staff:
            return await handler(event, data)

        settings = await group_repo.get_settings(group.id)
        text = message.text or message.caption or ""

        # 2. Check Content Locks
        lock_service = LockService(session)
        is_locked, lock_reason = await lock_service.is_message_locked(group.id, message)
        if is_locked:
            try:
                await message.delete()
                await message.answer(f"🔒 <b>{message.from_user.first_name}</b>: {lock_reason}", parse_mode="HTML")
            except Exception as e:
                logger.debug(f"Failed to delete locked message: {e}")
            return

        # 3. Check Banned Words & Phrases
        filter_service = ContentFilterService(session)
        has_bad_word, word_matched = await filter_service.check_banned_words(group.id, text)
        if has_bad_word:
            try:
                await message.delete()
                await message.answer(
                    f"🚫 <b>{message.from_user.first_name}</b>, your message contained a banned word/phrase and was removed.",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.debug(f"Failed to delete banned word message: {e}")
            return

        # 4. Check Link Filtering
        has_bad_link, link_reason = await filter_service.check_links(group.id, text)
        if has_bad_link:
            try:
                await message.delete()
                await message.answer(f"🔗 <b>{message.from_user.first_name}</b>: {link_reason}", parse_mode="HTML")
            except Exception as e:
                logger.debug(f"Failed to delete prohibited link: {e}")
            return

        # 5. Check Anti-Spam / Flooding if enabled
        if settings.anti_spam_enabled:
            is_spam, spam_reason = await spam_service.check_message_spam(
                chat_id=message.chat.id,
                user_id=message.from_user.id,
                text=text
            )
            if is_spam:
                logger.warning(f"Anti-spam triggered for user {message.from_user.id} in {message.chat.id}: {spam_reason}")
                try:
                    await message.delete()
                    await message.answer(
                        f"⚠️ <b>{message.from_user.first_name}</b>, message deleted.\nReason: <i>{spam_reason}</i>",
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.debug(f"Failed to delete spam message: {e}")
                return

        # 6. Auto-delete enqueueing if configured
        if settings.auto_delete_seconds > 0:
            del_at = datetime.now(timezone.utc) + timedelta(seconds=settings.auto_delete_seconds)
            await admin_repo.enqueue_auto_delete(group.id, message.message_id, del_at)

        return await handler(event, data)
