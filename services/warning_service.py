"""Warning Service for issuing and checking warning limits."""
from typing import Optional, Tuple, List
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession
from database.repositories.moderation_repo import ModerationRepository
from database.repositories.group_repo import GroupRepository
from database.models.user import User
from database.models.group import Group
from database.models.warning import Warning
from services.moderation_service import ModerationService
from utils.logging import get_logger

logger = get_logger(__name__)


class WarningService:
    def __init__(self, session: AsyncSession, bot: Bot) -> None:
        self.session = session
        self.bot = bot
        self.mod_repo = ModerationRepository(session)
        self.group_repo = GroupRepository(session)
        self.mod_service = ModerationService(session, bot)

    async def issue_warning(
        self,
        group: Group,
        user: User,
        admin_user_id: Optional[int],
        reason: str = "Rule violation"
    ) -> Tuple[Warning, int, int, bool]:
        """
        Issues a warning to a user.
        Returns: (warning_obj, current_warnings_count, warning_limit, action_triggered)
        """
        warning = await self.mod_repo.add_warning(
            group_id=group.id,
            user_id=user.id,
            admin_user_id=admin_user_id,
            reason=reason
        )

        current_count = await self.mod_repo.get_warnings_count(group.id, user.id)
        settings = await self.group_repo.get_settings(group.id)
        limit = settings.warning_limit or 3

        action_triggered = False
        if current_count >= limit:
            action_triggered = True
            action = (settings.failure_action or "RESTRICT").upper()
            if action == "KICK":
                await self.mod_service.kick_member(
                    group=group,
                    user=user,
                    admin_user_id=admin_user_id,
                    reason=f"Exceeded warning limit ({current_count}/{limit})"
                )
            else:
                await self.mod_service.restrict_member(
                    group=group,
                    user=user,
                    admin_user_id=admin_user_id,
                    reason=f"Exceeded warning limit ({current_count}/{limit})"
                )

        await self.mod_repo.add_log(
            action="WARN",
            group_id=group.id,
            user_id=user.id,
            admin_user_id=admin_user_id,
            details=f"Warning {current_count}/{limit}: {reason}. Action triggered: {action_triggered}"
        )

        return warning, current_count, limit, action_triggered

    async def get_user_warnings(self, group_id: int, user_id: int) -> List[Warning]:
        """Gets all warnings for user in group."""
        return await self.mod_repo.get_warnings(group_id, user_id)

    async def reset_user_warnings(self, group_id: int, user_id: int, admin_user_id: Optional[int]) -> int:
        """Resets warnings for user in group."""
        count = await self.mod_repo.reset_warnings(group_id, user_id)
        await self.mod_repo.add_log(
            action="RESET_WARNINGS",
            group_id=group_id,
            user_id=user_id,
            admin_user_id=admin_user_id,
            details=f"Cleared {count} warnings"
        )
        return count
