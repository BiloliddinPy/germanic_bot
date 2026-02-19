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

from handlers.common import router as common_router
from handlers.onboarding import router as onboarding_router
from handlers.dictionary import router as dictionary_router
from handlers.quiz import router as quiz_router
from handlers.grammar import router as grammar_router
from handlers.video import router as video_router
from handlers.materials import router as materials_router
from handlers.exams import router as exams_router
from handlers.daily_lesson import router as daily_lesson_router
from handlers.practice import router as practice_router
from handlers.stats import router as stats_router
from handlers.profile import router as profile_router
from handlers.admin_ops import router as admin_ops_router
from handlers.fallback import router as fallback_router

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
        common_router, onboarding_router, dictionary_router,
        quiz_router, grammar_router, video_router,
        materials_router, exams_router, practice_router,
        daily_lesson_router, stats_router, profile_router,
        admin_ops_router, fallback_router
    ]
    for router in routers:
        dp.include_router(router)

    # Global Error Handler
    @dp.error()
    async def global_error_handler(event: types.ErrorEvent):
        logging.exception(f"Global error: {event.exception}")
        if event.update.message:
            await event.update.message.answer(
                "⚠️ Kechirasiz, kutilmagan xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring yoki /start buyrug'ini bosing."
            )
        elif event.update.callback_query:
            await event.update.callback_query.answer(
                "⚠️ Xatolik yuz berdi. Iltimos, bosh menyuga qayting.",
                show_alert=True
            )
        return True

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
