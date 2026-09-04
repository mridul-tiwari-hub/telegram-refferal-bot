"""Invite Link Service for generating and managing unique referral links via Telegram Bot API."""
from typing import Optional
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession
from database.repositories.referral_repo import ReferralRepository
from database.repositories.moderation_repo import ModerationRepository
from database.models.referral_link import ReferralInviteLink
from database.models.user import User
from database.models.group import Group
from utils.security import generate_referral_code
from utils.logging import get_logger

logger = get_logger(__name__)


class InviteLinkService:
    def __init__(self, session: AsyncSession, bot: Bot) -> None:
        self.session = session
        self.bot = bot
        self.referral_repo = ReferralRepository(session)
        self.mod_repo = ModerationRepository(session)

    async def get_or_create_referral_link(
        self,
        user: User,
        group: Group,
        force_regenerate: bool = False
    ) -> Optional[ReferralInviteLink]:
        """
        Retrieves existing active invite link or generates a new unique Telegram chat invite link.
        """
        if not force_regenerate:
            existing = await self.referral_repo.get_active_invite_link(user.id, group.id)
            if existing:
                return existing

        code = generate_referral_code(length=6)
        link_name = f"Ref-{code}-{user.telegram_user_id}"[:32]

        try:
            # Official Telegram Bot API method: createChatInviteLink
            telegram_link_obj = await self.bot.create_chat_invite_link(
                chat_id=group.telegram_group_id,
                name=link_name,
                creates_join_request=False
            )
            invite_url = telegram_link_obj.invite_link
        except Exception as e:
            logger.error(
                f"Failed to create chat invite link on Telegram for group {group.telegram_group_id}: {e}"
            )
            return None

        # Persist in database
        saved_link = await self.referral_repo.create_invite_link(
            user_id=user.id,
            group_id=group.id,
            referral_code=code,
            telegram_invite_link=invite_url
        )

        await self.mod_repo.add_log(
            action="INVITE_LINK_CREATED",
            group_id=group.id,
            user_id=user.id,
            details=f"Generated referral link {invite_url} with code {code}"
        )

        logger.info(f"Created referral invite link for user {user.telegram_user_id} in group {group.telegram_group_id}: {invite_url}")
        return saved_link

    async def revoke_and_regenerate(self, user: User, group: Group) -> Optional[ReferralInviteLink]:
        """Revokes previous link on Telegram (if possible) and generates a fresh one."""
        old_link = await self.referral_repo.get_active_invite_link(user.id, group.id)
        if old_link:
            try:
                await self.bot.revoke_chat_invite_link(
                    chat_id=group.telegram_group_id,
                    invite_link=old_link.telegram_invite_link
                )
            except Exception as e:
                logger.warning(f"Could not revoke old Telegram invite link {old_link.telegram_invite_link}: {e}")

        return await self.get_or_create_referral_link(user, group, force_regenerate=True)
