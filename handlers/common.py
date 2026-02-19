from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, KeyboardButton, CallbackQuery
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.fsm.context import FSMContext
import re
from database import (
    add_user,
    record_navigation_event,
    get_or_create_user_profile,
    get_ui_state,
    set_ui_state,
    get_user_profile
)
from handlers.onboarding import start_onboarding
from utils.ui_utils import _send_fresh_main_menu, send_single_ui_message, _md_escape, MAIN_MENU_TEXT
from config import DAILY_LESSON_ENABLED, ADMIN_ID

router = Router()
UI_TEST_MODE = "🛠️ Bot hozirda test rejimida ishlayapti"
# UI tracking keys moved to ui_utils

async def _safe_delete_message(message: Message):
    try:
        await message.delete()
    except Exception:
        pass


async def _delete_tracked_message(message: Message, user_id: int, state_key: str):
    tracked_message_id = get_ui_state(user_id, state_key)
    if not tracked_message_id:
        return
    try:
        await message.bot.delete_message(chat_id=user_id, message_id=int(tracked_message_id))
    except Exception:
        pass

# _send_fresh_main_menu moved to utils.ui_utils

# get_main_menu and send_single_ui_message moved

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await _safe_delete_message(message)
    add_user(message.from_user.id, message.from_user.full_name, message.from_user.username)
    profile = get_or_create_user_profile(message.from_user.id) # Foundation Day 2 init
    record_navigation_event(message.from_user.id, "start", entry_type="command")

    # Onboarding check
    if not profile or not profile.get("onboarding_completed"):
        await start_onboarding(message, state)
        return
    
    text = (
        f"Assalomu alaykum, {message.from_user.full_name}! 👋\n\n"
        "**Germanic EdTech botiga xush kelibsiz!**\n\n"
        "🇩🇪 Nemis tilini biz bilan professional o'rganing:\n"
        "🚀 **Kunlik dars** — Shaxsiy dars rejangiz\n"
        "📘 **Lug'at** — A1-C1 darajadagi so'zlar\n"
        "📐 **Grammatika** — Mukammal qoidalar\n"
        "🧠 **Test va Quiz** — Bilimingizni sinash\n"
        "🗣️ **Sprechen & Schreiben** — Amaliy topshiriqlar\n"
        "🎥 **Video va materiallar** — Qo'shimcha resurslar\n"
        "🎓 **Imtihon tayyorgarligi** — Imtihonga tayyorgarlik\n"
        "📊 **Natijalar** — Natijalaringiz\n"
        "⚙️ **Profil** — Shaxsiy sozlamalar\n\n"
        f"🔖 {UI_TEST_MODE}\n\n"
        "Kerakli bo'limni tanlang:"
    )
    await _send_fresh_main_menu(message, text, user_id=message.from_user.id)

@router.message(Command("menu"))
@router.message(F.text == "🏠 Bosh menyu")
async def cmd_menu(message: Message):
    await _safe_delete_message(message)
    record_navigation_event(message.from_user.id, "main_menu", entry_type="text")
    await _send_fresh_main_menu(message, MAIN_MENU_TEXT, user_id=message.from_user.id)

@router.callback_query(F.data == "home")
async def go_to_home(call: CallbackQuery):
    record_navigation_event(call.from_user.id, "main_menu", entry_type="callback")
    await call.answer()
    try:
        await call.message.delete()
    except Exception:
        pass
    await _send_fresh_main_menu(call.message, MAIN_MENU_TEXT, user_id=call.from_user.id)

@router.message(Command("help"))
async def cmd_help(message: Message):
    await _safe_delete_message(message)
    text = (
        "ℹ️ **Yordam**\n\n"
        "Botdan foydalanish uchun pastdagi tugmalardan birini bosing.\n"
        "Muammolar bo'lsa, 'Aloqa' bo'limidan foydalaning."
    )
    await send_single_ui_message(message, text, reply_markup=get_main_menu(), parse_mode="Markdown")

@router.message(Command("about"))
async def cmd_about(message: Message):
    await _safe_delete_message(message)
    text = (
        "🏢 **Germanic Bot**\n\n"
        "Nemis tilini o'rganuvchilar uchun maxsus ishlab chiqilgan.\n\n"
        f"🔖 {UI_TEST_MODE}"
    )
    await send_single_ui_message(message, text, reply_markup=get_main_menu(), parse_mode="Markdown")

@router.message(Command("contact"))
@router.message(F.text == "☎️ Aloqa")
async def cmd_contact(message: Message):
    await _safe_delete_message(message)
    admin_link = f"tg://user?id={ADMIN_ID}" if ADMIN_ID else ""
    admin_text = f"👤 **Admin:** [Yozish]({admin_link})" if admin_link else "👤 Admin ID sozlanmagan."
    text = (
        "📞 **Biz bilan bog'lanish**\n\n"
        "Savollaringiz bo'lsa, adminga yozishingiz mumkin:\n"
        f"{admin_text}"
    )
    await send_single_ui_message(message, text, parse_mode="Markdown")
