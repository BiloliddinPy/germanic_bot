import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

# Feature Flags
DAILY_LESSON_ENABLED = os.getenv("DAILY_LESSON_ENABLED", "True").lower() == "true"
MISTAKE_REVIEW_ENABLED = os.getenv("MISTAKE_REVIEW_ENABLED", "True").lower() == "true"
STATS_ENABLED = os.getenv("STATS_ENABLED", "True").lower() == "true"

# AI Features (Safe Defaults: OFF)
AI_ENABLED = os.getenv("AI_ENABLED", "False").lower() == "true"
DAILY_AI_PLANNER_ENABLED = os.getenv("DAILY_AI_PLANNER_ENABLED", "False").lower() == "true"
WRITING_AI_FEEDBACK_ENABLED = os.getenv("WRITING_AI_FEEDBACK_ENABLED", "False").lower() == "true"
REVIEW_AI_ENABLED = os.getenv("REVIEW_AI_ENABLED", "False").lower() == "true"

# Daily Lesson Adaptive Tuning (AI-free)
DAILY_MISTAKE_BLEND = float(os.getenv("DAILY_MISTAKE_BLEND", "0.5"))
DAILY_AVOID_SAME_WRITING = os.getenv("DAILY_AVOID_SAME_WRITING", "True").lower() == "true"

def flag_enabled(name: str) -> bool:
    """Consistently check feature flags."""
    flags = {
        "AI": AI_ENABLED,
        "DAILY_AI_PLANNER": DAILY_AI_PLANNER_ENABLED,
        "WRITING_AI_FEEDBACK": WRITING_AI_FEEDBACK_ENABLED,
        "REVIEW_AI": REVIEW_AI_ENABLED,
        "DAILY_LESSON": DAILY_LESSON_ENABLED,
        "STATS": STATS_ENABLED
    }
    return flags.get(name, False)
