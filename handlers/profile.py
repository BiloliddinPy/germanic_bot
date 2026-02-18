from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from database import (
    get_or_create_user_profile,
    get_user_profile,
    update_user_profile,
    record_navigation_event,
    get_days_since_first_use
)
from handlers.common import send_single_ui_message

router = Router()

GOAL_LABELS = {
    "exam": "Imtihon",
    "speaking": "Suhbat",
    "general": "Umumiy"
}

TIMEZONE_OPTIONS = ["UTC", "UTC+3", "UTC+5", "UTC+6", "UTC+1"]

def _goal_label(value):
    return GOAL_LABELS.get(value, value or "Belgilanmagan")

def _profile_text(full_name, profile):
    goal = profile.get("goal") or profile.get("learning_goal")
    level = profile.get("current_level") or "A1"
    daily_minutes = profile.get("daily_time_minutes") or profile.get("daily_target") or 20
    tz = profile.get("timezone") or "UTC"
    days = get_days_since_first_use(profile.get("user_id")) if profile.get("user_id") else 0
    return (
        "⚙️ **Profil**\n\n"
        f"👤 **Foydalanuvchi:** {full_name}\n"
        f"📊 **Daraja:** {level}\n"
        f"🎯 **Maqsad:** {_goal_label(goal)}\n"
        f"⏱ **Kunlik vaqt:** {daily_minutes} daqiqa\n"
        f"🌍 **Timezone:** {tz}\n"
        f"📅 **Faollik:** {days} kun\n\n"
        "Quyidan kerakli sozlamani tanlang."
    )

def _profile_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Darajani o'zgartirish", callback_data="profile_edit_level")],
        [InlineKeyboardButton(text="🎯 Maqsadni o'zgartirish", callback_data="profile_edit_goal")],
        [InlineKeyboardButton(text="⏱ Kunlik vaqtni o'zgartirish", callback_data="profile_edit_time")],
        [InlineKeyboardButton(text="🌍 Timezone ni o'zgartirish", callback_data="profile_edit_tz")],
        [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")]
    ])

@router.message(F.text == "⚙️ Profil")
@router.message(F.text == "🎯 Maqsad")
@router.message(F.text == "⚙️ Profil & Maqsad")
async def profile_handler(message: Message):
    try:
        await message.delete()
    except Exception:
        pass
    record_navigation_event(message.from_user.id, "profile", entry_type="text")
    profile = get_or_create_user_profile(message.from_user.id) or {}
    text = _profile_text(message.from_user.full_name, profile)
    await send_single_ui_message(message, text, reply_markup=_profile_menu(), parse_mode="Markdown")

@router.callback_query(F.data == "profile_edit_level")
async def profile_edit_level(call: CallbackQuery):
    levels = ["A1", "A2", "B1", "B2", "C1"]
    rows = []
    for i in range(0, len(levels), 3):
        chunk = levels[i:i+3]
        rows.append([InlineKeyboardButton(text=l, callback_data=f"profile_set_level_{l}") for l in chunk])
    rows.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="profile_back")])
    await call.message.edit_text(
        "📊 **Daraja tanlang:**",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith("profile_set_level_"))
async def profile_set_level(call: CallbackQuery):
    level = call.data.replace("profile_set_level_", "")
    update_user_profile(call.from_user.id, current_level=level, target_level=level)
    await call.answer("Daraja yangilandi ✅")
    await _refresh_profile_view(call)

@router.callback_query(F.data == "profile_edit_goal")
async def profile_edit_goal(call: CallbackQuery):
    builder = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎯 Imtihon", callback_data="profile_set_goal_exam")],
        [InlineKeyboardButton(text="🗣 Suhbat", callback_data="profile_set_goal_speaking")],
        [InlineKeyboardButton(text="🌍 Umumiy", callback_data="profile_set_goal_general")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="profile_back")]
    ])
    await call.message.edit_text("🎯 **Maqsadni tanlang:**", reply_markup=builder, parse_mode="Markdown")

@router.callback_query(F.data.startswith("profile_set_goal_"))
async def profile_set_goal(call: CallbackQuery):
    goal = call.data.replace("profile_set_goal_", "")
    update_user_profile(call.from_user.id, goal=goal, learning_goal=goal)
    await call.answer("Maqsad yangilandi ✅")
    await _refresh_profile_view(call)

@router.callback_query(F.data == "profile_edit_time")
async def profile_edit_time(call: CallbackQuery):
    builder = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="10 daqiqa", callback_data="profile_set_time_10")],
        [InlineKeyboardButton(text="20 daqiqa", callback_data="profile_set_time_20")],
        [InlineKeyboardButton(text="30 daqiqa", callback_data="profile_set_time_30")],
        [InlineKeyboardButton(text="45 daqiqa", callback_data="profile_set_time_45")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="profile_back")]
    ])
    await call.message.edit_text("⏱ **Kunlik vaqtni tanlang:**", reply_markup=builder, parse_mode="Markdown")

@router.callback_query(F.data.startswith("profile_set_time_"))
async def profile_set_time(call: CallbackQuery):
    minutes = int(call.data.replace("profile_set_time_", ""))
    update_user_profile(call.from_user.id, daily_time_minutes=minutes, daily_target=minutes)
    await call.answer("Kunlik vaqt yangilandi ✅")
    await _refresh_profile_view(call)

@router.callback_query(F.data == "profile_edit_tz")
async def profile_edit_tz(call: CallbackQuery):
    rows = [[InlineKeyboardButton(text=tz, callback_data=f"profile_set_tz_{tz.replace('+', 'plus')}")] for tz in TIMEZONE_OPTIONS]
    rows.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="profile_back")])
    await call.message.edit_text("🌍 **Timezone tanlang:**", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="Markdown")

@router.callback_query(F.data.startswith("profile_set_tz_"))
async def profile_set_timezone(call: CallbackQuery):
    tz_raw = call.data.replace("profile_set_tz_", "")
    tz = tz_raw.replace("plus", "+")
    update_user_profile(call.from_user.id, timezone=tz)
    await call.answer("Timezone yangilandi ✅")
    await _refresh_profile_view(call)

@router.callback_query(F.data == "profile_back")
async def profile_back(call: CallbackQuery):
    await _refresh_profile_view(call)

async def _refresh_profile_view(call: CallbackQuery):
    profile = get_or_create_user_profile(call.from_user.id) or {}
    text = _profile_text(call.from_user.full_name or "Foydalanuvchi", profile)
    await call.message.edit_text(text, reply_markup=_profile_menu(), parse_mode="Markdown")
