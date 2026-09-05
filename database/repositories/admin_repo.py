"""Admin & Moderation Repository for locks, staff, filters, actions, queue, and activity."""
from datetime import datetime, timezone
from typing import Optional, List, Sequence
from sqlalchemy import select, update, delete, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession
from database.models.group_lock import GroupLock
from database.models.group_staff import GroupStaff
from database.models.banned_word import BannedWord
from database.models.blocked_domain import BlockedDomain
from database.models.temporary_action import TemporaryAction
from database.models.auto_delete import AutoDeleteQueue
from database.models.member_activity import MemberActivity
from database.models.captcha_pending import CaptchaPending


class AdminRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ==================== GROUP LOCKS ====================
    async def get_or_create_locks(self, group_id: int) -> GroupLock:
        stmt = select(GroupLock).where(GroupLock.group_id == group_id)
        result = await self.session.execute(stmt)
        locks = result.scalar_one_or_none()
        if not locks:
            locks = GroupLock(group_id=group_id)
            self.session.add(locks)
            await self.session.flush()
            await self.session.refresh(locks)
        return locks

    async def update_locks(self, group_id: int, **kwargs) -> GroupLock:
        locks = await self.get_or_create_locks(group_id)
        for key, value in kwargs.items():
            if hasattr(locks, key):
                setattr(locks, key, value)
        await self.session.flush()
        return locks

    # ==================== STAFF MANAGEMENT ====================
    async def get_staff(self, group_id: int, user_id: int) -> Optional[GroupStaff]:
        stmt = select(GroupStaff).where(
            and_(GroupStaff.group_id == group_id, GroupStaff.user_id == user_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def add_staff(
        self,
        group_id: int,
        user_id: int,
        permissions: str = "ban,mute,warn,delete,filters,locks,welcome,rules,stats,referrals,settings",
        created_by: Optional[int] = None
    ) -> GroupStaff:
        staff = await self.get_staff(group_id, user_id)
        if not staff:
            staff = GroupStaff(
                group_id=group_id,
                user_id=user_id,
                permissions=permissions,
                created_by=created_by
            )
            self.session.add(staff)
        else:
            staff.permissions = permissions
        await self.session.flush()
        await self.session.refresh(staff)
        return staff

    async def remove_staff(self, group_id: int, user_id: int) -> bool:
        stmt = delete(GroupStaff).where(
            and_(GroupStaff.group_id == group_id, GroupStaff.user_id == user_id)
        )
        res = await self.session.execute(stmt)
        await self.session.flush()
        return res.rowcount > 0

    async def list_staff(self, group_id: int) -> List[GroupStaff]:
        stmt = select(GroupStaff).where(GroupStaff.group_id == group_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # ==================== BANNED WORDS ====================
    async def add_banned_word(self, group_id: int, word: str, is_substring: bool = False) -> BannedWord:
        word_clean = word.strip().lower()
        stmt = select(BannedWord).where(
            and_(BannedWord.group_id == group_id, BannedWord.word == word_clean)
        )
        res = await self.session.execute(stmt)
        bw = res.scalar_one_or_none()
        if not bw:
            bw = BannedWord(group_id=group_id, word=word_clean, is_substring=is_substring)
            self.session.add(bw)
            await self.session.flush()
            await self.session.refresh(bw)
        return bw

    async def remove_banned_word(self, group_id: int, word: str) -> bool:
        word_clean = word.strip().lower()
        stmt = delete(BannedWord).where(
            and_(BannedWord.group_id == group_id, BannedWord.word == word_clean)
        )
        res = await self.session.execute(stmt)
        await self.session.flush()
        return res.rowcount > 0

    async def list_banned_words(self, group_id: int) -> List[BannedWord]:
        stmt = select(BannedWord).where(BannedWord.group_id == group_id)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def clear_banned_words(self, group_id: int) -> int:
        stmt = delete(BannedWord).where(BannedWord.group_id == group_id)
        res = await self.session.execute(stmt)
        await self.session.flush()
        return res.rowcount

    # ==================== DOMAINS (WHITELIST/BLACKLIST) ====================
    async def add_domain(self, group_id: int, domain: str, is_allowed: bool = False) -> BlockedDomain:
        dom_clean = domain.strip().lower()
        stmt = select(BlockedDomain).where(
            and_(BlockedDomain.group_id == group_id, BlockedDomain.domain == dom_clean)
        )
        res = await self.session.execute(stmt)
        bd = res.scalar_one_or_none()
        if not bd:
            bd = BlockedDomain(group_id=group_id, domain=dom_clean, is_allowed=is_allowed)
            self.session.add(bd)
        else:
            bd.is_allowed = is_allowed
        await self.session.flush()
        await self.session.refresh(bd)
        return bd

    async def remove_domain(self, group_id: int, domain: str) -> bool:
        dom_clean = domain.strip().lower()
        stmt = delete(BlockedDomain).where(
            and_(BlockedDomain.group_id == group_id, BlockedDomain.domain == dom_clean)
        )
        res = await self.session.execute(stmt)
        await self.session.flush()
        return res.rowcount > 0

    async def list_domains(self, group_id: int) -> List[BlockedDomain]:
        stmt = select(BlockedDomain).where(BlockedDomain.group_id == group_id)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # ==================== TEMPORARY ACTIONS ====================
    async def add_temporary_action(
        self,
        group_id: int,
        user_id: int,
        action_type: str,
        expires_at: datetime,
        reason: Optional[str] = None
    ) -> TemporaryAction:
        action = TemporaryAction(
            group_id=group_id,
            user_id=user_id,
            action_type=action_type.upper(),
            expires_at=expires_at,
            reason=reason,
            is_active=True
        )
        self.session.add(action)
        await self.session.flush()
        await self.session.refresh(action)
        return action

    async def get_due_temporary_actions(self, now: datetime) -> List[TemporaryAction]:
        stmt = (
            select(TemporaryAction)
            .where(and_(TemporaryAction.is_active.is_(True), TemporaryAction.expires_at <= now))
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def deactivate_temporary_action(self, action_id: int) -> None:
        stmt = (
            update(TemporaryAction)
            .where(TemporaryAction.id == action_id)
            .values(is_active=False)
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def get_active_actions_for_user(self, group_id: int, user_id: int) -> List[TemporaryAction]:
        stmt = select(TemporaryAction).where(
            and_(
                TemporaryAction.group_id == group_id,
                TemporaryAction.user_id == user_id,
                TemporaryAction.is_active.is_(True)
            )
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # ==================== AUTO DELETE QUEUE ====================
    async def enqueue_auto_delete(self, group_id: int, message_id: int, delete_at: datetime) -> AutoDeleteQueue:
        entry = AutoDeleteQueue(group_id=group_id, message_id=message_id, delete_at=delete_at)
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def get_due_auto_delete(self, now: datetime, limit: int = 100) -> List[AutoDeleteQueue]:
        stmt = (
            select(AutoDeleteQueue)
            .where(AutoDeleteQueue.delete_at <= now)
            .order_by(AutoDeleteQueue.delete_at)
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def remove_auto_delete_items(self, ids: Sequence[int]) -> None:
        if not ids:
            return
        stmt = delete(AutoDeleteQueue).where(AutoDeleteQueue.id.in_(ids))
        await self.session.execute(stmt)
        await self.session.flush()

    # ==================== MEMBER ACTIVITY ====================
    async def record_activity(self, group_id: int, user_id: int) -> None:
        stmt = select(MemberActivity).where(
            and_(MemberActivity.group_id == group_id, MemberActivity.user_id == user_id)
        )
        res = await self.session.execute(stmt)
        act = res.scalar_one_or_none()
        now = datetime.now(timezone.utc)
        if not act:
            act = MemberActivity(
                group_id=group_id,
                user_id=user_id,
                message_count=1,
                last_active_at=now
            )
            self.session.add(act)
        else:
            act.message_count += 1
            act.last_active_at = now
        await self.session.flush()

    async def get_top_chatters(self, group_id: int, limit: int = 10) -> List[MemberActivity]:
        stmt = (
            select(MemberActivity)
            .where(MemberActivity.group_id == group_id)
            .order_by(desc(MemberActivity.message_count))
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def get_inactive_members(self, group_id: int, cutoff_date: datetime) -> List[MemberActivity]:
        stmt = (
            select(MemberActivity)
            .where(
                and_(
                    MemberActivity.group_id == group_id,
                    MemberActivity.last_active_at < cutoff_date
                )
            )
            .order_by(MemberActivity.last_active_at)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # ==================== CAPTCHA PENDING ====================
    async def create_captcha(
        self,
        group_id: int,
        user_id: int,
        message_id: int,
        answer: str,
        expires_at: datetime
    ) -> CaptchaPending:
        captcha = CaptchaPending(
            group_id=group_id,
            user_id=user_id,
            message_id=message_id,
            answer=answer,
            expires_at=expires_at,
            is_verified=False
        )
        self.session.add(captcha)
        await self.session.flush()
        await self.session.refresh(captcha)
        return captcha

    async def get_pending_captcha(self, group_id: int, user_id: int) -> Optional[CaptchaPending]:
        stmt = select(CaptchaPending).where(
            and_(
                CaptchaPending.group_id == group_id,
                CaptchaPending.user_id == user_id,
                CaptchaPending.is_verified.is_(False)
            )
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def verify_captcha(self, captcha_id: int) -> None:
        stmt = (
            update(CaptchaPending)
            .where(CaptchaPending.id == captcha_id)
            .values(is_verified=True)
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def get_expired_captchas(self, now: datetime) -> List[CaptchaPending]:
        stmt = select(CaptchaPending).where(
            and_(
                CaptchaPending.is_verified.is_(False),
                CaptchaPending.expires_at <= now
            )
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())
