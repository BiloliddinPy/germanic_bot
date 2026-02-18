from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, KeyboardButton, CallbackQuery
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from database import (
    add_user,
    record_navigation_event,
    get_or_create_user_profile,
    get_ui_state,
    set_ui_state
)
from config import DAILY_LESSON_ENABLED, ADMIN_ID

router = Router()
UI_BUILD = "build-2026-02-18-01"
MAIN_MENU_STATE_KEY = "main_menu_message_id"
ACTIVE_UI_STATE_KEY = "active_ui_message_id"
MAIN_MENU_TEXT = "Asosiy menyu:\nKerakli bo'limni tanlang."

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

async def _send_fresh_main_menu(message: Message, text: str, user_id: int | None = None):
    resolved_user_id = user_id or message.chat.id
    existing_main_id = get_ui_state(resolved_user_id, MAIN_MENU_STATE_KEY)
    if existing_main_id:
        try:
            await message.bot.edit_message_text(
                chat_id=resolved_user_id,
                message_id=int(existing_main_id),
                text=text,
                reply_markup=get_main_menu(),
                parse_mode="Markdown"
            )
            set_ui_state(resolved_user_id, ACTIVE_UI_STATE_KEY, existing_main_id)
            return
        except Exception:
            pass

    sent = await message.bot.send_message(
        chat_id=resolved_user_id,
        text=text,
        reply_markup=get_main_menu(),
        parse_mode="Markdown"
    )
    set_ui_state(resolved_user_id, MAIN_MENU_STATE_KEY, sent.message_id)
    set_ui_state(resolved_user_id, ACTIVE_UI_STATE_KEY, sent.message_id)

async def send_single_ui_message(
    message: Message,
    text: str,
    reply_markup=None,
    parse_mode: str | None = None,
    user_id: int | None = None
):
    """Sends one active UI message by deleting previously tracked one."""
    resolved_user_id = user_id or message.chat.id
    prev_active_id = get_ui_state(resolved_user_id, ACTIVE_UI_STATE_KEY)
    main_menu_id = get_ui_state(resolved_user_id, MAIN_MENU_STATE_KEY)
    if prev_active_id and str(prev_active_id) != str(main_menu_id):
        try:
            await message.bot.delete_message(chat_id=resolved_user_id, message_id=int(prev_active_id))
        except Exception:
            pass
    sent = await message.bot.send_message(
        chat_id=resolved_user_id,
        text=text,
        reply_markup=reply_markup,
        parse_mode=parse_mode
    )
    set_ui_state(resolved_user_id, ACTIVE_UI_STATE_KEY, sent.message_id)
    return sent

def get_main_menu():
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

@router.message(CommandStart())
async def cmd_start(message: Message):
    await _safe_delete_message(message)
    add_user(message.from_user.id, message.from_user.full_name, message.from_user.username)
    get_or_create_user_profile(message.from_user.id) # Foundation Day 2 init
    record_navigation_event(message.from_user.id, "start", entry_type="command")
    
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
        f"🔖 {UI_BUILD}\n\n"
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
        f"🔖 Versiya: {UI_BUILD}"
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
