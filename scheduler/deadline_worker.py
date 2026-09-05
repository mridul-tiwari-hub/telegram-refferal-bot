"""Background scheduler for referral deadlines, temporary actions, captchas, and auto-delete."""
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
from database.session import async_session_maker
from database.models.group import Group
from database.repositories.admin_repo import AdminRepository
from services.deadline_service import DeadlineService
from services.advanced_moderation_service import AdvancedModerationService
from services.captcha_service import CaptchaService
from app.config import settings
from utils.logging import get_logger

logger = get_logger(__name__)


class DeadlineWorker:
    def __init__(self, bot: Bot) -> None:
        self.bot = bot
        self.scheduler = AsyncIOScheduler()
        self._is_running = False

    async def _run_deadline_check_job(self) -> None:
        """Periodic job checking expired referral requirements."""
        try:
            async with async_session_maker() as session:
                deadline_service = DeadlineService(session=session, bot=self.bot)
                processed = await deadline_service.check_and_process_expired_deadlines()
                await session.commit()
                if processed > 0:
                    logger.info(f"Processed {processed} expired referral requirements")
        except Exception as e:
            logger.error(f"Error during referral deadline job: {e}", exc_info=True)

    async def _run_temp_actions_job(self) -> None:
        """Periodic job lifting expired temporary bans and mutes."""
        try:
            async with async_session_maker() as session:
                mod_service = AdvancedModerationService(session=session, bot=self.bot)
                processed = await mod_service.process_expired_actions()
                await session.commit()
                if processed > 0:
                    logger.info(f"Lifted {processed} expired temporary restrictions")
        except Exception as e:
            logger.error(f"Error during temporary actions job: {e}", exc_info=True)

    async def _run_captcha_check_job(self) -> None:
        """Periodic job checking unverified captcha timeouts."""
        try:
            async with async_session_maker() as session:
                captcha_service = CaptchaService(session=session, bot=self.bot)
                processed = await captcha_service.process_expired_captchas()
                await session.commit()
                if processed > 0:
                    logger.info(f"Handled {processed} expired captcha verifications")
        except Exception as e:
            logger.error(f"Error during captcha check job: {e}", exc_info=True)

    async def _run_autodelete_job(self) -> None:
        """Periodic job deleting queued auto-delete messages."""
        try:
            async with async_session_maker() as session:
                admin_repo = AdminRepository(session)
                now = datetime.now(timezone.utc)
                due = await admin_repo.get_due_auto_delete(now, limit=50)
                if not due:
                    return

                deleted_ids = []
                for item in due:
                    try:
                        group = await session.get(Group, item.group_id)
                        if group:
                            await self.bot.delete_message(chat_id=group.telegram_group_id, message_id=item.message_id)
                    except Exception:
                        pass
                    deleted_ids.append(item.id)

                await admin_repo.remove_auto_delete_items(deleted_ids)
                await session.commit()
        except Exception as e:
            logger.error(f"Error during auto-delete job: {e}", exc_info=True)

    def start(self) -> None:
        """Starts the scheduler with all background workers."""
        if not self._is_running:
            # 1. Referral deadline worker
            self.scheduler.add_job(
                self._run_deadline_check_job,
                "interval",
                seconds=settings.DEADLINE_CHECK_INTERVAL_SECONDS,
                id="referral_deadline_check",
                replace_existing=True
            )
            # 2. Temporary action unban/unmute worker
            self.scheduler.add_job(
                self._run_temp_actions_job,
                "interval",
                seconds=30,
                id="temp_actions_check",
                replace_existing=True
            )
            # 3. Captcha timeout worker
            self.scheduler.add_job(
                self._run_captcha_check_job,
                "interval",
                seconds=30,
                id="captcha_timeout_check",
                replace_existing=True
            )
            # 4. Auto-delete cleanup worker
            self.scheduler.add_job(
                self._run_autodelete_job,
                "interval",
                seconds=15,
                id="autodelete_queue_check",
                replace_existing=True
            )

            self.scheduler.start()
            self._is_running = True
            logger.info("All background workers started successfully.")

    def shutdown(self) -> None:
        """Stops the scheduler gracefully."""
        if self._is_running:
            self.scheduler.shutdown(wait=False)
            self._is_running = False
            logger.info("Background workers scheduler stopped.")
