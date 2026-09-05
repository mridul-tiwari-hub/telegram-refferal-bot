"""Member Activity & Statistics Service."""
from datetime import datetime, timezone, timedelta
from typing import List, Tuple
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession
from database.models.group import Group
from database.models.user import User
from database.repositories.admin_repo import AdminRepository
from database.repositories.user_repo import UserRepository
from utils.logging import get_logger

logger = get_logger(__name__)


class ActivityService:
    def __init__(self, session: AsyncSession, bot: Bot) -> None:
        self.session = session
        self.bot = bot
        self.admin_repo = AdminRepository(session)
        self.user_repo = UserRepository(session)

    async def record_activity(self, group_id: int, user_id: int) -> None:
        """Increments member message counter and updates last active timestamp."""
        try:
            await self.admin_repo.record_activity(group_id, user_id)
        except Exception as e:
            logger.debug(f"Failed to record member activity: {e}")

    async def get_top_chatters_text(self, group_id: int, limit: int = 10) -> str:
        """Returns leaderboard of most active group chatters."""
        top_list = await self.admin_repo.get_top_chatters(group_id, limit)
        if not top_list:
            return "📊 <i>No message activity recorded yet.</i>"

        lines = ["🏆 <b>TOP CHATTERS LEADERBOARD</b>\n"]
        for idx, act in enumerate(top_list, 1):
            user = await self.session.get(User, act.user_id)
            if user:
                name = user.first_name
                if user.username:
                    name += f" (@{user.username})"
            else:
                name = f"User {act.user_id}"

            medal = "🥇" if idx == 1 else ("🥈" if idx == 2 else ("🥉" if idx == 3 else f"{idx}."))
            lines.append(f"{medal} <b>{name}</b> — <code>{act.message_count}</code> messages")

        return "\n".join(lines)

    async def get_inactive_members_text(self, group_id: int, days: int = 30) -> str:
        """Returns list of members inactive for greater than specified days."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        inactive = await self.admin_repo.get_inactive_members(group_id, cutoff)
        if not inactive:
            return f"💤 <i>No members found inactive for more than {days} days.</i>"

        lines = [f"💤 <b>INACTIVE MEMBERS (> {days} days) — Total: {len(inactive)}</b>\n"]
        for idx, act in enumerate(inactive[:20], 1):
            user = await self.session.get(User, act.user_id)
            name = user.first_name if user else f"User {act.user_id}"
            last_date = act.last_active_at.strftime("%Y-%m-%d")
            lines.append(f"{idx}. <b>{name}</b> (Last active: {last_date}, {act.message_count} msgs)")

        if len(inactive) > 20:
            lines.append(f"\n... and {len(inactive) - 20} more inactive members.")

        return "\n".join(lines)
