from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from utils.ui_utils import send_single_ui_message

router = Router()

@router.message(F.text == "📊 Natijalar")
async def show_stats_dashboard(message: Message):
    try:
        await message.delete()
    except Exception:
        pass

    text = (
        "📊 *Natijalar*\n\n"
        "🔧 Bu bo'lim hozirda ishlanmoqda...\n\n"
        "Tez orada siz uchun:\n"
        "• 📈 Barcha bo'limlar bo'yicha progress\n"
        "• 🎯 Hozirgi daraja va bosqich\n"
        "• 🏆 XP balli va streak\n"
        "• 📊 Kuchli va zaif tomonlar tahlili\n\n"
        "_Shaxsiy statistika dashboardi yaratilmoqda. Kuting!_ 🚀"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")]
    ])

    await send_single_ui_message(message, text, reply_markup=kb, parse_mode="Markdown")
