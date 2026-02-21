import asyncio
import logging
import sys
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from core.config import settings
from database import create_table, bootstrap_words_if_empty
from utils.scheduler import start_scheduler, stop_scheduler
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
    logging.info("DB path: %s", settings.db_path)
    
    if not settings.bot_token:
        logging.error("BOT_TOKEN is not set!")
        return

    is_webhook_mode = settings.delivery_mode == "webhook"
    instance_lock = None
    if not is_webhook_mode:
        # Polling mode must remain single-instance.
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

    # Bot Commands (scoped): default users do not see admin commands.
    user_commands = [
        types.BotCommand(command="start", description="Botni ishga tushirish"),
        types.BotCommand(command="menu", description="Bosh menyu"),
        types.BotCommand(command="stats", description="Mening natijalarim"),
        types.BotCommand(command="profile", description="Profil sozlamalari"),
    ]
    await bot.set_my_commands(
        user_commands,
        scope=types.BotCommandScopeDefault(),
    )

    if settings.admin_id:
        admin_commands = [
            types.BotCommand(command="start", description="Botni ishga tushirish"),
            types.BotCommand(command="menu", description="Bosh menyu"),
            types.BotCommand(command="admin", description="Admin buyruqlari"),
            types.BotCommand(command="users_count", description="Userlar soni"),
            types.BotCommand(command="admin_stats", description="Admin statistika"),
            types.BotCommand(command="health", description="Bot health"),
            types.BotCommand(command="webhook_info", description="Webhook holati"),
            types.BotCommand(command="backup_now", description="Backup yaratish"),
            types.BotCommand(command="diag_db", description="DB diagnostika"),
        ]
        await bot.set_my_commands(
            admin_commands,
            scope=types.BotCommandScopeChat(chat_id=int(settings.admin_id)),
        )

    await start_scheduler(bot)

    if is_webhook_mode:
        if not settings.webhook_url:
            logging.error("WEBHOOK_URL (or WEBHOOK_BASE_URL + WEBHOOK_PATH) is required in webhook mode.")
            stop_scheduler()
            return

        await bot.set_webhook(
            url=settings.webhook_url,
            secret_token=(settings.webhook_secret_token or None),
            drop_pending_updates=False,
        )

        app = web.Application()
        webhook_requests_handler = SimpleRequestHandler(
            dispatcher=dp,
            bot=bot,
            secret_token=(settings.webhook_secret_token or None),
        )
        webhook_requests_handler.register(app, path=settings.webhook_path)
        setup_application(app, dp, bot=bot)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host=settings.webhook_host, port=settings.webhook_port)
        await site.start()

        logging.info(
            "🚀 Germanic Bot started in webhook mode. listen=%s:%s path=%s webhook_url=%s",
            settings.webhook_host,
            settings.webhook_port,
            settings.webhook_path,
            settings.webhook_url,
        )
        try:
            while True:
                await asyncio.sleep(3600)
        finally:
            stop_scheduler()
            try:
                await runner.cleanup()
            except Exception:
                pass
    else:
        await bot.delete_webhook(drop_pending_updates=True)
        logging.info("🚀 Germanic Bot started in polling mode.")
        try:
            await dp.start_polling(bot)
        finally:
            stop_scheduler()
            if instance_lock:
                instance_lock.release()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot stopped by user.")
