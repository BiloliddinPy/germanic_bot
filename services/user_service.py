from database.repositories.user_repository import get_or_create_user_profile, update_user_profile
from core.texts import GOAL_LABELS

class UserService:
    @staticmethod
    def get_profile(user_id: int):
        profile = get_or_create_user_profile(user_id)
        if not profile:
            profile = {}
        # Add virtual fields/formatting
        goal_key = str(profile.get("goal") or "")
        profile["goal_label"] = GOAL_LABELS.get(goal_key, "Noma'lum")
        return profile

    @staticmethod
    def set_goal(user_id: int, goal: str):
        update_user_profile(user_id, goal=goal)

    @staticmethod
    def complete_onboarding(user_id: int):
        update_user_profile(user_id, onboarding_completed=1)

    @staticmethod
    def update_level(user_id: int, level: str):
        update_user_profile(user_id, current_level=level)

    @staticmethod
    def update_daily_target(user_id: int, minutes: int):
        update_user_profile(user_id, daily_time_minutes=minutes)

    @staticmethod
    def update_notification_time(user_id: int, time_str: str):
        update_user_profile(user_id, notification_time=time_str)
