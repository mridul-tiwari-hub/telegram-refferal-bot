"""User Repository for database operations."""
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from database.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_or_create_user(
        self,
        telegram_user_id: int,
        username: Optional[str] = None,
        first_name: str = "",
        last_name: Optional[str] = None,
        is_admin: bool = False
    ) -> User:
        """Retrieves existing user or creates a new record."""
        stmt = select(User).where(User.telegram_user_id == telegram_user_id)
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                telegram_user_id=telegram_user_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                is_admin=is_admin,
                is_active=True
            )
            self.session.add(user)
            await self.session.flush()
            await self.session.refresh(user)
        else:
            # Update latest user details if changed
            updated = False
            if username and user.username != username:
                user.username = username
                updated = True
            if first_name and user.first_name != first_name:
                user.first_name = first_name
                updated = True
            if last_name and user.last_name != last_name:
                user.last_name = last_name
                updated = True
            if is_admin and not user.is_admin:
                user.is_admin = is_admin
                updated = True
            if not user.is_active:
                user.is_active = True
                user.left_at = None
                updated = True

            if updated:
                await self.session.flush()
        return user

    async def get_by_telegram_id(self, telegram_user_id: int) -> Optional[User]:
        """Finds user by Telegram ID."""
        stmt = select(User).where(User.telegram_user_id == telegram_user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> Optional[User]:
        """Finds user by Telegram username (case-insensitive)."""
        if not username:
            return None
        clean_username = username.lstrip("@").lower()
        from sqlalchemy import func
        stmt = select(User).where(func.lower(User.username) == clean_username)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_id(self, user_id: int) -> Optional[User]:
        """Finds user by primary key ID."""
        stmt = select(User).where(User.id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def mark_left(self, telegram_user_id: int) -> None:
        """Marks user as left."""
        stmt = (
            update(User)
            .where(User.telegram_user_id == telegram_user_id)
            .values(is_active=False, left_at=datetime.now(timezone.utc))
        )
        await self.session.execute(stmt)
        await self.session.flush()
