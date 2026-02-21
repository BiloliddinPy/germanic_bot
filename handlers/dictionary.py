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
from core.texts import BTN_DICTIONARY

router = Router()

@router.message(F.text == BTN_DICTIONARY)
async def show_dictionary_levels(message: Message):
    try:
        await message.delete()
    except Exception:
        pass
    
    if not message.from_user:
        return
    StatsService.log_navigation(message.from_user.id, "dictionary", entry_type="text")
    
    await send_single_ui_message(
        message,
        "📘 **Lug'at (A1–C1)**\n\nBu bo'limda siz turli darajadagi so'zlarni o'rganishingiz mumkin. Qaysi darajani o'rganmoqchisiz?",
        reply_markup=get_levels_keyboard("dict"),
        parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith("dict_alpha_"))
async def dictionary_alphabet_view_handler(call: CallbackQuery):
    """Shows the A-Z letter picker for a specific level."""
    data = call.data or ""
    parts = data.split("_")
    if len(parts) < 3:
        await call.answer("Noto'g'ri lug'at so'rovi.", show_alert=True)
        return
    level = parts[2]
    message = call.message if isinstance(call.message, Message) else None
    if not message:
        await call.answer("Xabar topilmadi.", show_alert=True)
        return
    await message.edit_text(
        f"🔍 *{level}* - qidirish uchun harfni tanlang:",
        reply_markup=get_alphabet_keyboard(level),
        parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith("dict_letter_"))
async def dictionary_letter_handler(call: CallbackQuery):
    """Handles letter selection from alphabet keyboard."""
    data = call.data or ""
    parts = data.split("_")
    if len(parts) < 4:
        await call.answer("Noto'g'ri harf so'rovi.", show_alert=True)
        return
    level = parts[2]
    letter = parts[3]
    offset = 0
    
    result = DictionaryService.get_page(level, offset=offset, letter=letter)
    
    if not result["words"]:
        await call.answer(f"Bu harf ({letter}) uchun so'zlar topilmadi.", show_alert=True)
        return

    await _show_word_page(call, level, result, offset, letter=letter)

@router.callback_query(F.data.startswith("dict_next_"))
async def dictionary_pagination_handler(call: CallbackQuery):
    """Handles Next page pagination."""
    data = call.data or ""
    parts = data.split("_")
    if len(parts) < 4:
        await call.answer("Noto'g'ri sahifa so'rovi.", show_alert=True)
        return
    
    if parts[2] == "letter":
        letter = parts[3]
        level = parts[4]
        offset = int(parts[5]) + settings.page_size
        result = DictionaryService.get_page(level, offset=offset, letter=letter)
        await _show_word_page(call, level, result, offset, letter=letter)
    else:
        level = parts[2]
        offset = int(parts[3]) + settings.page_size
        result = DictionaryService.get_page(level, offset=offset)
        await _show_word_page(call, level, result, offset)

@router.callback_query(F.data.startswith("dict_") & ~F.data.startswith("dict_letter_") & ~F.data.startswith("dict_next_") & ~F.data.startswith("dict_alpha_") & ~F.data.contains("pdf"))
async def dictionary_level_handler(call: CallbackQuery):
    """Handles level selection (dict_A1, etc.) and dict_back."""
    data = call.data or ""
    message = call.message if isinstance(call.message, Message) else None
    if not message:
        await call.answer("Xabar topilmadi.", show_alert=True)
        return
    if data == "dict_back":
        await message.edit_text(
            "📘 **Lug'at (A1–C1)**\n\nQaysi darajani o'rganmoqchisiz?",
            reply_markup=get_levels_keyboard("dict"),
            parse_mode="Markdown"
        )
        return

    parts = data.split("_")
    if len(parts) < 2:
        await call.answer("Noto'g'ri daraja so'rovi.", show_alert=True)
        return
    level = parts[1]
    result = DictionaryService.get_page(level, offset=0)
    await _show_word_page(call, level, result, 0)

async def _show_word_page(call, level, result, offset, letter=None):
    """Renders a page of dictionary words, safely within Telegram's 4096 char limit."""
    words = result["words"]
    total = result["total"]
    
    header = f"📚 *Lug'at: {level}*"
    if letter:
        header += f" | Harf: *{letter}*"
    
    sub_header = f"_{offset + 1}–{offset + len(words)} / {total} ta so'z_"
    lines = [f"{header}\n{sub_header}\n"]
    
    MAX_LEN = 3600  # safely under Telegram's 4096 char limit
    
    for word in words:
        pos = f" `{word['pos']}`" if word.get('pos') else ""
        line = f"🔹 *{word['de']}*{pos} — {word['uz']}\n"
        if "\n".join(lines + [line]).__len__() > MAX_LEN:
            break
        lines.append(line)
    
    response_text = "\n".join(lines)
    
    # Pagination
    if letter:
        next_callback = f"dict_next_letter_{letter}_{level}_{offset}"
        back_callback = f"dict_alpha_{level}"
        back_label = "🔙 Alifbo"
    else:
        next_callback = f"dict_next_{level}_{offset}"
        back_callback = "dict_back"
        back_label = "🔙 Orqaga"

    builder = get_pagination_keyboard(
        next_callback=next_callback if result["has_next"] else None,
        back_callback=back_callback,
        back_label=back_label
    )
    
    # Append alphabet search button if browsing all words (not filtered)
    if not letter:
        kb = InlineKeyboardBuilder.from_markup(builder)
        kb.row(InlineKeyboardButton(
            text="🔍 Alifbo bo'yicha qidirish",
            callback_data=f"dict_alpha_{level}"
        ))
        builder = kb.as_markup()
    
    message = call.message if isinstance(call.message, Message) else None
    if not message:
        await call.answer("Xabar topilmadi.", show_alert=True)
        return
    try:
        await message.edit_text(response_text, reply_markup=builder, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Dictionary edit error: {e}")
        await call.answer("Xatolik yuz berdi. Qaytadan urinib ko'ring.", show_alert=True)

@router.callback_query(F.data == "dict_pdf")
async def dictionary_pdf_download_handler(call: CallbackQuery):
    pdf_path = "data/Nemis tili lug'at 17.000+  .pdf"
    if not os.path.exists(pdf_path):
        await call.answer("Kechirasiz, PDF fayl topilmadi.", show_alert=True)
        return
        
    message = call.message if isinstance(call.message, Message) else None
    if not message:
        await call.answer("Xabar topilmadi.", show_alert=True)
        return
    await call.answer("Lug'at yuborilmoqda...")
    document = FSInputFile(pdf_path, filename="Nemis-Uzbek-Lugat-17k.pdf")
    await message.answer_document(
        document,
        caption="📘 **Nemis tili lug'ati (17,000+ so'z)**\n\nTo'liq lug'at kitobi."
    )
