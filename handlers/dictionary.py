import os
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile

DICTIONARY_PDF = "data/Nemis tili lug‘at 17.000+  .pdf"
from keyboards.builders import get_levels_keyboard, get_pagination_keyboard
from database import (
    update_dictionary_progress, 
    get_dictionary_progress, 
    get_words_by_level, 
    get_total_words_count,
    record_navigation_event,
    DB_NAME
)
from handlers.common import send_single_ui_message

router = Router()

PAGE_SIZE = 20

@router.message(F.text == "📘 Lug‘at (A1–C1)")
async def show_dictionary_levels(message: Message):
    try:
        await message.delete()
    except Exception:
        pass
    record_navigation_event(message.from_user.id, "dictionary", entry_type="text")
    await send_single_ui_message(
        message,
        "📘 **Lug'at bo'limi**\n\nIltimos, darajani tanlang:",
        reply_markup=get_levels_keyboard("dict"),
        parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith("dict_"))
async def dictionary_callback_handler(call: CallbackQuery):
    data = call.data
    logging.info("dict_callback data=%s db=%s", data, DB_NAME)
    
    if data == "dict_back":
        await call.message.edit_text(
            "📘 **Lug'at bo'limi**\n\nIltimos, darajani tanlang:",
            reply_markup=get_levels_keyboard("dict")
        )
        return

    # Handle Next Page
    if "next" in data:
        _, _, level, offset = data.split("_")
        offset = int(offset) + PAGE_SIZE
    else:
        # Handle Level Selection
        level = data.split("_")[1]
        record_navigation_event(call.from_user.id, "dictionary", level=level, entry_type="callback")
        offset = get_dictionary_progress(call.from_user.id, level)

    # DATABASE FETCH
    words = get_words_by_level(level, limit=PAGE_SIZE, offset=offset)
    total_count = get_total_words_count(level)
    logging.info(
        "dict_fetch user=%s level=%s offset=%s fetched=%s total=%s db=%s",
        call.from_user.id,
        level,
        offset,
        len(words),
        total_count,
        DB_NAME
    )
    
    if not words:
        if offset == 0:
             await call.answer("Bu daraja uchun xozircha so'zlar yo'q.", show_alert=True)
        else:
             await call.answer("✅ Bu darajadagi barcha so'zlar tugadi!", show_alert=True)
             await call.message.edit_text(
                f"✅ **{level}** daraja so'zlari tugadi. (Jami: {total_count} ta)",
                reply_markup=get_levels_keyboard("dict")
             )
        return

    update_dictionary_progress(call.from_user.id, level, offset)
    
    text_lines = [f"📚 **Lug'at: {level}** ({offset+1}-{offset+len(words)} / {total_count})\n"]
    for word in words:
        emoji = "🔹"
        pos = f"({word['pos']})" if word['pos'] else ""
        
        line = (
            f"{emoji} **{word['de']}** {pos}\n"
            f"   🇺🇿 {word['uz']}\n"
        )
        if word['example_de']:
             line += f"   📌 _{word['example_de']}_ ({word['example_uz']})\n"
             
        text_lines.append(line)
    
    response_text = "\n".join(text_lines)
    
    has_next = (offset + PAGE_SIZE) < total_count
    
    await call.message.edit_text(
        response_text,
        reply_markup=get_pagination_keyboard(level, offset, has_next, "dict"),
        parse_mode="Markdown"
    )

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
