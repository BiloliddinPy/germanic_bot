import json
import os
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from keyboards.builders import get_levels_keyboard
from database import (
    record_navigation_event,
    update_module_progress,
    mark_grammar_topic_seen,
    log_event,
    get_recent_topic_mistake_scores,
)
from handlers.common import send_single_ui_message

router = Router()
DATA_DIR = "data"
GRAMMAR_PDF = "data/Grammatik Aktiv A1B1.docx"


def load_grammar():
    file_path = f"{DATA_DIR}/grammar.json"
    if not os.path.exists(file_path):
        return {}
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _find_topic(topics, topic_id):
    for topic in topics:
        if topic.get("id") == topic_id:
            return topic
    return None


@router.message(F.text == "📐 Grammatika")
async def grammar_level_handler(message: Message):
    try:
        await message.delete()
    except Exception:
        pass
    record_navigation_event(message.from_user.id, "grammar", entry_type="text")
    await send_single_ui_message(
        message,
        "📚 **Grammatika**\n\nQaysi darajadagi mavzularni o'rganmoqchisiz?",
        reply_markup=get_levels_keyboard("grammar"),
        parse_mode="Markdown"
    )


@router.callback_query(
    F.data.startswith("grammar_")
    & ~F.data.contains("topic")
    & ~F.data.contains("back")
    & ~F.data.contains("pdf")
)
async def grammar_topic_list_handler(call: CallbackQuery):
    level = call.data.split("_")[1]
    record_navigation_event(call.from_user.id, "grammar", level=level, entry_type="callback")
    update_module_progress(call.from_user.id, "grammar", level)

    data = load_grammar()
    topics = data.get(level, [])

    if not topics:
        await call.answer("Bu darajada mavzular hali kiritilmagan.", show_alert=True)
        return

    rows = []

    # Adaptive recommendation based on recent mistakes in this level.
    weak_topics = get_recent_topic_mistake_scores(call.from_user.id, level, days=14, limit=1)
    if weak_topics:
        weak_topic_id = weak_topics[0][0]
        weak_topic = _find_topic(topics, weak_topic_id)
        if weak_topic:
            rows.append([
                InlineKeyboardButton(
                    text=f"🎯 Tavsiya: {weak_topic.get('title', 'Zaif mavzu')}",
                    callback_data=f"grammar_topic_{weak_topic_id}"
                )
            ])

    for topic in topics:
        rows.append([InlineKeyboardButton(text=topic["title"], callback_data=f"grammar_topic_{topic['id']}")])

    rows.append([InlineKeyboardButton(text="🔙 Darajalar", callback_data="grammar_back")])
    builder = InlineKeyboardMarkup(inline_keyboard=rows)

    await call.message.edit_text(
        f"📚 **{level} Grammatika Mavzulari**\n\nTanlang:",
        reply_markup=builder,
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

    data = load_grammar()
    found_topic = None
    level_found = None

    for level, topics in data.items():
        for topic in topics:
            if topic.get("id") == topic_id:
                found_topic = topic
                level_found = level
                break
        if found_topic:
            break

    if not found_topic or not level_found:
        await call.answer("Mavzu topilmadi.", show_alert=True)
        return

    mark_grammar_topic_seen(call.from_user.id, topic_id, level_found)
    update_module_progress(call.from_user.id, "grammar", level_found, completed=True)
    log_event(
        call.from_user.id,
        "grammar_topic_opened",
        section_name="grammar",
        level=level_found,
        metadata={"topic_id": topic_id}
    )

    text = (
        f"📌 **{found_topic['title']}**\n\n"
        f"{found_topic['content']}\n\n"
        f"📝 **Misollar:**\n{found_topic['example']}"
    )

    builder = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Mavzularga qaytish", callback_data=f"grammar_{level_found}")],
        [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")]
    ])

    await call.message.edit_text(text, reply_markup=builder, parse_mode="Markdown")


@router.callback_query(F.data == "grammar_pdf")
async def grammar_pdf_download_handler(call: CallbackQuery):
    if not os.path.exists(GRAMMAR_PDF):
        await call.answer("Kechirasiz, PDF fayl topilmadi.", show_alert=True)
        return

    await call.answer("Fayl yuborilmoqda...")
    document = FSInputFile(GRAMMAR_PDF, filename="Grammatik-Aktiv-A1-B1.docx")
    await call.message.answer_document(
        document,
        caption="📚 **Grammatik Aktiv A1-B1**\n\nNemis tili grammatikasi uchun qo'llanma."
    )
