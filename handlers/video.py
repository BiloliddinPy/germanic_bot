import json
import os
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from keyboards.builders import get_levels_keyboard
from database.repositories.progress_repository import record_navigation_event, log_event
from utils.ui_utils import send_single_ui_message

router = Router()
DATA_DIR = "data"

def load_videos():
    file_path = f"{DATA_DIR}/videos.json"
    if not os.path.exists(file_path):
        return []
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

@router.message(F.text == "🎥 Video va materiallar")
async def video_materials_menu(message: Message):
    try:
        await message.delete()
    except Exception:
        pass
    if not message.from_user:
        return
    record_navigation_event(message.from_user.id, "video_materials_menu", entry_type="text")
    text = (
        "🎥 **Video va materiallar**\n\n"
        "Kerakli bo'limni tanlang:"
    )
    builder = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎥 Video", callback_data="video_main_menu")],
        [InlineKeyboardButton(text="📂 Materiallar", callback_data="materials_open")],
        [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")]
    ])
    await send_single_ui_message(message, text, reply_markup=builder, parse_mode="Markdown")

@router.callback_query(F.data == "video_main_menu")
async def video_level_handler(call: CallbackQuery):
    message = call.message if isinstance(call.message, Message) else None
    if not message:
        await call.answer("Xabar topilmadi.", show_alert=True)
        return
    await message.edit_text(
        "🎥 **Video Darslar**\n\nQaysi darajadagi darslarni ko'rmoqchisiz?",
        reply_markup=get_levels_keyboard("video")
    )

@router.callback_query(F.data == "video_materials_back")
async def video_materials_back(call: CallbackQuery):
    message = call.message if isinstance(call.message, Message) else None
    if not message:
        await call.answer("Xabar topilmadi.", show_alert=True)
        return
    text = (
        "🎥 **Video va materiallar**\n\n"
        "Kerakli bo'limni tanlang:"
    )
    builder = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎥 Video", callback_data="video_main_menu")],
        [InlineKeyboardButton(text="📂 Materiallar", callback_data="materials_open")],
        [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")]
    ])
    await message.edit_text(text, reply_markup=builder, parse_mode="Markdown")

@router.callback_query(F.data.startswith("video_") & ~F.data.contains("watch") & ~F.data.contains("back"))
async def video_list_handler(call: CallbackQuery):
    data = call.data or ""
    parts = data.split("_")
    if len(parts) < 2:
        await call.answer("Noto'g'ri video so'rovi.", show_alert=True)
        return
    level = parts[1]
    message = call.message if isinstance(call.message, Message) else None
    if not message:
        await call.answer("Xabar topilmadi.", show_alert=True)
        return
    record_navigation_event(call.from_user.id, "video_materials", level=level, entry_type="callback")
    all_videos = load_videos()
    
    videos = [v for v in all_videos if v['level'] == level]
    
    if not videos:
        await call.answer(f"{level} darajasi uchun videolar hozircha yo'q.", show_alert=True)
        return

    builder = InlineKeyboardMarkup(inline_keyboard=[])
    rows = []
    
    for v in videos:
        rows.append([InlineKeyboardButton(text=v['title'], callback_data=f"video_watch_{v['id']}")])
        
    rows.append([InlineKeyboardButton(text="🔙 Darajalar", callback_data="video_back")])
    builder.inline_keyboard = rows
    
    await message.edit_text(
        f"🎥 **{level} Video Darslari**\n\nTanlang:",
        reply_markup=builder
    )

@router.callback_query(F.data == "video_back")
async def video_back_handler(call: CallbackQuery):
    message = call.message if isinstance(call.message, Message) else None
    if not message:
        await call.answer("Xabar topilmadi.", show_alert=True)
        return
    await message.edit_text(
        "🎥 **Video Darslar**\n\nQaysi darajadagi darslarni ko'rmoqchisiz?",
        reply_markup=get_levels_keyboard("video")
    )

@router.callback_query(F.data.startswith("video_watch_"))
async def video_watch_handler(call: CallbackQuery):
    data = call.data or ""
    video_id = data.replace("video_watch_", "")
    message = call.message if isinstance(call.message, Message) else None
    if not message:
        await call.answer("Xabar topilmadi.", show_alert=True)
        return
    
    all_videos = load_videos()
    video = next((v for v in all_videos if v['id'] == video_id), None)
    
    if not video:
        await call.answer("Video topilmadi.", show_alert=True)
        return
        
    log_event(call.from_user.id, "video_watch", section_name="video", level=video['level'], metadata={"video_id": video_id})
        
    text = (
        f"🎬 **{video['title']}**\n\n"
        f"{video['description']}\n\n"
        f"🔗 [Videoni ko'rish]({video['url']})"
    )
    
    builder = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="▶️ Videoni ochish", url=video['url'])],
        [InlineKeyboardButton(text="🔙 Darslar ro'yxati", callback_data=f"video_{video['level']}")]
    ])
    
    await message.edit_text(text, reply_markup=builder, parse_mode="Markdown")
