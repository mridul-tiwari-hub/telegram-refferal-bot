"""Captcha & New Member Verification Service."""
from datetime import datetime, timezone, timedelta
from typing import Optional
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions
from sqlalchemy.ext.asyncio import AsyncSession
from database.models.group import Group
from database.models.user import User
from database.repositories.admin_repo import AdminRepository
from utils.logging import get_logger

logger = get_logger(__name__)


def get_captcha_keyboard(group_id: int, user_id: int) -> InlineKeyboardMarkup:
    """Creates single-tap human verification button."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ I am Human (Verify)",
                    callback_data=f"cpt_vfy:{group_id}:{user_id}"
                )
            ]
        ]
    )


class CaptchaService:
    def __init__(self, session: AsyncSession, bot: Bot) -> None:
        self.session = session
        self.bot = bot
        self.admin_repo = AdminRepository(session)

    async def prompt_captcha(self, group: Group, user: User, timeout_seconds: int = 180) -> Optional[int]:
        """Restricts new member and sends verification challenge."""
        try:
            # 1. Restrict member temporarily until verified
            restricted_perms = ChatPermissions(
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
                permissions=restricted_perms
            )

            # 2. Send challenge message
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=timeout_seconds)
            text = (
                f"🛡 <b>Verification Required</b>\n\n"
                f"Welcome {user.first_name}! To prevent automated spam, please click the button below within {timeout_seconds // 60} minute(s) to verify your account."
            )
            sent_msg = await self.bot.send_message(
                chat_id=group.telegram_group_id,
                text=text,
                reply_markup=get_captcha_keyboard(group.id, user.id)
            )

            # 3. Store pending captcha
            await self.admin_repo.create_captcha(
                group_id=group.id,
                user_id=user.id,
                message_id=sent_msg.message_id,
                answer="VERIFIED",
                expires_at=expires_at
            )
            return sent_msg.message_id
        except Exception as e:
            logger.error(f"Failed to prompt captcha for user {user.telegram_user_id}: {e}")
            return None

    async def verify_member(self, group: Group, user: User) -> bool:
        """Verifies member and restores default permissions."""
        pending = await self.admin_repo.get_pending_captcha(group.id, user.id)
        if not pending:
            return False

        try:
            # Restore normal permissions
            allowed_perms = ChatPermissions(
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
                permissions=allowed_perms
            )

            # Delete challenge message
            try:
                await self.bot.delete_message(
                    chat_id=group.telegram_group_id,
                    message_id=pending.message_id
                )
            except Exception:
                pass

            await self.admin_repo.verify_captcha(pending.id)
            return True
        except Exception as e:
            logger.error(f"Error verifying captcha for user {user.telegram_user_id}: {e}")
            return False

    async def process_expired_captchas(self) -> int:
        """Worker method: kicks or restricts unverified members after timeout."""
        now = datetime.now(timezone.utc)
        expired = await self.admin_repo.get_expired_captchas(now)
        processed = 0

        for pending in expired:
            try:
                group = await self.session.get(Group, pending.group_id)
                user = await self.session.get(User, pending.user_id)
                if group and user:
                    # Remove unverified user (kick: ban followed by unban)
                    await self.bot.ban_chat_member(
                        chat_id=group.telegram_group_id,
                        user_id=user.telegram_user_id
                    )
                    await self.bot.unban_chat_member(
                        chat_id=group.telegram_group_id,
                        user_id=user.telegram_user_id,
                        only_if_banned=True
                    )
                    # Delete challenge message
                    try:
                        await self.bot.delete_message(
                            chat_id=group.telegram_group_id,
                            message_id=pending.message_id
                        )
                    except Exception:
                        pass
                await self.admin_repo.verify_captcha(pending.id)
                processed += 1
            except Exception as e:
                logger.error(f"Error processing expired captcha {pending.id}: {e}")
                await self.admin_repo.verify_captcha(pending.id)

        return processed
