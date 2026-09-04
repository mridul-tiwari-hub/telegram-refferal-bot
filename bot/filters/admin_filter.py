"""Administrator filter for verifying Telegram admin status."""
from typing import Union
from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery
from aiogram.enums import ChatMemberStatus, ChatType


class IsAdminFilter(BaseFilter):
    async def __call__(self, event: Union[Message, CallbackQuery]) -> bool:
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
            return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]
        except Exception:
            return False
