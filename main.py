import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from database import create_table
from utils.scheduler import start_scheduler

from handlers import common, dictionary, quiz, grammar, video, daily, materials, exams, daily_lesson, practice, stats, profile, fallback

async def main():
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    
    create_table()

    if not BOT_TOKEN:
        logging.error("BOT_TOKEN is not set in .env file!")
        return

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(common.router)
    dp.include_router(dictionary.router)
    dp.include_router(quiz.router)
    dp.include_router(grammar.router)
    dp.include_router(video.router)
    dp.include_router(daily.router)
    dp.include_router(materials.router)
    dp.include_router(exams.router)
    dp.include_router(daily_lesson.router)
    dp.include_router(practice.router)
    dp.include_router(stats.router)
    dp.include_router(profile.router)
    dp.include_router(fallback.router)

    await bot.set_my_commands([
        types.BotCommand(command="start", description="Botni ishga tushirish"),
        types.BotCommand(command="help", description="Yordam"),
        types.BotCommand(command="menu", description="Bosh menyu"),
        types.BotCommand(command="about", description="Loyiha haqida"),
        types.BotCommand(command="contact", description="Aloqa (Admin)")
    ])

    await start_scheduler(bot)

    logging.info("Germanic Bot started...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot stopped!")
