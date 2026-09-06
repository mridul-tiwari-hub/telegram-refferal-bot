"""Centralized Permission & Hierarchy Service."""
from enum import IntEnum
from typing import Optional, Tuple
from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from sqlalchemy.ext.asyncio import AsyncSession
from database.repositories.admin_repo import AdminRepository
from database.repositories.group_repo import GroupRepository
from database.repositories.user_repo import UserRepository
from database.repositories.moderation_repo import ModerationRepository
from database.models.group import Group
from database.models.user import User
from app.config import settings
from utils.logging import get_logger

logger = get_logger(__name__)


class UserRole(IntEnum):
    BANNED = 0
    RESTRICTED = 1
    MEMBER = 10
    STAFF = 50
    ADMIN = 80
    OWNER = 100


class PermissionService:
    def __init__(self, session: AsyncSession, bot: Bot) -> None:
        self.session = session
        self.bot = bot
        self.admin_repo = AdminRepository(session)
        self.group_repo = GroupRepository(session)
        self.user_repo = UserRepository(session)
        self.mod_repo = ModerationRepository(session)

    async def get_user_role_and_rank(
        self,
        chat_id: int,
        user_id: int,
        group_db_id: Optional[int] = None
    ) -> Tuple[UserRole, str]:
        """Determines the effective role and rank of a user in a Telegram chat."""
        # 1. Telegram Anonymous Admin check (Telegram anonymous bot ID)
        if user_id == 1087968824:
            return UserRole.OWNER, "Owner"

        # 2. Query Telegram get_chat_member
        try:
            member = await self.bot.get_chat_member(chat_id=chat_id, user_id=user_id)
            if member.status in [ChatMemberStatus.CREATOR, "creator"]:
                return UserRole.OWNER, "Owner"
            if member.status in [ChatMemberStatus.ADMINISTRATOR, "administrator"]:
                return UserRole.ADMIN, "Administrator"
            if member.status in [ChatMemberStatus.RESTRICTED, "restricted"]:
                return UserRole.RESTRICTED, "Restricted Member"
            if member.status in [ChatMemberStatus.KICKED, "kicked"]:
                return UserRole.BANNED, "Banned Member"
        except Exception as e:
            logger.debug(f"Could not fetch Telegram chat member {user_id} in {chat_id}: {e}")

        # 3. Fallback: Query chat administrators (failsafe if get_chat_member was throttled or restricted)
        try:
            admins = await self.bot.get_chat_administrators(chat_id=chat_id)
            for adm in admins:
                if adm.user.id == user_id:
                    if adm.status in [ChatMemberStatus.CREATOR, "creator"]:
                        return UserRole.OWNER, "Owner"
                    return UserRole.ADMIN, "Administrator"
        except Exception as e:
            logger.debug(f"Could not fetch chat administrators for {chat_id}: {e}")

        # 4. If not Telegram creator/admin, check if configured as bot staff
        if group_db_id:
            user_db = await self.user_repo.get_by_telegram_id(user_id)
            if user_db:
                staff = await self.admin_repo.get_staff(group_db_id, user_db.id)
                if staff:
                    return UserRole.STAFF, "Staff"

        return UserRole.MEMBER, "Member"

    async def can_perform_action(
        self,
        chat_id: int,
        actor_tg_id: int,
        required_permission: str,
        target_tg_id: Optional[int] = None,
        group_db_id: Optional[int] = None
    ) -> Tuple[bool, str]:
        """
        Validates whether actor has authority to perform action:
        1. Check actor role & permissions.
        2. If target is provided, enforce strict hierarchy protection.
        """
        actor_role, actor_role_name = await self.get_user_role_and_rank(chat_id, actor_tg_id, group_db_id)

        # Owner and Administrator have full permissions
        if actor_role >= UserRole.ADMIN:
            actor_permitted = True
        elif actor_role == UserRole.STAFF and group_db_id:
            user_db = await self.user_repo.get_by_telegram_id(actor_tg_id)
            if user_db:
                staff = await self.admin_repo.get_staff(group_db_id, user_db.id)
                actor_permitted = staff.has_permission(required_permission) if staff else False
            else:
                actor_permitted = False
        else:
            actor_permitted = False

        if not actor_permitted:
            return False, f"Permission denied. Required privilege: <code>{required_permission}</code>"

        # Hierarchy check if target user is specified
        if target_tg_id is not None:
            if actor_tg_id == target_tg_id:
                return False, "You cannot perform administrative actions on yourself."

            target_role, target_role_name = await self.get_user_role_and_rank(chat_id, target_tg_id, group_db_id)
            if actor_role <= target_role:
                return False, f"Hierarchy violation: You ({actor_role_name}) cannot moderate {target_role_name}."

        return True, "Authorized"

    async def log_action(
        self,
        group: Group,
        actor_tg_id: Optional[int],
        action: str,
        target_tg_id: Optional[int] = None,
        reason: Optional[str] = None,
        details: Optional[str] = None
    ) -> None:
        """Persists moderation log in DB and forwards to configured log channels."""
        actor_db = await self.user_repo.get_by_telegram_id(actor_tg_id) if actor_tg_id else None
        target_db = await self.user_repo.get_by_telegram_id(target_tg_id) if target_tg_id else None

        full_details = f"Reason: {reason}" if reason else ""
        if details:
            full_details = f"{full_details} | {details}" if full_details else details

        await self.mod_repo.add_log(
            action=action,
            group_id=group.id,
            user_id=target_db.id if target_db else None,
            admin_user_id=actor_db.id if actor_db else None,
            details=full_details
        )

        # Broadcast to Admin Log Channel if configured
        log_text = (
            f"📋 <b>MODERATION LOG</b>\n"
            f"• Action: <b>{action}</b>\n"
            f"• Group: <b>{group.group_name}</b> (<code>{group.telegram_group_id}</code>)\n"
            f"• Actor: <code>{actor_tg_id}</code>\n"
            f"• Target: <code>{target_tg_id or 'N/A'}</code>\n"
            f"• Details: <i>{full_details or 'None'}</i>"
        )

        # 1. Global config log channel
        if settings.ADMIN_LOG_CHAT_ID:
            try:
                await self.bot.send_message(chat_id=settings.ADMIN_LOG_CHAT_ID, text=log_text)
            except Exception as e:
                logger.debug(f"Failed to send log to global ADMIN_LOG_CHAT_ID: {e}")

        # 2. Per-group configured log channel
        group_settings = await self.group_repo.get_settings(group.id)
        if group_settings and group_settings.log_channel_id:
            try:
                await self.bot.send_message(chat_id=group_settings.log_channel_id, text=log_text)
            except Exception as e:
                logger.debug(f"Failed to send log to group log_channel_id {group_settings.log_channel_id}: {e}")
