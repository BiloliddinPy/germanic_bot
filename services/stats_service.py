from database.repositories.progress_repository import record_navigation_event, log_event, log_mistake, update_module_progress
from database.repositories.mastery_repository import get_level_progress_stats

class StatsService:
    @staticmethod
    def log_navigation(user_id: int, section: str, level: str = None, **kwargs):
        record_navigation_event(user_id, section, level=level, **kwargs)

    @staticmethod
    def log_activity(user_id: int, event: str, metadata: dict = None, **kwargs):
        log_event(user_id, event, metadata=metadata, **kwargs)

    @staticmethod
    def mark_progress(user_id: int, module: str, level: str, completed: bool = False):
        update_module_progress(user_id, module, level, completed=completed)

    @staticmethod
    def get_dashboard_data(user_id: int, levels: list):
        data = {}
        for level in levels:
            mastered, total = get_level_progress_stats(user_id, level)
            data[level] = {
                "mastered": mastered,
                "total": total,
                "percentage": round((mastered / total * 100), 1) if total > 0 else 0
            }
        return data
