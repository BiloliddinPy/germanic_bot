import json
import random
import os
import datetime
from aiogram import Router, F, Bot
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from database import get_subscribed_users
from utils.ui_utils import send_single_ui_message

router = Router()
DATA_DIR = "data"

def load_daily_words():
    file_path = f"{DATA_DIR}/daily_words.json"
    if not os.path.exists(file_path):
        return []
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def get_todays_word():
    words = load_daily_words()
    if not words:
        return None
    day_of_year = datetime.datetime.now().timetuple().tm_yday
    word_index = day_of_year % len(words)
    return words[word_index]

@router.message(F.text == "🌟 Kun so‘zi")
async def daily_word_manual_handler(message: Message):
    try:
        await message.delete()
    except Exception:
        pass
    word = get_todays_word()
    
    if not word:
        await send_single_ui_message(message, "Bugungi kun so'zi hali belgilanmagan.")
        return

    text = (
        f"🌟 **Kun so‘zi**\n\n"
        f"🇩🇪 **{word['de']}** ({word['pos']})\n"
        f"🇺🇿 {word['uz']}\n\n"
        f"📌 Misol:\n"
        f"🇩🇪 _{word['example_de']}_\n"
        f"🇺🇿 _{word['example_uz']}_"
    )
    
    builder = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔁 Boshqa so'z", callback_data="daily_random")],
        [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")]
    ])
    
    await send_single_ui_message(message, text, reply_markup=builder, parse_mode="Markdown")

@router.callback_query(F.data == "daily_random")
async def daily_random_handler(call: CallbackQuery):
    words = load_daily_words()
    if not words:
         await call.answer("So'zlar yo'q.", show_alert=True)
         return
         
    word = random.choice(words)
    
    text = (
        f"🌟 **Tasodifiy so‘z**\n\n"
        f"🇩🇪 **{word['de']}** ({word['pos']})\n"
        f"🇺🇿 {word['uz']}\n\n"
        f"📌 Misol:\n"
        f"🇩🇪 _{word['example_de']}_\n"
        f"🇺🇿 _{word['example_uz']}_"
    )
    
    builder = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔁 Yana", callback_data="daily_random")],
        [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")]
    ])
    
    await call.message.edit_text(text, reply_markup=builder, parse_mode="Markdown")

async def send_daily_word_to_all(bot: Bot):
    try:
        users = get_subscribed_users()
        word = get_todays_word()
        
        if not word or not users:
            return

        text = (
            f"🌟 **Kun so‘zi**\n\n"
            f"🇩🇪 **{word['de']}** ({word['pos']})\n"
            f"🇺🇿 {word['uz']}\n\n"
            f"📌 Misol:\n"
            f"🇩🇪 _{word['example_de']}_\n"
            f"🇺🇿 _{word['example_uz']}_"
        )
        
        import asyncio
        for user_id in users:
            try:
                await bot.send_message(user_id, text, parse_mode="Markdown")
                await asyncio.sleep(0.05) 
            except Exception as e:
                pass
                
    except Exception as e:
        print(f"Daily broadcast error: {e}")
