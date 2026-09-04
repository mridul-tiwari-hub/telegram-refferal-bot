"""Group Repository for database operations."""
from typing import Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from database.models.group import Group
from database.models.group_settings import GroupSettings
from app.config import settings


class GroupRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_or_create_group(
        self,
        telegram_group_id: int,
        group_name: str = ""
    ) -> Group:
        """Retrieves group or creates it along with default settings."""
        stmt = select(Group).where(Group.telegram_group_id == telegram_group_id)
        result = await self.session.execute(stmt)
        group = result.scalar_one_or_none()

        if group is None:
            group = Group(
                telegram_group_id=telegram_group_id,
                group_name=group_name,
                is_active=True
            )
            self.session.add(group)
            await self.session.flush()
            await self.session.refresh(group)

            # Create default group settings
            group_settings = GroupSettings(
                group_id=group.id,
                referral_enabled=True,
                referral_deadline_hours=settings.DEFAULT_REFERRAL_DEADLINE_HOURS,
                required_referrals=settings.DEFAULT_REQUIRED_REFERRALS,
                failure_action=settings.DEFAULT_FAILURE_ACTION,
                warning_limit=settings.DEFAULT_WARNING_LIMIT,
                anti_spam_enabled=True
            )
            self.session.add(group_settings)
            await self.session.flush()
        else:
            if group_name and group.group_name != group_name:
                group.group_name = group_name
                await self.session.flush()

        return group

    async def get_by_telegram_id(self, telegram_group_id: int) -> Optional[Group]:
        """Finds group by Telegram ID."""
        stmt = select(Group).where(Group.telegram_group_id == telegram_group_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_settings(self, group_id: int) -> GroupSettings:
        """Gets settings for a specific group ID."""
        stmt = select(GroupSettings).where(GroupSettings.group_id == group_id)
        result = await self.session.execute(stmt)
        group_settings = result.scalar_one_or_none()

        if group_settings is None:
            group_settings = GroupSettings(
                group_id=group_id,
                referral_enabled=True,
                referral_deadline_hours=settings.DEFAULT_REFERRAL_DEADLINE_HOURS,
                required_referrals=settings.DEFAULT_REQUIRED_REFERRALS,
                failure_action=settings.DEFAULT_FAILURE_ACTION,
                warning_limit=settings.DEFAULT_WARNING_LIMIT,
                anti_spam_enabled=True
            )
            self.session.add(group_settings)
            await self.session.flush()
            await self.session.refresh(group_settings)

        return group_settings

    async def update_settings(self, group_id: int, **kwargs) -> GroupSettings:
        """Updates group settings."""
        stmt = (
            update(GroupSettings)
            .where(GroupSettings.group_id == group_id)
            .values(**kwargs)
        )
        await self.session.execute(stmt)
        await self.session.flush()
        return await self.get_settings(group_id)

    async def set_rules(self, group_id: int, rules_text: str) -> None:
        """Sets group rules."""
        stmt = (
            update(Group)
            .where(Group.id == group_id)
            .values(rules=rules_text)
        )
        await self.session.execute(stmt)
        await self.session.flush()
