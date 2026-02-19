from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

def get_levels_keyboard(callback_prefix: str):
    levels = ["A1", "A2", "B1", "B2", "C1"]
    builder = InlineKeyboardBuilder()
    for level in levels:
        builder.button(text=level, callback_data=f"{callback_prefix}_{level}")
    builder.adjust(2) 
    builder.row(InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home"))
    
    return builder.as_markup()

def get_pagination_keyboard(level: str, current_offset: int, has_next: bool, callback_prefix: str):
    builder = InlineKeyboardBuilder()
    if has_next:
        builder.button(text="▶️ Keyingi 20 ta", callback_data=f"{callback_prefix}_next_{level}_{current_offset}")
    builder.row(
        InlineKeyboardButton(text="🔙 Darajalar", callback_data=f"{callback_prefix}_back"),
        InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")
    )
    return builder.as_markup()
def get_quiz_length_keyboard(level: str):
    builder = InlineKeyboardBuilder()
    builder.button(text="10 ta savol", callback_data=f"quiz_start_{level}_10")
    builder.button(text="15 ta savol", callback_data=f"quiz_start_{level}_15")
    builder.button(text="🔙 Orqaga", callback_data="quiz_back")
    return builder.as_markup()

def get_alphabet_keyboard(level: str):
    """Build A-Z keyboard for dictionary letter selection."""
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    builder = InlineKeyboardBuilder()
    
    for letter in alphabet:
        builder.button(text=letter, callback_data=f"dict_letter_{level}_{letter}")
    
    builder.adjust(5)  # 5 buttons per row
    builder.row(InlineKeyboardButton(text="🔙 Darajalar", callback_data="dict_back"))
    return builder.as_markup()

def get_practice_categories_keyboard(callback_prefix: str):
    categories = [
        ("🏠 Kundalik hayot", "daily"),
        ("💼 Ish va karyera", "work"),
        ("✈️ Sayohat", "travel"),
        ("🎓 Ta'lim", "edu"),
        ("🎭 Bo'sh vaqt", "leisure")
    ]
    builder = InlineKeyboardBuilder()
    for text, slug in categories:
        builder.button(text=text, callback_data=f"{callback_prefix}_{slug}")
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home"))
    return builder.as_markup()
def get_main_menu_keyboard():
    builder = ReplyKeyboardBuilder()
    # Row 1: Primary Action
    builder.row(KeyboardButton(text="🚀 Kunlik dars"))
    
    # Row 2: Core Learning
    builder.row(
        KeyboardButton(text="📘 Lug‘at (A1–C1)"),
        KeyboardButton(text="📐 Grammatika")
    )
    
    # Row 3: Practice & Assessment
    builder.row(
        KeyboardButton(text="🧠 Test va Quiz"),
        KeyboardButton(text="🗣️ Sprechen & Schreiben")
    )
    
    # Row 4: Supplement & Exam
    builder.row(
        KeyboardButton(text="🎥 Video va materiallar"),
        KeyboardButton(text="🎓 Imtihon tayyorgarligi")
    )
    
    # Row 5: User Specific
    builder.row(
        KeyboardButton(text="📊 Natijalar"),
        KeyboardButton(text="⚙️ Profil")
    )
    
    return builder.as_markup(resize_keyboard=True)
