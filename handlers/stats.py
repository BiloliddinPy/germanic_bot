from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from services.user_service import UserService
from services.learning_service import LearningService
from utils.ui_utils import _get_progress_bar
from utils.ui_utils import send_single_ui_message

router = Router()

@router.message(F.text == "📊 Natijalar")
async def show_stats_dashboard(message: Message):
    try:
        await message.delete()
    except Exception:
        pass
    if not message.from_user:
        return
    user_id = message.from_user.id
    profile = UserService.get_profile(user_id) or {}
    level = str(profile.get("current_level") or "A1")
    mastery = LearningService.get_mastery_level(user_id, level)
    progress_bar = _get_progress_bar(mastery["percentage"])

    status_emoji = "🟢" if mastery["percentage"] >= 60 else "🟡" if mastery["percentage"] >= 30 else "🔴"

    text = (
        "📊 *Natijalar*\n\n"
        f"🎯 Joriy daraja: *{level}*\n"
        f"{status_emoji} *Level Progress ({level}):*\n"
        f"{progress_bar} *{mastery['percentage']}%*\n"
        f"_{mastery['mastered']} / {mastery['total']} so'z o'zlashtirilgan_\n\n"
        "ℹ️ Profil bo'limida faqat onboarding ma'lumotlari ko'rsatiladi."
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")]
    ])

    await send_single_ui_message(message, text, reply_markup=kb, parse_mode="Markdown")
