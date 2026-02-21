from aiogram.types import InlineKeyboardButton, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from core.texts import BTN_HOME, BTN_BACK, BTN_DAILY_LESSON, BTN_DICTIONARY, BTN_GRAMMAR, BTN_QUIZ, BTN_PRACTICE, BTN_VIDEO, BTN_EXAMS, BTN_STATS, BTN_PROFILE

def get_levels_keyboard(callback_prefix: str):
    levels = ["A1", "A2", "B1", "B2", "C1"]
    builder = InlineKeyboardBuilder()
    for level in levels:
        builder.button(text=level, callback_data=f"{callback_prefix}_{level}")
    builder.adjust(2) 
    builder.row(InlineKeyboardButton(text=BTN_HOME, callback_data="home"))
    return builder.as_markup()

def get_pagination_keyboard(next_callback: str | None = None, back_callback: str = "home", back_label: str = BTN_BACK):
    builder = InlineKeyboardBuilder()
    if next_callback:
        builder.button(text="▶️ Keyingi", callback_data=next_callback)
    
    builder.row(
        InlineKeyboardButton(text=back_label, callback_data=back_callback),
        InlineKeyboardButton(text=BTN_HOME, callback_data="home")
    )
    return builder.as_markup()

def get_quiz_length_keyboard(level: str):
    builder = InlineKeyboardBuilder()
    builder.button(text="10 ta savol", callback_data=f"quiz_start_{level}_10")
    builder.button(text="15 ta savol", callback_data=f"quiz_start_{level}_15")
    builder.button(text=BTN_BACK, callback_data="quiz_back")
    return builder.as_markup()

def get_alphabet_keyboard(level: str):
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    builder = InlineKeyboardBuilder()
    for letter in alphabet:
        builder.button(text=letter, callback_data=f"dict_letter_{level}_{letter}")
    builder.adjust(5)
    builder.row(InlineKeyboardButton(text=BTN_BACK, callback_data="dict_back"), InlineKeyboardButton(text=BTN_HOME, callback_data="home"))
    return builder.as_markup()

def get_main_menu_keyboard():
    builder = ReplyKeyboardBuilder()
    # Row 1: Primary Action
    builder.row(KeyboardButton(text=BTN_DAILY_LESSON))
    # Row 2: Core Learning
    builder.row(KeyboardButton(text=BTN_DICTIONARY), KeyboardButton(text=BTN_GRAMMAR))
    # Row 3: Practice & Assessment
    builder.row(KeyboardButton(text=BTN_QUIZ), KeyboardButton(text=BTN_PRACTICE))
    # Row 4: Supplement & Exam
    builder.row(KeyboardButton(text=BTN_VIDEO), KeyboardButton(text=BTN_EXAMS))
    # Row 5: User Specific
    builder.row(KeyboardButton(text=BTN_STATS), KeyboardButton(text=BTN_PROFILE))
    
    return builder.as_markup(resize_keyboard=True)

def get_main_menu():
    """Alias for backward compatibility."""
    return get_main_menu_keyboard()

def get_practice_categories_keyboard(callback_prefix: str = "practice_cat"):
    categories = [
        ("🏠 Kundalik hayot", "daily"),
        ("💼 Ish va karyera", "work"),
        ("✈️ Sayohat", "travel"),
        ("🌍 Umumiy", "general")
    ]
    builder = InlineKeyboardBuilder()
    for text, code in categories:
        builder.button(text=text, callback_data=f"practice_cat_{code}")
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text=BTN_BACK, callback_data="practice_back_main"))
    return builder.as_markup()
