"""Anti-Raid Protection Service."""
import time
from collections import defaultdict
from typing import Dict, List, Tuple
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession
from database.models.group import Group
from database.repositories.group_repo import GroupRepository
from services.permission_service import PermissionService
from utils.logging import get_logger

logger = get_logger(__name__)


class RaidService:
    def __init__(self, session: AsyncSession, bot: Bot) -> None:
        self.session = session
        self.bot = bot
        self.group_repo = GroupRepository(session)
        self.perm_service = PermissionService(session, bot)

    # In-memory join timestamps per chat_id: list of timestamps
    _join_history: Dict[int, List[float]] = defaultdict(list)

    async def record_join_and_check_raid(
        self,
        group: Group,
        threshold: int = 10,
        window_seconds: int = 60
    ) -> Tuple[bool, int]:
        """
        Records a new member join. If joins within window exceed threshold,
        activates raid mode and notifies admins.
        """
        now = time.time()
        chat_id = group.telegram_group_id
        joins = self._join_history[chat_id]

        # Filter to recent window
        joins = [t for t in joins if now - t <= window_seconds]
        joins.append(now)
        self._join_history[chat_id] = joins

        if len(joins) >= threshold:
            settings = await self.group_repo.get_settings(group.id)
            if not settings.raid_mode:
                await self.group_repo.update_settings(group.id, raid_mode=True)
                logger.warning(f"Raid mode auto-triggered in group {group.telegram_group_id} ({len(joins)} joins in {window_seconds}s)")

                # Notify admins / group
                try:
                    alert_text = (
                        f"🚨 <b>ANTI-RAID ALERT!</b>\n\n"
                        f"Abnormal join spike detected: <b>{len(joins)} members joined in {window_seconds} seconds</b>.\n"
                        f"🛡 <b>Raid Mode has been automatically ACTIVATED!</b> New members will be restricted.\n"
                        f"Admins can disable with <code>/raidmode off</code>."
                    )
                    await self.bot.send_message(chat_id=group.telegram_group_id, text=alert_text)
                    await self.perm_service.log_action(
                        group=group,
                        actor_tg_id=None,
                        action="RAID_MODE_TRIGGERED",
                        details=f"{len(joins)} joins in {window_seconds}s"
                    )
                except Exception as e:
                    logger.debug(f"Failed to post raid alert: {e}")

            return True, len(joins)

        return False, len(joins)
