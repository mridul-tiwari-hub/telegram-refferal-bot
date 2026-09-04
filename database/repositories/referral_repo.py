"""Referral Repository for handling links, relationships, and requirements."""
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import select, update, func, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession
from database.models.referral_link import ReferralInviteLink
from database.models.referral_relationship import ReferralRelationship
from database.models.referral_requirement import ReferralRequirement
from database.models.user import User


class ReferralRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_invite_link(
        self,
        user_id: int,
        group_id: int,
        referral_code: str,
        telegram_invite_link: str
    ) -> ReferralInviteLink:
        """Deactivates any previous active link for the user in this group and creates a new one."""
        # Deactivate old links
        await self.session.execute(
            update(ReferralInviteLink)
            .where(
                and_(
                    ReferralInviteLink.user_id == user_id,
                    ReferralInviteLink.group_id == group_id,
                    ReferralInviteLink.is_active == True
                )
            )
            .values(is_active=False)
        )

        link = ReferralInviteLink(
            user_id=user_id,
            group_id=group_id,
            referral_code=referral_code,
            telegram_invite_link=telegram_invite_link,
            is_active=True,
            usage_count=0
        )
        self.session.add(link)
        await self.session.flush()
        await self.session.refresh(link)
        return link

    async def get_active_invite_link(self, user_id: int, group_id: int) -> Optional[ReferralInviteLink]:
        """Gets active invite link for user in group."""
        stmt = (
            select(ReferralInviteLink)
            .where(
                and_(
                    ReferralInviteLink.user_id == user_id,
                    ReferralInviteLink.group_id == group_id,
                    ReferralInviteLink.is_active == True
                )
            )
            .order_by(desc(ReferralInviteLink.id))
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_link_str(self, invite_link_str: str) -> Optional[ReferralInviteLink]:
        """Finds invite link record by the Telegram invite URL string."""
        stmt = select(ReferralInviteLink).where(
            ReferralInviteLink.telegram_invite_link == invite_link_str
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_referral_code(self, code: str) -> Optional[ReferralInviteLink]:
        """Finds invite link record by code."""
        stmt = select(ReferralInviteLink).where(
            ReferralInviteLink.referral_code == code
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def record_referral(
        self,
        group_id: int,
        referrer_user_id: int,
        referred_user_id: int,
        invite_link_id: int
    ) -> Tuple[Optional[ReferralRelationship], bool]:
        """
        Records referral relationship.
        Returns: (relationship, is_new)
        Uses constraint to prevent duplicate attribution for the same user in the group.
        """
        # Check if already referred in this group
        stmt = select(ReferralRelationship).where(
            and_(
                ReferralRelationship.group_id == group_id,
                ReferralRelationship.referred_user_id == referred_user_id
            )
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            return existing, False

        rel = ReferralRelationship(
            group_id=group_id,
            referrer_user_id=referrer_user_id,
            referred_user_id=referred_user_id,
            invite_link_id=invite_link_id
        )
        self.session.add(rel)

        # Increment link usage count
        await self.session.execute(
            update(ReferralInviteLink)
            .where(ReferralInviteLink.id == invite_link_id)
            .values(usage_count=ReferralInviteLink.usage_count + 1)
        )
        await self.session.flush()
        await self.session.refresh(rel)
        return rel, True

    async def create_requirement(
        self,
        user_id: int,
        group_id: int,
        deadline: datetime,
        required_referrals: int = 1
    ) -> ReferralRequirement:
        """Creates or resets a referral requirement for a user."""
        stmt = select(ReferralRequirement).where(
            and_(
                ReferralRequirement.user_id == user_id,
                ReferralRequirement.group_id == group_id
            )
        )
        result = await self.session.execute(stmt)
        req = result.scalar_one_or_none()

        if req is None:
            req = ReferralRequirement(
                user_id=user_id,
                group_id=group_id,
                deadline=deadline,
                required_referrals=required_referrals,
                completed_referrals=0,
                status="PENDING",
                is_exempt=False,
                action_taken=False
            )
            self.session.add(req)
        else:
            req.deadline = deadline
            req.required_referrals = required_referrals
            req.completed_referrals = 0
            req.status = "PENDING"
            req.is_exempt = False
            req.action_taken = False

        await self.session.flush()
        await self.session.refresh(req)
        return req

    async def get_requirement(self, user_id: int, group_id: int) -> Optional[ReferralRequirement]:
        """Gets user requirement in a group."""
        stmt = select(ReferralRequirement).where(
            and_(
                ReferralRequirement.user_id == user_id,
                ReferralRequirement.group_id == group_id
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def increment_completed_referral(
        self,
        user_id: int,
        group_id: int
    ) -> Optional[ReferralRequirement]:
        """Increments completed referrals and updates status to COMPLETED if requirement met."""
        req = await self.get_requirement(user_id, group_id)
        if not req:
            return None

        req.completed_referrals += 1
        if req.status == "PENDING" and req.completed_referrals >= req.required_referrals:
            req.status = "COMPLETED"

        await self.session.flush()
        await self.session.refresh(req)
        return req

    async def get_expired_pending_requirements(
        self,
        batch_size: int = 100
    ) -> List[ReferralRequirement]:
        """Gets pending requirements that have exceeded their deadline and no action was taken."""
        now = datetime.now(timezone.utc)
        stmt = (
            select(ReferralRequirement)
            .where(
                and_(
                    ReferralRequirement.status == "PENDING",
                    ReferralRequirement.is_exempt == False,
                    ReferralRequirement.action_taken == False,
                    ReferralRequirement.deadline <= now
                )
            )
            .limit(batch_size)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def mark_requirement_action_taken(
        self,
        requirement_id: int,
        final_status: str = "FAILED"
    ) -> None:
        """Atomically marks requirement action taken to ensure idempotence."""
        stmt = (
            update(ReferralRequirement)
            .where(ReferralRequirement.id == requirement_id)
            .values(
                status=final_status,
                action_taken=True,
                updated_at=datetime.now(timezone.utc)
            )
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def set_exempt(self, user_id: int, group_id: int, is_exempt: bool = True) -> Optional[ReferralRequirement]:
        """Marks user as exempt from referral requirements."""
        req = await self.get_requirement(user_id, group_id)
        if req:
            req.is_exempt = is_exempt
            if is_exempt:
                req.status = "EXEMPT"
            elif req.status == "EXEMPT":
                req.status = "PENDING" if req.completed_referrals < req.required_referrals else "COMPLETED"
            await self.session.flush()
            await self.session.refresh(req)
        return req

    async def reset_timer(
        self,
        user_id: int,
        group_id: int,
        new_deadline: datetime
    ) -> Optional[ReferralRequirement]:
        """Resets the referral deadline timer for a user."""
        req = await self.get_requirement(user_id, group_id)
        if req:
            req.deadline = new_deadline
            req.action_taken = False
            if req.status == "FAILED":
                req.status = "PENDING"
            await self.session.flush()
            await self.session.refresh(req)
        return req

    async def get_top_referrers(self, group_id: int, limit: int = 10) -> List[Tuple[User, int]]:
        """Returns top referrers ordered by count of successful referrals."""
        stmt = (
            select(User, func.count(ReferralRelationship.id).label("ref_count"))
            .join(ReferralRelationship, ReferralRelationship.referrer_user_id == User.id)
            .where(ReferralRelationship.group_id == group_id)
            .group_by(User.id)
            .order_by(desc("ref_count"))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]

    async def get_referral_stats(self, group_id: int) -> Dict[str, Any]:
        """Computes comprehensive group statistics."""
        # Pending count
        stmt_pending = select(func.count()).select_from(ReferralRequirement).where(
            and_(ReferralRequirement.group_id == group_id, ReferralRequirement.status == "PENDING")
        )
        pending_count = (await self.session.execute(stmt_pending)).scalar() or 0

        # Completed count
        stmt_completed = select(func.count()).select_from(ReferralRequirement).where(
            and_(ReferralRequirement.group_id == group_id, ReferralRequirement.status == "COMPLETED")
        )
        completed_count = (await self.session.execute(stmt_completed)).scalar() or 0

        # Failed count
        stmt_failed = select(func.count()).select_from(ReferralRequirement).where(
            and_(ReferralRequirement.group_id == group_id, ReferralRequirement.status == "FAILED")
        )
        failed_count = (await self.session.execute(stmt_failed)).scalar() or 0

        # Exempt count
        stmt_exempt = select(func.count()).select_from(ReferralRequirement).where(
            and_(ReferralRequirement.group_id == group_id, ReferralRequirement.status == "EXEMPT")
        )
        exempt_count = (await self.session.execute(stmt_exempt)).scalar() or 0

        # Total successful referrals
        stmt_refs = select(func.count()).select_from(ReferralRelationship).where(
            ReferralRelationship.group_id == group_id
        )
        total_referrals = (await self.session.execute(stmt_refs)).scalar() or 0

        return {
            "pending": pending_count,
            "completed": completed_count,
            "failed": failed_count,
            "exempt": exempt_count,
            "total_referrals": total_referrals
        }

    async def get_direct_referrals(self, user_id: int, group_id: int) -> List[User]:
        """Gets members directly referred by user."""
        stmt = (
            select(User)
            .join(ReferralRelationship, ReferralRelationship.referred_user_id == User.id)
            .where(
                and_(
                    ReferralRelationship.group_id == group_id,
                    ReferralRelationship.referrer_user_id == user_id
                )
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_referrer(self, user_id: int, group_id: int) -> Optional[User]:
        """Finds who referred this user."""
        stmt = (
            select(User)
            .join(ReferralRelationship, ReferralRelationship.referrer_user_id == User.id)
            .where(
                and_(
                    ReferralRelationship.group_id == group_id,
                    ReferralRelationship.referred_user_id == user_id
                )
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_referral_tree_nodes(self, group_id: int) -> List[Tuple[int, int]]:
        """Returns all (referrer_user_id, referred_user_id) pairs in group for building trees."""
        stmt = select(
            ReferralRelationship.referrer_user_id,
            ReferralRelationship.referred_user_id
        ).where(ReferralRelationship.group_id == group_id)
        result = await self.session.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]
