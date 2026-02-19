from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from database import get_or_create_user_profile # From package init
from database.repositories.user_repository import add_user, get_user_profile
from database.repositories.progress_repository import record_navigation_event
from database.repositories.ui_repository import get_ui_state, set_ui_state
from handlers.onboarding import start_onboarding
from utils.ui_utils import _send_fresh_main_menu, send_single_ui_message, MAIN_MENU_TEXT
from core.config import settings

router = Router()
UI_TEST_MODE = "🛠️ Bot hozirda test rejimida ishlayapti"

async def _safe_delete_message(message: Message):
    try:
        await message.delete()
    except Exception:
        pass

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await _safe_delete_message(message)
    add_user(message.from_user.id, message.from_user.full_name, message.from_user.username)
    profile = get_or_create_user_profile(message.from_user.id)
    record_navigation_event(message.from_user.id, "start", entry_type="command")

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
    from keyboards.builders import get_main_menu
    await send_single_ui_message(message, text, reply_markup=get_main_menu(), parse_mode="Markdown")

@router.message(Command("about"))
async def cmd_about(message: Message):
    await _safe_delete_message(message)
    text = (
        "🏢 **Germanic Bot**\n\n"
        "Nemis tilini o'rganuvchilar uchun maxsus ishlab chiqilgan.\n\n"
        f"🔖 {UI_TEST_MODE}"
    )
    from keyboards.builders import get_main_menu
    await send_single_ui_message(message, text, reply_markup=get_main_menu(), parse_mode="Markdown")

@router.message(Command("contact"))
@router.message(F.text == "☎️ Aloqa")
async def cmd_contact(message: Message):
    await _safe_delete_message(message)
    admin_id = settings.admin_id
    admin_link = f"tg://user?id={admin_id}" if admin_id else ""
    admin_text = f"👤 **Admin:** [Yozish]({admin_link})" if admin_link else "👤 Admin ID sozlanmagan."
    text = (
        "📞 **Biz bilan bog'lanish**\n\n"
        "Savollaringiz bo'lsa, adminga yozishingiz mumkin:\n"
        f"{admin_text}"
    )
    await send_single_ui_message(message, text, parse_mode="Markdown")
