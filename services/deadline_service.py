"""Deadline Service for enforcing referral deadlines and failure actions."""
from typing import List
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession
from database.repositories.referral_repo import ReferralRepository
from database.repositories.group_repo import GroupRepository
from database.repositories.user_repo import UserRepository
from database.repositories.moderation_repo import ModerationRepository
from database.models.referral_requirement import ReferralRequirement
from services.moderation_service import ModerationService
from utils.logging import get_logger

logger = get_logger(__name__)


class DeadlineService:
    def __init__(self, session: AsyncSession, bot: Bot) -> None:
        self.session = session
        self.bot = bot
        self.referral_repo = ReferralRepository(session)
        self.group_repo = GroupRepository(session)
        self.user_repo = UserRepository(session)
        self.mod_repo = ModerationRepository(session)
        self.mod_service = ModerationService(session, bot)

    async def check_and_process_expired_deadlines(self, batch_size: int = 100) -> int:
        """
        Scans for expired pending referral requirements and applies failure actions idempotently.
        Returns the number of requirements processed.
        """
        expired_reqs: List[ReferralRequirement] = await self.referral_repo.get_expired_pending_requirements(batch_size=batch_size)
        if not expired_reqs:
            return 0

        logger.info(f"Found {len(expired_reqs)} expired referral requirements to process")
        processed_count = 0

        for req in expired_reqs:
            # Re-check status & exemption
            if req.is_exempt:
                await self.referral_repo.mark_requirement_action_taken(req.id, final_status="EXEMPT")
                continue

            if req.completed_referrals >= req.required_referrals:
                await self.referral_repo.mark_requirement_action_taken(req.id, final_status="COMPLETED")
                continue

            # Requirement has failed: get group settings to determine failure action
            group_settings = await self.group_repo.get_settings(req.group_id)
            failure_action = (group_settings.failure_action or "RESTRICT").upper()

            user = await self.user_repo.get_by_id(req.user_id)
            group = await self.group_repo.session.get(group_settings.group.__class__, req.group_id) if hasattr(group_settings, 'group') else None
            if not group:
                from database.models.group import Group
                group = await self.session.get(Group, req.group_id)

            if not user or not group:
                logger.warning(f"User {req.user_id} or Group {req.group_id} not found for req {req.id}")
                await self.referral_repo.mark_requirement_action_taken(req.id, final_status="FAILED")
                continue

            # Execute failure action
            logger.info(f"Enforcing failure action '{failure_action}' on user {user.telegram_user_id} in group {group.telegram_group_id}")

            if failure_action == "KICK":
                await self.mod_service.kick_member(
                    group=group,
                    user=user,
                    reason="Failed to meet referral requirement within deadline"
                )
            elif failure_action == "RESTRICT":
                await self.mod_service.restrict_member(
                    group=group,
                    user=user,
                    reason="Failed to meet referral requirement within deadline"
                )
            elif failure_action == "NONE":
                logger.info(f"No moderation action configured for failed requirement {req.id}")

            # Idempotently mark action taken in database
            await self.referral_repo.mark_requirement_action_taken(req.id, final_status="FAILED")

            await self.mod_repo.add_log(
                action="DEADLINE_EXPIRED",
                group_id=group.id,
                user_id=user.id,
                details=f"Status: FAILED. Action executed: {failure_action}. Completed: {req.completed_referrals}/{req.required_referrals}"
            )

            # Attempt notification to user DM if possible
            try:
                action_desc = "removed from" if failure_action == "KICK" else "restricted in" if failure_action == "RESTRICT" else "noted in"
                await self.bot.send_message(
                    chat_id=user.telegram_user_id,
                    text=(
                        f"⚠️ <b>Referral Deadline Expired</b>\n"
                        f"You did not complete your referral requirement in <b>{group.group_name}</b> in time.\n"
                        f"You were {action_desc} the group."
                    ),
                    parse_mode="HTML"
                )
            except Exception:
                pass

            processed_count += 1

        return processed_count
