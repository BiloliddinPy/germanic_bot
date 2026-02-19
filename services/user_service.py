from database.repositories.user_repository import get_or_create_user_profile, update_user_profile
from core.texts import GOAL_LABELS

class UserService:
    @staticmethod
    def get_profile(user_id: int):
        profile = get_or_create_user_profile(user_id)
        # Add virtual fields/formatting
        profile["goal_label"] = GOAL_LABELS.get(profile.get("goal"), "Noma'lum")
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
