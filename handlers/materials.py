from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from utils.ui_utils import send_single_ui_message

router = Router()
MATERIALS = [
    {
        "id": "a1b1_docx",
        "title": "Grammatik Aktiv A1-B1",
        "path": "data/Grammatik Aktiv A1B1.docx",
        "filename": "Grammatik-Aktiv-A1-B1.docx"
    },
    {
        "id": "b2c1_docx",
        "title": "Grammatik Aktiv B2-C1",
        "path": "data/Grammatik Aktiv B2-C1 .docx",
        "filename": "Grammatik-Aktiv-B2-C1.docx"
    },
    {
        "id": "dict_pdf",
        "title": "Nemis-Uzbek Lug'at (17k+)",
        "path": "data/Nemis tili lug‘at 17.000+  .pdf",
        "filename": "Nemis-Uzbek-Lugat-17k.pdf"
    },
]

def _materials_menu_markup():
    rows = [
        [InlineKeyboardButton(text=f"📘 {m['title']}", callback_data=f"material_send_{m['id']}")]
        for m in MATERIALS
    ]
    rows.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="video_materials_back")])
    rows.append([InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def _find_material(material_id: str):
    return next((m for m in MATERIALS if m["id"] == material_id), None)

@router.message(F.text == "📂 Materiallar")
async def materials_handler(message: Message):
    try:
        await message.delete()
    except Exception:
        pass
    text = (
        "📂 *Materiallar*\n\n"
        "🔧 Bu bo'lim hozirda ishlanmoqda...\n\n"
        "Tez orada siz uchun:\n"
        "• 📘 PDF va DOCX darsliklar\n"
        "• 🎧 Audio materiallar\n"
        "• 🗂️ Darajalar bo'yicha tartiblangan kutubxona\n\n"
        "_Materiallar kutubxonasi yaratilmoqda. Kuting!_ 🚀"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")]
    ])
    await send_single_ui_message(message, text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "materials_open")
@router.callback_query(F.data == "materials_main_menu")
async def materials_open_callback(call: CallbackQuery):
    text = (
        "📂 *Materiallar*\n\n"
        "🔧 Bu bo'lim hozirda ishlanmoqda...\n\n"
        "Tez orada:\n"
        "• 📚 Materiallar daraja yoki mavzu bo'yicha filtrlanadi\n"
        "• 📩 Maqsadli faylni bossangiz — to'g'ridan-to'g'ri chatga yuboriladi\n"
        "• 🗂️ Barcha fayllar kanaldan olinadi\n\n"
        "_Kutubxona yaratilmoqda!_ 🚀"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="video_materials_back")],
        [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")]
    ])
    await call.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")


