"""Moderation Service for executing Telegram moderation actions."""
from typing import Optional
from aiogram import Bot
from aiogram.types import ChatPermissions
from sqlalchemy.ext.asyncio import AsyncSession
from database.repositories.moderation_repo import ModerationRepository
from database.models.user import User
from database.models.group import Group
from app.config import settings
from utils.logging import get_logger

logger = get_logger(__name__)


class ModerationService:
    def __init__(self, session: AsyncSession, bot: Bot) -> None:
        self.session = session
        self.bot = bot
        self.mod_repo = ModerationRepository(session)

    async def notify_admin_channel(self, text: str) -> None:
        """Sends moderation event notification to designated admin log chat if configured."""
        if settings.ADMIN_LOG_CHAT_ID:
            try:
                await self.bot.send_message(chat_id=settings.ADMIN_LOG_CHAT_ID, text=text)
            except Exception as e:
                logger.warning(f"Failed to forward log to ADMIN_LOG_CHAT_ID: {e}")

    async def kick_member(
        self,
        group: Group,
        user: User,
        admin_user_id: Optional[int] = None,
        reason: str = "Referral deadline failure / Kicked"
    ) -> bool:
        """
        Kicks a user from the group.
        Performs ban followed by immediate unban so the user is not permanently banned.
        """
        try:
            # Step 1: Ban user to remove them from group
            await self.bot.ban_chat_member(
                chat_id=group.telegram_group_id,
                user_id=user.telegram_user_id
            )
            # Step 2: Unban immediately so user can rejoin in the future
            await self.bot.unban_chat_member(
                chat_id=group.telegram_group_id,
                user_id=user.telegram_user_id,
                only_if_banned=True
            )

            await self.mod_repo.add_log(
                action="KICK",
                group_id=group.id,
                user_id=user.id,
                admin_user_id=admin_user_id,
                details=f"Reason: {reason}"
            )
            await self.notify_admin_channel(
                f"🚫 <b>KICK</b>\nUser: {user.first_name} (ID: {user.telegram_user_id})\nGroup: {group.group_name}\nReason: {reason}"
            )
            logger.info(f"Kicked user {user.telegram_user_id} from group {group.telegram_group_id}")
            return True
        except Exception as e:
            logger.error(f"Error kicking user {user.telegram_user_id}: {e}")
            return False

    async def restrict_member(
        self,
        group: Group,
        user: User,
        admin_user_id: Optional[int] = None,
        reason: str = "Referral deadline failure / Restricted"
    ) -> bool:
        """Restricts a member from sending messages or media."""
        try:
            permissions = ChatPermissions(
                can_send_messages=False,
                can_send_audios=False,
                can_send_documents=False,
                can_send_photos=False,
                can_send_videos=False,
                can_send_video_notes=False,
                can_send_voice_notes=False,
                can_send_polls=False,
                can_send_other_messages=False,
                can_add_web_page_previews=False
            )
            await self.bot.restrict_chat_member(
                chat_id=group.telegram_group_id,
                user_id=user.telegram_user_id,
                permissions=permissions
            )

            await self.mod_repo.add_log(
                action="RESTRICT",
                group_id=group.id,
                user_id=user.id,
                admin_user_id=admin_user_id,
                details=f"Reason: {reason}"
            )
            await self.notify_admin_channel(
                f"🔇 <b>RESTRICT</b>\nUser: {user.first_name} (ID: {user.telegram_user_id})\nGroup: {group.group_name}\nReason: {reason}"
            )
            logger.info(f"Restricted user {user.telegram_user_id} in group {group.telegram_group_id}")
            return True
        except Exception as e:
            logger.error(f"Error restricting user {user.telegram_user_id}: {e}")
            return False

    async def unrestrict_member(
        self,
        group: Group,
        user: User,
        admin_user_id: Optional[int] = None
    ) -> bool:
        """Restores normal member permissions."""
        try:
            permissions = ChatPermissions(
                can_send_messages=True,
                can_send_audios=True,
                can_send_documents=True,
                can_send_photos=True,
                can_send_videos=True,
                can_send_video_notes=True,
                can_send_voice_notes=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True
            )
            await self.bot.restrict_chat_member(
                chat_id=group.telegram_group_id,
                user_id=user.telegram_user_id,
                permissions=permissions
            )

            await self.mod_repo.add_log(
                action="UNRESTRICT",
                group_id=group.id,
                user_id=user.id,
                admin_user_id=admin_user_id,
                details="Permissions restored"
            )
            await self.notify_admin_channel(
                f"🔊 <b>UNRESTRICT</b>\nUser: {user.first_name} (ID: {user.telegram_user_id})\nGroup: {group.group_name}"
            )
            logger.info(f"Unrestricted user {user.telegram_user_id} in group {group.telegram_group_id}")
            return True
        except Exception as e:
            logger.error(f"Error unrestricting user {user.telegram_user_id}: {e}")
            return False
