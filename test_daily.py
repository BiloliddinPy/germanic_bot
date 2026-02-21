import asyncio
from unittest.mock import AsyncMock
from aiogram.types import Message
from handlers.daily_lesson import _render_step
from aiogram import Bot

async def main():
    message = AsyncMock(spec=Message)
    message.edit_text = AsyncMock()
    
    state = {
        "step": 1,
        "plan": {
            "grammar_topic_id": None
        }
    }
    
    try:
        await _render_step(message, 1, state)
        print("Success for step 1")
    except Exception as e:
        print(f"CRASH step 1: {type(e).__name__}: {e}")

asyncio.run(main())
