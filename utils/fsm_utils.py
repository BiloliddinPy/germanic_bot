from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
import logging

MAIN_MENU_BUTTONS = [
    "🚀 Kunlik dars",
    "📘 Lug‘at (A1–C1)",
    "📐 Grammatika",
    "🧠 Test va Quiz",
    "🧠 Quiz & Tests", 
    "🧠 Quiz & Test",
    "🗣️ Sprechen & Schreiben",
    "🎥 Video va materiallar",
    "🎓 Imtihon tayyorgarligi",
    "📊 Natijalar",
    "📊 Progress",
    "⚙️ Profil",
    "🏠 Bosh menyu"
]

class StateCleanupMiddleware(BaseMiddleware):
    """
    Automatically clears FSM state if the user clicks a main menu button 
    or sends a command. This prevents users from getting stuck in 
    specialized states (like mid-quiz) when they want to navigate away.
    """
    async def __call__(self, handler, event, data):
        state: FSMContext = data.get("state")
        
        if isinstance(event, Message) and event.text:
            # Clear state on commands
            if event.text.startswith("/"):
                current_state = await state.get_state()
                if current_state:
                    logging.info(f"Clearing state {current_state} for user {event.from_user.id} due to command {event.text}")
                    await state.clear()
            
            # Clear state on main menu buttons
            elif event.text in MAIN_MENU_BUTTONS:
                current_state = await state.get_state()
                if current_state:
                    logging.info(f"Clearing state {current_state} for user {event.from_user.id} due to menu button {event.text}")
                    await state.clear()
        
        elif isinstance(event, CallbackQuery) and event.data == "home":
             # Explicit home button click
             current_state = await state.get_state()
             if current_state:
                logging.info(f"Clearing state {current_state} for user {event.from_user.id} due to 'home' callback")
                await state.clear()

        return await handler(event, data)
