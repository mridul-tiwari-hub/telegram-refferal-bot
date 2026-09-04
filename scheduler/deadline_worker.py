"""Background scheduler for periodic referral deadline enforcement."""
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
from database.session import async_session_maker
from services.deadline_service import DeadlineService
from app.config import settings
from utils.logging import get_logger

logger = get_logger(__name__)


class DeadlineWorker:
    def __init__(self, bot: Bot) -> None:
        self.bot = bot
        self.scheduler = AsyncIOScheduler()
        self._is_running = False

    async def _run_deadline_check_job(self) -> None:
        """Periodic job executing deadline check inside database session."""
        try:
            async with async_session_maker() as session:
                deadline_service = DeadlineService(session=session, bot=self.bot)
                processed = await deadline_service.check_and_process_expired_deadlines()
                await session.commit()
                if processed > 0:
                    logger.info(f"Processed {processed} expired referral requirements")
        except Exception as e:
            logger.error(f"Error during deadline check job: {e}", exc_info=True)

    def start(self) -> None:
        """Starts the scheduler."""
        if not self._is_running:
            self.scheduler.add_job(
                self._run_deadline_check_job,
                "interval",
                seconds=settings.DEADLINE_CHECK_INTERVAL_SECONDS,
                id="referral_deadline_check",
                replace_existing=True
            )
            self.scheduler.start()
            self._is_running = True
            logger.info(
                f"Deadline worker scheduler started (checking every {settings.DEADLINE_CHECK_INTERVAL_SECONDS}s)"
            )

    def shutdown(self) -> None:
        """Stops the scheduler gracefully."""
        if self._is_running:
            self.scheduler.shutdown(wait=False)
            self._is_running = False
            logger.info("Deadline worker scheduler stopped")
