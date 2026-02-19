from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from services.user_service import UserService
from services.learning_service import LearningService
from services.stats_service import StatsService
from utils.ui_utils import send_single_ui_message, _get_progress_bar
from keyboards.builders import get_main_menu_keyboard

router = Router()

@router.message(F.text == "⚙️ Profil")
async def show_profile(message: Message):
    try:
        await message.delete()
    except Exception:
        pass
    
    user_id = message.from_user.id
    profile = UserService.get_profile(user_id)
    level = profile.get("current_level", "A1")
    
    mastery = LearningService.get_mastery_level(user_id, level)
    progress_bar = _get_progress_bar(mastery["percentage"])
    
    text = (
        f"👤 **SHAXSIY PROFIL**\n\n"
        f"🆔 ID: `{user_id}`\n"
        f"📊 Daraja: **{level}**\n"
        f"🎯 Maqsad: **{profile['goal_label']}**\n"
        f"⏱ Kunlik: **{profile.get('daily_time_minutes', 15)} min**\n\n"
        f"📈 **Level Progress ({level}):**\n"
        f"{progress_bar} {mastery['percentage']}%\n"
        f"_{mastery['mastered']} / {mastery['total']} so'z o'zlashtirildi_"
    )
    
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✏️ Ma'lumotlarni o'zgartirish", callback_data="onboarding_start"))
    builder.row(InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home"))
    
    StatsService.log_navigation(user_id, "profile")
    
    await send_single_ui_message(
        message, 
        text, 
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )
