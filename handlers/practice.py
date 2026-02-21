from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from database.repositories.progress_repository import record_navigation_event
from utils.ui_utils import send_single_ui_message

router = Router()

@router.message(F.text.contains("Gapirish va yozish") | F.text.contains("Sprechen & Schreiben"))
async def speaking_writing_handler(message: Message, state: FSMContext):
    await state.clear()
    try:
        await message.delete()
    except Exception:
        pass
    if not message.from_user:
        return

    record_navigation_event(message.from_user.id, "practice_main", entry_type="text")
    
    text = (
        "🗣️ **Sprechen & Schreiben**\n\n"
        "🔧 Bu bo'lim hozirda ishlanmoqda...\n\n"
        "Tez orada ushbu bo'limda siz:\n"
        "• Sun'iy intellekt bilan yozishma (Writing) mashqlarini qilasiz\n"
        "• Ovozli xabar orqali matnlarni talaffuz qilasiz (Speaking)\n"
        "• AI xatolaringizni tekshirib, tahlil qilib beradi\n\n"
        "_Interaktiv amaliyot moduli yaratilmoqda. Kuting!_ 🚀"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")]
    ])
    
    await send_single_ui_message(message, text, reply_markup=kb, parse_mode="Markdown")
