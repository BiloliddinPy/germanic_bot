import os
from dotenv import load_dotenv
from dataclasses import dataclass

load_dotenv()

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _resolve_db_path(raw_path: str) -> str:
    candidate = (raw_path or "").strip() or "./germanic.db"
    candidate = os.path.expanduser(candidate)
    if os.path.isabs(candidate):
        return os.path.abspath(candidate)
    return os.path.abspath(os.path.join(_PROJECT_ROOT, candidate))

@dataclass(frozen=True)
class Config:
    bot_token: str = os.getenv("BOT_TOKEN", "")
    admin_id: int = int(os.getenv("ADMIN_ID", "0"))
    db_path: str = _resolve_db_path(os.getenv("DB_PATH", "./germanic.db"))
    
    # Feature Flags
    daily_lesson_enabled: bool = os.getenv("DAILY_LESSON_ENABLED", "True").lower() == "true"
    mistake_review_enabled: bool = os.getenv("MISTAKE_REVIEW_ENABLED", "True").lower() == "true"
    stats_enabled: bool = os.getenv("STATS_ENABLED", "True").lower() == "true"
    
    # AI Features
    ai_enabled: bool = os.getenv("AI_ENABLED", "False").lower() == "true"
    ai_api_key: str = os.getenv("AI_API_KEY", "")
    
    # Adaptive Logic
    daily_mistake_blend: float = float(os.getenv("DAILY_MISTAKE_BLEND", "0.5"))
    
    # Scheduler
    backup_time_utc: str = os.getenv("BACKUP_TIME_UTC", "03:00")
    
    # UI Constants
    page_size: int = 20
    main_menu_state_key: str = "main_menu_msg_id"
    active_ui_state_key: str = "active_ui_msg_id"

# Global Instance
settings = Config()
