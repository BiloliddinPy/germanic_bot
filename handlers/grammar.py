import re
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from services.grammar_service import GrammarService
from services.stats_service import StatsService
from keyboards.builders import get_levels_keyboard
from utils.ui_utils import send_single_ui_message

router = Router()

@router.message(F.text == "📐 Grammatika")
async def show_grammar_levels(message: Message):
    try:
        await message.delete()
    except Exception:
        pass
    
    StatsService.log_navigation(message.from_user.id, "grammar", entry_type="text")
    
    await send_single_ui_message(
        message,
        "📚 **Grammatika**\n\nQaysi darajadagi mavzularni o'rganmoqchisiz?",
        reply_markup=get_levels_keyboard("grammar"),
        parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith("grammar_") & ~F.data.contains("topic") & ~F.data.contains("back"))
async def grammar_topic_list_handler(call: CallbackQuery):
    level = call.data.split("_")[1]
    StatsService.log_navigation(call.from_user.id, "grammar", level=level, entry_type="callback")
    StatsService.mark_progress(call.from_user.id, "grammar", level)

    topics = GrammarService.get_topics_by_level(level)
    if not topics:
        await call.answer("Bu darajada mavzular hali kiritilmagan.", show_alert=True)
        return

    rows = []
    
    # Adaptive recommendation
    rec = GrammarService.get_recommendation(call.from_user.id, level)
    if rec:
        rows.append([
            InlineKeyboardButton(
                text=f"🎯 Tavsiya: {rec.get('title', 'Zaif mavzu')}",
                callback_data=f"grammar_topic_{rec.get('id')}"
            )
        ])

    for topic in topics:
        rows.append([InlineKeyboardButton(text=topic["title"], callback_data=f"grammar_topic_{topic['id']}")])

    rows.append([InlineKeyboardButton(text="🔙 Darajalar", callback_data="grammar_back")])
    rows.append([InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")])
    
    await call.message.edit_text(
        f"📚 **{level} Grammatika Mavzulari**\n\nTanlang:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "grammar_back")
async def grammar_back_handler(call: CallbackQuery):
    await call.message.edit_text(
        "📚 **Grammatika**\n\nQaysi darajadagi mavzularni o'rganmoqchisiz?",
        reply_markup=get_levels_keyboard("grammar"),
        parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith("grammar_topic_"))
async def grammar_topic_detail_handler(call: CallbackQuery):
    topic_id = call.data.replace("grammar_topic_", "")
    topic, level = GrammarService.get_topic_by_id(topic_id)

    if not topic:
        await call.answer("Mavzu topilmadi.", show_alert=True)
        return

    try:
        GrammarService.mark_completed(call.from_user.id, topic_id, level)
    except Exception:
        pass  # Don't let tracking errors kill the view

    # Sanitize GitHub-flavored Markdown → Telegram-safe text
    content = topic.get("content", "")
    content = re.sub(r"^#{1,6}\s*", "", content, flags=re.MULTILINE)  # Remove ### headers
    content = re.sub(r"^>\s*\[!\w+\]\s*", "💡 ", content, flags=re.MULTILINE)  # [!TIP] → 💡
    content = re.sub(r"^>\s*", "  ", content, flags=re.MULTILINE)  # > blockquote indent
    # Remove Markdown table rows (lines starting with |)
    content = re.sub(r"^\|.*\|\s*$", "", content, flags=re.MULTILINE)
    content = re.sub(r"`(.*?)`", r"\1", content)  # strip backtick code (no nested in Telegram)
    content = re.sub(r"\*\*(.*?)\*\*", r"*\1*", content)  # **bold** → *bold* (MarkdownV1)
    content = re.sub(r"\n{3,}", "\n\n", content).strip()  # collapse blank lines

    example = topic.get("example", "")
    
    raw_text = (
        f"📌 *{topic['title']}*\n\n"
        f"{content}\n\n"
        f"📝 *Misollar:*\n{example}"
    )
    
    # Hard cap for Telegram's 4096 limit
    if len(raw_text) > 3800:
        raw_text = raw_text[:3800] + "\n\n_...davomi bor_"

    builder = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Mavzularga qaytish", callback_data=f"grammar_{level}")],
        [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")]
    ])

    try:
        await call.message.edit_text(raw_text, reply_markup=builder, parse_mode="Markdown")
    except Exception as e:
        # Last resort: try without parse_mode
        try:
            plain = re.sub(r"[*_`]", "", raw_text)
            await call.message.edit_text(plain, reply_markup=builder)
        except Exception:
            await call.answer("Mavzu kontenti juda uzun. Tez orada qisqartiriladi.", show_alert=True)
