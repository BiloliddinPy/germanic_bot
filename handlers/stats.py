from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from services.stats_service import StatsService
from services.user_service import UserService
from utils.ui_utils import send_single_ui_message, _get_progress_bar

router = Router()

@router.message(F.text == "📊 Natijalar")
async def show_stats_dashboard(message: Message):
    try:
        await message.delete()
    except Exception:
        pass
    
    user_id = message.from_user.id
    levels = ["A1", "A2", "B1", "B2", "C1"]
    dashboard = StatsService.get_dashboard_data(user_id, levels)
    
    # Header
    text = "📊 **NATIJALAR DASHBOARDI**\n\n"
    
    # Progress bars for each level
    for level, data in dashboard.items():
        if data["total"] > 0:
            bar = _get_progress_bar(data["percentage"])
            text += f"🔹 **{level} Daraja:**\n"
            text += f"{bar} {data['percentage']}%\n"
            text += f"   _{data['mastered']} / {data['total']} so'z_\n\n"
    
    # Footer info
    text += "🚀 *O'rganishda davom eting! Har kuni yangi natijalar sari!*"
    
    builder = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")]
    ])
    
    StatsService.log_navigation(user_id, "stats")
    
    await send_single_ui_message(
        message,
        text,
        reply_markup=builder,
        parse_mode="Markdown"
    )
