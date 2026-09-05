"""Advanced Moderation Service for Ban, Temp-Ban, Mute, Temp-Mute, and Restrictions."""
import re
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
from aiogram import Bot
from aiogram.types import ChatPermissions
from sqlalchemy.ext.asyncio import AsyncSession
from database.models.group import Group
from database.models.user import User
from database.repositories.admin_repo import AdminRepository
from database.repositories.group_repo import GroupRepository
from services.permission_service import PermissionService
from utils.logging import get_logger

logger = get_logger(__name__)


def parse_duration_string(duration_str: str) -> Optional[int]:
    """
    Parses strings like '10m', '2h', '1d', '1w', '30s' into total seconds.
    Returns None if format is invalid.
    """
    if not duration_str:
        return None
    match = re.match(r"^(\d+)([smhdw])$", duration_str.strip().lower())
    if not match:
        return None
    value, unit = int(match.group(1)), match.group(2)
    multipliers = {
        "s": 1,
        "m": 60,
        "h": 3600,
        "d": 86400,
        "w": 604800
    }
    return value * multipliers.get(unit, 1)


class AdvancedModerationService:
    def __init__(self, session: AsyncSession, bot: Bot) -> None:
        self.session = session
        self.bot = bot
        self.admin_repo = AdminRepository(session)
        self.group_repo = GroupRepository(session)
        self.permission_service = PermissionService(session, bot)

    async def ban_member(
        self,
        group: Group,
        target_user: User,
        actor_user: Optional[User] = None,
        duration_seconds: Optional[int] = None,
        reason: str = "Banned by administrator"
    ) -> Tuple[bool, str]:
        """Bans a member permanently or temporarily."""
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=duration_seconds) if duration_seconds else None

        try:
            if expires_at:
                await self.bot.ban_chat_member(
                    chat_id=group.telegram_group_id,
                    user_id=target_user.telegram_user_id,
                    until_date=expires_at
                )
                await self.admin_repo.add_temporary_action(
                    group_id=group.id,
                    user_id=target_user.id,
                    action_type="BAN",
                    expires_at=expires_at,
                    reason=reason
                )
                duration_text = f"for {duration_seconds // 60} minutes" if duration_seconds < 3600 else f"for {duration_seconds // 3600} hours"
                msg = f"Temporarily banned user <code>{target_user.telegram_user_id}</code> {duration_text}."
            else:
                await self.bot.ban_chat_member(
                    chat_id=group.telegram_group_id,
                    user_id=target_user.telegram_user_id
                )
                msg = f"Permanently banned user <code>{target_user.telegram_user_id}</code>."

            await self.permission_service.log_action(
                group=group,
                actor_tg_id=actor_user.telegram_user_id if actor_user else None,
                action="TEMP_BAN" if expires_at else "BAN",
                target_tg_id=target_user.telegram_user_id,
                reason=reason,
                details=f"Until {expires_at.isoformat()}" if expires_at else "Permanent"
            )
            return True, msg
        except Exception as e:
            logger.error(f"Error banning user {target_user.telegram_user_id}: {e}")
            return False, f"Telegram API error: {e}"

    async def unban_member(
        self,
        group: Group,
        target_user: User,
        actor_user: Optional[User] = None
    ) -> Tuple[bool, str]:
        """Unbans a member so they can rejoin."""
        try:
            await self.bot.unban_chat_member(
                chat_id=group.telegram_group_id,
                user_id=target_user.telegram_user_id,
                only_if_banned=True
            )
            # Deactivate any active temporary bans in DB
            actions = await self.admin_repo.get_active_actions_for_user(group.id, target_user.id)
            for act in actions:
                if act.action_type == "BAN":
                    await self.admin_repo.deactivate_temporary_action(act.id)

            await self.permission_service.log_action(
                group=group,
                actor_tg_id=actor_user.telegram_user_id if actor_user else None,
                action="UNBAN",
                target_tg_id=target_user.telegram_user_id,
                details="Unbanned"
            )
            return True, f"Successfully unbanned user <code>{target_user.telegram_user_id}</code>."
        except Exception as e:
            logger.error(f"Error unbanning user {target_user.telegram_user_id}: {e}")
            return False, f"Telegram API error: {e}"

    async def mute_member(
        self,
        group: Group,
        target_user: User,
        actor_user: Optional[User] = None,
        duration_seconds: Optional[int] = None,
        reason: str = "Muted by administrator"
    ) -> Tuple[bool, str]:
        """Mutes a member permanently or temporarily."""
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=duration_seconds) if duration_seconds else None

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

        try:
            if expires_at:
                await self.bot.restrict_chat_member(
                    chat_id=group.telegram_group_id,
                    user_id=target_user.telegram_user_id,
                    permissions=permissions,
                    until_date=expires_at
                )
                await self.admin_repo.add_temporary_action(
                    group_id=group.id,
                    user_id=target_user.id,
                    action_type="MUTE",
                    expires_at=expires_at,
                    reason=reason
                )
                duration_text = f"for {duration_seconds // 60}m" if duration_seconds < 3600 else f"for {duration_seconds // 3600}h"
                msg = f"Temporarily muted user <code>{target_user.telegram_user_id}</code> {duration_text}."
            else:
                await self.bot.restrict_chat_member(
                    chat_id=group.telegram_group_id,
                    user_id=target_user.telegram_user_id,
                    permissions=permissions
                )
                msg = f"Permanently muted user <code>{target_user.telegram_user_id}</code>."

            await self.permission_service.log_action(
                group=group,
                actor_tg_id=actor_user.telegram_user_id if actor_user else None,
                action="TEMP_MUTE" if expires_at else "MUTE",
                target_tg_id=target_user.telegram_user_id,
                reason=reason,
                details=f"Until {expires_at.isoformat()}" if expires_at else "Permanent"
            )
            return True, msg
        except Exception as e:
            logger.error(f"Error muting user {target_user.telegram_user_id}: {e}")
            return False, f"Telegram API error: {e}"

    async def unmute_member(
        self,
        group: Group,
        target_user: User,
        actor_user: Optional[User] = None
    ) -> Tuple[bool, str]:
        """Restores chat permissions for a muted member."""
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

        try:
            await self.bot.restrict_chat_member(
                chat_id=group.telegram_group_id,
                user_id=target_user.telegram_user_id,
                permissions=permissions
            )
            # Deactivate any active temporary mutes in DB
            actions = await self.admin_repo.get_active_actions_for_user(group.id, target_user.id)
            for act in actions:
                if act.action_type == "MUTE":
                    await self.admin_repo.deactivate_temporary_action(act.id)

            await self.permission_service.log_action(
                group=group,
                actor_tg_id=actor_user.telegram_user_id if actor_user else None,
                action="UNMUTE",
                target_tg_id=target_user.telegram_user_id,
                details="Permissions restored"
            )
            return True, f"Unmuted user <code>{target_user.telegram_user_id}</code>."
        except Exception as e:
            logger.error(f"Error unmuting user {target_user.telegram_user_id}: {e}")
            return False, f"Telegram API error: {e}"

    async def process_expired_actions(self) -> int:
        """Background worker method: lifts expired temporary bans and mutes."""
        now = datetime.now(timezone.utc)
        due_actions = await self.admin_repo.get_due_temporary_actions(now)
        processed = 0

        for action in due_actions:
            try:
                group = await self.session.get(Group, action.group_id)
                user = await self.session.get(User, action.user_id)
                if not group or not user:
                    await self.admin_repo.deactivate_temporary_action(action.id)
                    continue

                if action.action_type == "BAN":
                    await self.bot.unban_chat_member(
                        chat_id=group.telegram_group_id,
                        user_id=user.telegram_user_id,
                        only_if_banned=True
                    )
                elif action.action_type == "MUTE":
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

                await self.admin_repo.deactivate_temporary_action(action.id)
                processed += 1
                logger.info(f"Auto-lifted expired {action.action_type} for user {user.telegram_user_id} in {group.telegram_group_id}")
            except Exception as e:
                logger.error(f"Error processing expired action {action.id}: {e}")
                # Still deactivate to prevent loop
                await self.admin_repo.deactivate_temporary_action(action.id)

        return processed
