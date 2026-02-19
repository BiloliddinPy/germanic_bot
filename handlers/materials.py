import os
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, FSInputFile
from database.repositories.progress_repository import record_navigation_event, log_event
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
    record_navigation_event(message.from_user.id, "materials", entry_type="text")
    text = (
        "📂 **Materiallar bo'limi**\n\n"
        "Quyidagi materiallardan birini tanlang va bot ichida yuklab oling."
    )
    await send_single_ui_message(message, text, reply_markup=_materials_menu_markup(), parse_mode="Markdown")

@router.callback_query(F.data == "materials_open")
@router.callback_query(F.data == "materials_main_menu")
async def materials_open_callback(call: CallbackQuery):
    record_navigation_event(call.from_user.id, "materials", entry_type="callback")
    text = (
        "📂 **Materiallar bo'limi**\n\n"
        "Quyidagi materiallardan birini tanlang va bot ichida yuklab oling."
    )
    await call.message.edit_text(text, reply_markup=_materials_menu_markup(), parse_mode="Markdown")

@router.callback_query(F.data.startswith("material_send_"))
async def material_send_callback(call: CallbackQuery):
    material_id = call.data.replace("material_send_", "", 1)
    material = _find_material(material_id)
    if not material:
        await call.answer("Material topilmadi.", show_alert=True)
        return

    path = material["path"]
    if not os.path.exists(path):
        await call.answer("Fayl topilmadi. Admin bilan bog'laning.", show_alert=True)
        return

    log_event(call.from_user.id, "material_download", section_name="materials", metadata={"material_id": material_id})
    await call.answer("Material yuborilmoqda...")
    await call.message.answer_document(
        FSInputFile(path, filename=material["filename"]),
        caption=f"📚 **{material['title']}**"
    )
