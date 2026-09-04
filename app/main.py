"""Main Application Entry Point."""
import asyncio
import signal
import sys
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from app.config import settings
from utils.logging import setup_logging, get_logger
from database.session import init_db, engine
from services.spam_service import spam_service
from scheduler.deadline_worker import DeadlineWorker
from bot.middleware.db_session import DatabaseSessionMiddleware
from bot.middleware.antispam import AntiSpamMiddleware
from bot.handlers import register_all_routers

logger = get_logger("app.main")


async def main() -> None:
    # 1. Setup structured logging
    setup_logging()
    logger.info("Initializing Telegram Referral Growth & Group Management Bot...")

    # 2. Initialize Database tables
    logger.info("Connecting to database and verifying schema...")
    await init_db()
    logger.info("Database schema initialized successfully.")

    # 3. Initialize Redis/Spam service
    await spam_service.init()

    # 4. Instantiate Bot and Dispatcher
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    # 5. Register Middlewares
    db_middleware = DatabaseSessionMiddleware()
    dp.message.middleware(db_middleware)
    dp.callback_query.middleware(db_middleware)
    dp.chat_member.middleware(db_middleware)

    # Anti-spam middleware on messages
    dp.message.middleware(AntiSpamMiddleware())

    # 6. Register Handlers
    register_all_routers(dp)

    # 7. Start Deadline Worker Scheduler
    deadline_worker = DeadlineWorker(bot=bot)
    deadline_worker.start()

    # 8. Test bot connection and log identity
    bot_user = await bot.get_me()
    logger.info(f"Bot connected successfully as @{bot_user.username} (ID: {bot_user.id})")

    # 9. Start polling with ChatMemberUpdated enabled
    try:
        logger.info("Starting Telegram long-polling (listening for chat_member updates, messages, commands)...")
        # Ensure chat_member update type is listened to for referral attribution
        allowed_updates = ["message", "callback_query", "chat_member", "my_chat_member"]
        await dp.start_polling(bot, allowed_updates=allowed_updates)
    finally:
        logger.info("Shutting down bot services...")
        deadline_worker.shutdown()
        await bot.session.close()
        await engine.dispose()
        if spam_service.redis:
            await spam_service.redis.close()
        logger.info("Bot successfully stopped.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot execution terminated by user or system signal.")
