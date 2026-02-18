from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

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
