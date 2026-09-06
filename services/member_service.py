"""Member Service for user-level administration and exemptions."""
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession
from database.repositories.user_repo import UserRepository
from database.repositories.group_repo import GroupRepository
from database.repositories.referral_repo import ReferralRepository
from database.repositories.moderation_repo import ModerationRepository
from database.models.user import User
from database.models.group import Group
from database.models.referral_requirement import ReferralRequirement
from services.invite_link_service import InviteLinkService
from utils.security import format_time_remaining


class MemberService:
    def __init__(self, session: AsyncSession, bot: Bot) -> None:
        self.session = session
        self.bot = bot
        self.user_repo = UserRepository(session)
        self.group_repo = GroupRepository(session)
        self.referral_repo = ReferralRepository(session)
        self.mod_repo = ModerationRepository(session)
        self.invite_service = InviteLinkService(session, bot)

    async def get_member_profile(self, user_id: int, group_id: int) -> Optional[Dict[str, Any]]:
        """Retrieves member's status, requirement, warnings, and referrer info."""
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            return None

        req = await self.referral_repo.get_requirement(user.id, group_id)
        link = await self.referral_repo.get_active_invite_link(user.id, group_id)
        if not link:
            group = await self.group_repo.get_by_id(group_id)
            if group:
                try:
                    link = await self.invite_service.get_or_create_referral_link(user, group)
                except Exception as e:
                    logger.debug(f"Could not auto-create invite link: {e}")

        warnings_count = await self.mod_repo.get_warnings_count(group_id, user.id)
        referrer = await self.referral_repo.get_referrer(user.id, group_id)
        direct_referrals = await self.referral_repo.get_direct_referrals(user.id, group_id)

        time_str = "N/A"
        if req:
            time_str, _ = format_time_remaining(req.deadline)

        return {
            "user": user,
            "requirement": req,
            "time_remaining": time_str,
            "invite_link": link.telegram_invite_link if link else "None",
            "warnings_count": warnings_count,
            "referrer": referrer,
            "referrals_count": len(direct_referrals)
        }

    async def exempt_member(self, user: User, group: Group, is_exempt: bool, admin_id: Optional[int]) -> ReferralRequirement:
        """Exempts or un-exempts a member."""
        req = await self.referral_repo.set_exempt(user.id, group.id, is_exempt=is_exempt)
        action_name = "EXEMPT" if is_exempt else "UNEXEMPT"
        await self.mod_repo.add_log(
            action=action_name,
            group_id=group.id,
            user_id=user.id,
            admin_user_id=admin_id,
            details=f"Exemption set to {is_exempt}"
        )
        return req

    async def reset_member_timer(self, user: User, group: Group, hours: int, admin_id: Optional[int]) -> ReferralRequirement:
        """Resets the referral timer for a member."""
        new_deadline = datetime.now(timezone.utc) + timedelta(hours=hours)
        req = await self.referral_repo.reset_timer(user.id, group.id, new_deadline)
        await self.mod_repo.add_log(
            action="RESET_TIMER",
            group_id=group.id,
            user_id=user.id,
            admin_user_id=admin_id,
            details=f"Timer reset to {hours} hours from now"
        )
        return req

    async def manually_complete_requirement(self, user: User, group: Group, admin_id: Optional[int]) -> Optional[ReferralRequirement]:
        """Manually marks a requirement as COMPLETED."""
        req = await self.referral_repo.get_requirement(user.id, group.id)
        if req:
            req.status = "COMPLETED"
            req.completed_referrals = max(req.completed_referrals, req.required_referrals)
            req.action_taken = False
            await self.session.flush()
            await self.mod_repo.add_log(
                action="MANUAL_COMPLETE",
                group_id=group.id,
                user_id=user.id,
                admin_user_id=admin_id,
                details="Manually marked requirement as COMPLETED by administrator"
            )
        return req
