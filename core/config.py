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


def _join_webhook_url(base_url: str, path: str) -> str:
    clean_base = (base_url or "").strip().rstrip("/")
    clean_path = (path or "").strip()
    if not clean_base:
        return ""
    if not clean_path.startswith("/"):
        clean_path = "/" + clean_path
    return clean_base + clean_path

@dataclass(frozen=True)
class Config:
    bot_token: str = os.getenv("BOT_TOKEN", "")
    admin_id: int = int(os.getenv("ADMIN_ID", "0"))
    db_backend: str = os.getenv("DB_BACKEND", "sqlite").strip().lower()
    database_url: str = os.getenv("DATABASE_URL", "").strip()
    db_pool_min_size: int = int(os.getenv("DB_POOL_MIN_SIZE", "1"))
    db_pool_max_size: int = int(os.getenv("DB_POOL_MAX_SIZE", "20"))
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
    broadcast_window_minutes: int = int(os.getenv("BROADCAST_WINDOW_MINUTES", "10"))
    broadcast_claim_batch_size: int = int(os.getenv("BROADCAST_CLAIM_BATCH_SIZE", "1000"))
    broadcast_send_concurrency: int = int(os.getenv("BROADCAST_SEND_CONCURRENCY", "30"))
    broadcast_max_attempts: int = int(os.getenv("BROADCAST_MAX_ATTEMPTS", "6"))
    delivery_mode: str = os.getenv("DELIVERY_MODE", "polling").strip().lower()
    webhook_host: str = os.getenv("WEBHOOK_HOST", "0.0.0.0").strip()
    webhook_port: int = int(os.getenv("PORT", os.getenv("WEBHOOK_PORT", "8080")))
    webhook_path: str = os.getenv("WEBHOOK_PATH", "/telegram/webhook").strip()
    webhook_secret_token: str = os.getenv("WEBHOOK_SECRET_TOKEN", "").strip()
    webhook_base_url: str = os.getenv("WEBHOOK_BASE_URL", "").strip()
    webhook_url: str = (
        os.getenv("WEBHOOK_URL", "").strip()
        or _join_webhook_url(os.getenv("WEBHOOK_BASE_URL", "").strip(), os.getenv("WEBHOOK_PATH", "/telegram/webhook").strip())
    )
    
    # UI Constants
    page_size: int = 20
    main_menu_state_key: str = "main_menu_msg_id"
    active_ui_state_key: str = "active_ui_msg_id"

# Global Instance
settings = Config()
