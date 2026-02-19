import os
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext

DICTIONARY_PDF = "data/Nemis tili lug‘at 17.000+  .pdf"

from database import (
    update_dictionary_progress, 
    get_dictionary_progress, 
    get_words_by_level, 
    get_words_by_level_and_letter,
    get_total_words_count,
    get_total_words_count_by_letter,
    record_navigation_event,
    DB_NAME
)
from utils.ui_utils import send_single_ui_message
from keyboards.builders import get_levels_keyboard, get_pagination_keyboard, get_alphabet_keyboard

router = Router()

PAGE_SIZE = 15 # Reduced for better mobile visibility

@router.message(F.text == "📘 Lug‘at (A1–C1)")
async def show_dictionary_levels(message: Message):
    try:
        await message.delete()
    except Exception:
        pass
    record_navigation_event(message.from_user.id, "dictionary", entry_type="text")
    await send_single_ui_message(
        message,
        "📘 **Lug'at (A1–C1)**\n\nBu bo'limda siz turli darajadagi so'zlarni o'rganishingiz mumkin. Qaysi darajani o'rganmoqchisiz?",
        reply_markup=get_levels_keyboard("dict"),
        parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith("dict_") & ~F.data.startswith("dict_letter_") & ~F.data.startswith("dict_next_"))
async def dictionary_level_handler(call: CallbackQuery):
    data = call.data
    if data == "dict_back":
        await call.message.edit_text(
            "📘 **Lug'at (A1–C1)**\n\nQaysi darajani o'rganmoqchisiz?",
            reply_markup=get_levels_keyboard("dict")
        )
        return

    level = data.split("_")[1]
    # Show Alphabet or Start Browsing
    await call.message.edit_text(
        f"📚 **{level}** darajasi tanlandi.\n\nSo'zlarni alifbo bo'yicha qidirishingiz yoki shunchaki ko'rib chiqishingiz mumkin:",
        reply_markup=get_alphabet_keyboard(level)
    )

@router.callback_query(F.data.startswith("dict_letter_"))
async def dictionary_letter_handler(call: CallbackQuery):
    parts = call.data.split("_")
    level = parts[2]
    letter = parts[3]
    offset = 0
    
    words = get_words_by_level_and_letter(level, letter, limit=PAGE_SIZE, offset=offset)
    total_count = get_total_words_count_by_letter(level, letter)
    
    if not words:
        await call.answer(f"Bu harf ({letter}) uchun so'zlar topilmadi.", show_alert=True)
        return

    await _show_word_page(call, level, words, total_count, offset, f"dict_letter_{letter}", letter=letter)

@router.callback_query(F.data.startswith("dict_next_"))
async def dictionary_pagination_handler(call: CallbackQuery):
    # data format: dict_next_A1_20 or dict_next_letter_A_A1_20
    parts = call.data.split("_")
    
    if parts[2] == "letter":
        # dict_next_letter_A_A1_offset
        letter = parts[3]
        level = parts[4]
        offset = int(parts[5]) + PAGE_SIZE
        words = get_words_by_level_and_letter(level, letter, limit=PAGE_SIZE, offset=offset)
        total_count = get_total_words_count_by_letter(level, letter)
        await _show_word_page(call, level, words, total_count, offset, f"dict_letter_{letter}", letter=letter)
    else:
        # dict_next_A1_offset (Legacy or future use for "All")
        level = parts[2]
        offset = int(parts[3]) + PAGE_SIZE
        words = get_words_by_level(level, limit=PAGE_SIZE, offset=offset)
        total_count = get_total_words_count(level)
        await _show_word_page(call, level, words, total_count, offset, "dict")

async def _show_word_page(call, level, words, total_count, offset, callback_prefix, letter=None):
    header = f"📚 **Lug'at: {level}**"
    if letter:
        header += f" (Harf: {letter})"
    
    sub_header = f"Showing {offset+1}-{offset+len(words)} of {total_count}"
    
    text_lines = [f"{header}\n_{sub_header}_\n"]
    
    for word in words:
        emoji = "🔹"
        pos = f"({word['pos']})" if word['pos'] else ""
        line = f"{emoji} **{word['de']}** {pos}\n   🇺🇿 {word['uz']}\n"
        if word['example_de']:
             line += f"   📌 _{word['example_de']}_\n"
             
        text_lines.append(line)
    
    response_text = "\n".join(text_lines)
    has_next = (offset + PAGE_SIZE) < total_count
    
    # Custom pagination logic for letters
    prefix = callback_prefix
    if letter:
        # We need a custom way to pass 'next' for letters
        # Let's use dict_next_letter_A_A1_20
        next_callback = f"dict_next_letter_{letter}_{level}_{offset}"
    else:
        next_callback = f"dict_next_{level}_{offset}"

    builder = get_pagination_keyboard(next_callback=next_callback, back_callback=f"dict_{level}", back_label="🔙 Alifbo")
    
    try:
        await call.message.edit_text(response_text, reply_markup=builder, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Error editing dictionary message: {e}")
        await call.answer("Xatolik yuz berdi. Iltimos qaytadan urinib ko'ring.")

@router.callback_query(F.data == "dict_pdf")
async def dictionary_pdf_download_handler(call: CallbackQuery):
    if not os.path.exists(DICTIONARY_PDF):
        await call.answer("Kechirasiz, PDF fayl topilmadi.", show_alert=True)
        return
        
    await call.answer("Lug'at yuborilmoqda...")
    document = FSInputFile(DICTIONARY_PDF, filename="Nemis-Uzbek-Lugat-17k.pdf")
    await call.message.answer_document(
        document,
        caption="📘 **Nemis tili lug'ati (17,000+ so'z)**\n\nTo'liq lug'at kitobi."
    )
