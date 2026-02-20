import os
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from services.dictionary_service import DictionaryService
from services.stats_service import StatsService
from core.config import settings
from utils.ui_utils import send_single_ui_message
from keyboards.builders import get_levels_keyboard, get_pagination_keyboard, get_alphabet_keyboard

router = Router()

@router.message(F.text == "📘 Lug‘at (A1–C1)")
async def show_dictionary_levels(message: Message):
    try:
        await message.delete()
    except Exception:
        pass
    
    StatsService.log_navigation(message.from_user.id, "dictionary", entry_type="text")
    
    await send_single_ui_message(
        message,
        "📘 **Lug'at (A1–C1)**\n\nBu bo'limda siz turli darajadagi so'zlarni o'rganishingiz mumkin. Qaysi darajani o'rganmoqchisiz?",
        reply_markup=get_levels_keyboard("dict"),
        parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith("dict_") & ~F.data.startswith("dict_letter_") & ~F.data.startswith("dict_next_") & ~F.data.contains("pdf"))
async def dictionary_level_handler(call: CallbackQuery):
    data = call.data
    if data == "dict_back":
        await call.message.edit_text(
            "📘 **Lug'at (A1–C1)**\n\nQaysi darajani o'rganmoqchisiz?",
            reply_markup=get_levels_keyboard("dict")
        )
        return

    level = data.split("_")[1]
    result = DictionaryService.get_page(level, offset=0)
    await _show_word_page(call, level, result, 0, "dict")

@router.callback_query(F.data.startswith("dict_letter_"))
async def dictionary_letter_handler(call: CallbackQuery):
    parts = call.data.split("_")
    level = parts[2]
    letter = parts[3]
    offset = 0
    
    result = DictionaryService.get_page(level, offset=offset, letter=letter)
    
    if not result["words"]:
        await call.answer(f"Bu harf ({letter}) uchun so'zlar topilmadi.", show_alert=True)
        return

    await _show_word_page(call, level, result, offset, f"dict_letter_{letter}", letter=letter)

@router.callback_query(F.data.startswith("dict_next_"))
async def dictionary_pagination_handler(call: CallbackQuery):
    parts = call.data.split("_")
    
    if parts[2] == "letter":
        letter = parts[3]
        level = parts[4]
        offset = int(parts[5]) + settings.page_size
        result = DictionaryService.get_page(level, offset=offset, letter=letter)
        await _show_word_page(call, level, result, offset, f"dict_letter_{letter}", letter=letter)
    else:
        level = parts[2]
        offset = int(parts[3]) + settings.page_size
        result = DictionaryService.get_page(level, offset=offset)
        await _show_word_page(call, level, result, offset, "dict")

async def _show_word_page(call, level, result, offset, callback_prefix, letter=None):
    words = result["words"]
    total = result["total"]
    
    header = f"📚 **Lug'at: {level}**"
    if letter:
        header += f" (Harf: {letter})"
    
    sub_header = f"Showing {offset+1}-{offset+len(words)} of {total}"
    text_lines = [f"{header}\n_{sub_header}_\n"]
    
    for word in words:
        emoji = "🔹"
        pos = f"({word['pos']})" if word['pos'] else ""
        line = f"{emoji} **{word['de']}** {pos}\n   🇺🇿 {word['uz']}\n"
        if word['example_de']:
             line += f"   📌 _{word['example_de']}_\n"
             
        text_lines.append(line)
    
    response_text = "\n".join(text_lines)
    
    if letter:
        next_callback = f"dict_next_letter_{letter}_{level}_{offset}"
    else:
        next_callback = f"dict_next_{level}_{offset}"

    builder = get_pagination_keyboard(
        next_callback=next_callback if result["has_next"] else None, 
        back_callback="dict_back" if not letter else f"dict_alpha_{level}", 
        back_label="🔙 Orqaga" if not letter else "🔙 Alifbo"
    )
    
    # Add Alphabet Search button if not searching by letter already
    if not letter:
        kb_builder = InlineKeyboardBuilder.from_markup(builder)
        kb_builder.row(InlineKeyboardButton(text="🔍 Alifbo bo'yicha qidirish", callback_data=f"dict_alpha_{level}"))
        builder = kb_builder.as_markup()
    
    try:
        await call.message.edit_text(response_text, reply_markup=builder, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Error editing dictionary message: {e}")
        await call.answer("Xatolik yuz berdi. Iltimos qaytadan urinib ko'ring.")

@router.callback_query(F.data.startswith("dict_alpha_"))
async def dictionary_alphabet_view_handler(call: CallbackQuery):
    level = call.data.split("_")[2]
    await call.message.edit_text(
        f"🔍 **{level}** - qidirish uchun harfni tanlang:",
        reply_markup=get_alphabet_keyboard(level)
    )

@router.callback_query(F.data == "dict_pdf")
async def dictionary_pdf_download_handler(call: CallbackQuery):
    pdf_path = "data/Nemis tili lug‘at 17.000+  .pdf"
    if not os.path.exists(pdf_path):
        await call.answer("Kechirasiz, PDF fayl topilmadi.", show_alert=True)
        return
        
    await call.answer("Lug'at yuborilmoqda...")
    document = FSInputFile(pdf_path, filename="Nemis-Uzbek-Lugat-17k.pdf")
    await call.message.answer_document(
        document,
        caption="📘 **Nemis tili lug'ati (17,000+ so'z)**\n\nTo'liq lug'at kitobi."
    )
