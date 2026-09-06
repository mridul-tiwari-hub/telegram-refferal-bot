"""Administrator filter for verifying Telegram admin status."""
from typing import Union, Optional
from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery
from aiogram.enums import ChatMemberStatus, ChatType


class IsAdminFilter(BaseFilter):
    async def __call__(self, event: Union[Message, CallbackQuery], session: Optional["AsyncSession"] = None) -> bool:
        if isinstance(event, CallbackQuery):
            message = event.message
            user = event.from_user
        else:
            message = event
            user = event.from_user

        if not message or not user:
            return False

        # In private chat, we allow if accessed with a target group or admin mode
        if message.chat.type == ChatType.PRIVATE:
            return True

        # In groups/supergroups, verify using Telegram Bot API get_chat_member
        try:
            member = await message.chat.get_member(user.id)
            if member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
                return True
        except Exception:
            pass

        # Also check if user is configured as bot staff in database
        try:
            from database.repositories.group_repo import GroupRepository
            from database.repositories.user_repo import UserRepository
            from database.repositories.admin_repo import AdminRepository

            async def _check_staff(s):
                group_repo = GroupRepository(s)
                user_repo = UserRepository(s)
                admin_repo = AdminRepository(s)
                group = await group_repo.get_by_telegram_id(message.chat.id)
                if group:
                    db_user = await user_repo.get_by_telegram_id(user.id)
                    if db_user:
                        staff = await admin_repo.get_staff(group.id, db_user.id)
                        if staff:
                            return True
                return False

            if session:
                return await _check_staff(session)

            from database.session import async_session_maker
            async with async_session_maker() as sess:
                return await _check_staff(sess)
        except Exception:
            pass

        return False
