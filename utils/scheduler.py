from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
from handlers.daily import send_daily_word_to_all

async def start_scheduler(bot: Bot):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_daily_word_to_all, 'cron', hour=9, minute=0, timezone='Asia/Tashkent', args=[bot])
    scheduler.start()
