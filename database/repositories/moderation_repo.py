"""Moderation Repository for warnings and moderation logs."""
from typing import Optional, List
from sqlalchemy import select, delete, func, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession
from database.models.warning import Warning
from database.models.moderation_log import ModerationLog


class ModerationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_warning(
        self,
        group_id: int,
        user_id: int,
        admin_user_id: Optional[int],
        reason: str = "No reason specified"
    ) -> Warning:
        """Adds a warning record."""
        warning = Warning(
            group_id=group_id,
            user_id=user_id,
            admin_user_id=admin_user_id,
            reason=reason
        )
        self.session.add(warning)
        await self.session.flush()
        await self.session.refresh(warning)
        return warning

    async def get_warnings_count(self, group_id: int, user_id: int) -> int:
        """Returns total warnings count for user in group."""
        stmt = select(func.count()).select_from(Warning).where(
            and_(Warning.group_id == group_id, Warning.user_id == user_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def get_warnings(self, group_id: int, user_id: int) -> List[Warning]:
        """Gets all warning records for a user in group."""
        stmt = (
            select(Warning)
            .where(and_(Warning.group_id == group_id, Warning.user_id == user_id))
            .order_by(desc(Warning.created_at))
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def reset_warnings(self, group_id: int, user_id: int) -> int:
        """Deletes all warnings for a user in group and returns count deleted."""
        stmt = (
            delete(Warning)
            .where(and_(Warning.group_id == group_id, Warning.user_id == user_id))
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount

    async def add_log(
        self,
        action: str,
        group_id: Optional[int] = None,
        user_id: Optional[int] = None,
        admin_user_id: Optional[int] = None,
        details: Optional[str] = None
    ) -> ModerationLog:
        """Records an action in moderation logs."""
        log_entry = ModerationLog(
            action=action,
            group_id=group_id,
            user_id=user_id,
            admin_user_id=admin_user_id,
            details=details
        )
        self.session.add(log_entry)
        await self.session.flush()
        return log_entry

    async def get_recent_logs(self, group_id: Optional[int] = None, limit: int = 50) -> List[ModerationLog]:
        """Gets recent moderation logs."""
        stmt = select(ModerationLog)
        if group_id:
            stmt = stmt.where(ModerationLog.group_id == group_id)
        stmt = stmt.order_by(desc(ModerationLog.created_at)).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
