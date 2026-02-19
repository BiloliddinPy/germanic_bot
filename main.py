import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage

from core.config import settings
from database import create_table, bootstrap_words_if_empty
from utils.scheduler import start_scheduler
from utils.runtime_state import mark_started
from utils.update_tracking import UpdateTrackingMiddleware
from utils.single_instance import SingleInstanceLock
from utils.fsm_utils import StateCleanupMiddleware

from handlers import (
    common, dictionary, quiz, grammar, video, 
    materials, exams, daily_lesson, practice, 
    onboarding, stats, profile, admin_ops, fallback
)

async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stdout
    )
    
    mark_started()
    
    # Initialize Database
    create_table()
    bootstrap_words_if_empty()
    
    if not settings.bot_token:
        logging.error("BOT_TOKEN is not set!")
        return

    # Single Instance Lock
    instance_lock = SingleInstanceLock("./data/bot.instance.lock")
    if not instance_lock.acquire():
        logging.error("Another bot instance is already running.")
        return

    # Bot & Dispatcher
    bot = Bot(token=settings.bot_token)
    dp = Dispatcher(storage=MemoryStorage())
    
    # Middlewares
    dp.update.outer_middleware(UpdateTrackingMiddleware())
    dp.update.outer_middleware(StateCleanupMiddleware())
    
    # Register Routers
    routers = [
        common.router, onboarding.router, dictionary.router,
        quiz.router, grammar.router, video.router,
        materials.router, exams.router, practice.router,
        daily_lesson.router, stats.router, profile.router,
        admin_ops.router, fallback.router
    ]
    for router in routers:
        dp.include_router(router)

    # Bot Commands
    await bot.set_my_commands([
        types.BotCommand(command="start", description="Botni ishga tushirish"),
        types.BotCommand(command="menu", description="Bosh menyu"),
        types.BotCommand(command="stats", description="Mening natijalarim"),
        types.BotCommand(command="profile", description="Profil sozlamalari")
    ])

    await bot.delete_webhook(drop_pending_updates=True)
    await start_scheduler(bot)

    logging.info("🚀 Germanic Bot started successfully.")
    try:
        await dp.start_polling(bot)
    finally:
        instance_lock.release()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot stopped by user.")
