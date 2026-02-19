import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from database import create_table, bootstrap_words_if_empty, DB_NAME, get_total_words_count
from utils.scheduler import start_scheduler
from utils.runtime_state import mark_started
from utils.update_tracking import UpdateTrackingMiddleware
from utils.ops_logging import log_structured
from utils.single_instance import SingleInstanceLock
from utils.fsm_utils import StateCleanupMiddleware

from handlers import common, dictionary, quiz, grammar, video, daily, materials, exams, daily_lesson, practice, onboarding, stats, profile, admin_ops, fallback

async def main():
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    mark_started()
    log_structured("startup", component="main")
    
    create_table()
    restored = bootstrap_words_if_empty()
    if restored:
        logging.warning("Auto-restored words rows: %s", restored)
    logging.info(
        "DB ready path=%s counts={A1:%s,A2:%s,B1:%s,B2:%s,C1:%s}",
        DB_NAME,
        get_total_words_count("A1"),
        get_total_words_count("A2"),
        get_total_words_count("B1"),
        get_total_words_count("B2"),
        get_total_words_count("C1"),
    )

    if not BOT_TOKEN:
        logging.error("BOT_TOKEN is not set in .env file!")
        return

    instance_lock = SingleInstanceLock("./data/bot.instance.lock")
    if not instance_lock.acquire():
        logging.error("Another bot instance is already running (lock exists). Exiting.")
        return

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    update_tracker = UpdateTrackingMiddleware()
    dp.message.middleware(update_tracker)
    dp.callback_query.middleware(update_tracker)
    
    state_cleanup_mw = StateCleanupMiddleware()
    dp.message.middleware(state_cleanup_mw)
    dp.callback_query.middleware(state_cleanup_mw)

    dp.include_router(common.router)
    dp.include_router(onboarding.router)
    dp.include_router(dictionary.router)
    dp.include_router(quiz.router)
    dp.include_router(grammar.router)
    dp.include_router(video.router)
    dp.include_router(daily.router)
    dp.include_router(materials.router)
    dp.include_router(exams.router)
    dp.include_router(practice.router)
    dp.include_router(daily_lesson.router)
    dp.include_router(stats.router)
    dp.include_router(profile.router)
    dp.include_router(admin_ops.router)
    dp.include_router(fallback.router)

    await bot.set_my_commands([
        types.BotCommand(command="start", description="Botni ishga tushirish"),
        types.BotCommand(command="help", description="Yordam"),
        types.BotCommand(command="menu", description="Bosh menyu"),
        types.BotCommand(command="about", description="Loyiha haqida"),
        types.BotCommand(command="contact", description="Aloqa (Admin)"),
        types.BotCommand(command="health", description="Admin health"),
        types.BotCommand(command="admin_stats", description="Admin stats"),
        types.BotCommand(command="ops_last_errors", description="Ops recent errors"),
        types.BotCommand(command="ops_alerts", description="Ops alerts status"),
        types.BotCommand(command="ops_throw_test", description="Ops throw test"),
        types.BotCommand(command="backup_now", description="Run backup now"),
        types.BotCommand(command="backup_list", description="List backups"),
        types.BotCommand(command="backup_send_latest", description="Send latest backup")
    ])

    try:
        # Ensure polling mode is clean even if webhook was previously configured.
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception as e:
        logging.warning("delete_webhook failed: %s", e)

    await start_scheduler(bot)

    logging.info("Germanic Bot started...")
    log_structured("polling_started", component="main")
    try:
        await dp.start_polling(bot)
    finally:
        instance_lock.release()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot stopped!")
