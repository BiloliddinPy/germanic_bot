import datetime
from database.repositories.mastery_repository import get_due_reviews, update_mastery, get_level_progress_stats, get_weighted_mistake_word_ids
from database.repositories.word_repository import get_words_by_ids, get_random_words
from database.repositories.lesson_repository import get_last_daily_plan, get_grammar_coverage_map
from services.grammar_service import GrammarService
from core.config import settings

class LearningService:
    @staticmethod
    def get_daily_lesson_pool(user_id: int, level: str, count: int = 10):
        """
        Mixes SRS due reviews with new words for a daily session.
        """
        # 1. Get due reviews
        due_ids = get_due_reviews(user_id, limit=int(count * settings.daily_mistake_blend))
        due_words = get_words_by_ids(due_ids)
        
        # 2. Add new words to reach 'count'
        remaining = count - len(due_words)
        new_words = []
        if remaining > 0:
            new_words = get_random_words(level, limit=remaining)
            
        return {
            "reviews": due_words,
            "new": new_words,
            "total_count": len(due_words) + len(new_words)
        }

    @staticmethod
    def process_review_result(user_id: int, item_id: int, is_correct: bool):
        update_mastery(user_id, item_id, is_correct)

    @staticmethod
    def get_mastery_level(user_id: int, level: str):
        mastered, total = get_level_progress_stats(user_id, level)
        percentage = (mastered / total * 100) if total > 0 else 0
        return {
            "mastered": mastered,
            "total": total,
            "percentage": round(percentage, 1)
        }

    @staticmethod
    def create_daily_plan(user_id: int, profile: dict):
        level = profile.get("current_level", "A1")
        # Logic from daily_lesson.py build_daily_plan
        minutes = int(profile.get("daily_time_minutes") or profile.get("daily_target") or 10)
        vocab_n, quiz_n = (3, 4) if minutes <= 10 else (5, 5) if minutes >= 20 else (4, 4)

        last_plan_obj = get_last_daily_plan(user_id)
        avoid_topic_id = last_plan_obj.get("grammar_topic_id") if last_plan_obj else None

        topic = LearningService.pick_grammar_topic(user_id, level, avoid_topic_id)
        vocab_words = LearningService.select_words_for_topic(level, topic, vocab_n)
        vocab_ids = [w["id"] for w in vocab_words]
        
        practice_ids = LearningService._pick_practice_ids(user_id, level, quiz_n, vocab_ids)
        
        production_mode = "writing" if level in ("A1", "A2") else "speaking" if level == "C1" else ("speaking" if (datetime.date.today().toordinal() + user_id) % 2 else "writing")

        return {
            "level": level,
            "grammar_topic_id": topic.get("id"),
            "vocab_ids": vocab_ids,
            "practice_quiz_ids": practice_ids,
            "production_mode": production_mode,
        }

    @staticmethod
    def pick_grammar_topic(user_id, level, avoid_topic_id=None):
        topics = GrammarService.get_topics_by_level(level)
        if not topics:
            return {"id": None, "title": "Grammatika", "content": "", "example": "-"}
        
        coverage = get_grammar_coverage_map(user_id, level)
        least_seen = sorted(topics, key=lambda t: coverage.get(t.get("id"), 0))
        
        for t in least_seen:
            if t.get("id") != avoid_topic_id:
                return t
        return least_seen[0]

    @staticmethod
    def select_words_for_topic(level, topic, count):
        pool = get_random_words(level, limit=count * 10)
        # Simple scoring based on topic text
        topic_text = f"{topic.get('title','')} {topic.get('content','')}".lower()
        scored = sorted(pool, key=lambda w: (1 if w['de'].lower() in topic_text or w['uz'].lower() in topic_text else 0), reverse=True)
        return scored[:count]

    @staticmethod
    def _pick_practice_ids(user_id, level, count, exclude_ids):
        mistake_ids = get_weighted_mistake_word_ids(user_id, level, limit=10) or []
        picked = [wid for wid in mistake_ids if wid not in exclude_ids][:count]
        if len(picked) < count:
            extra = get_random_words(level, limit=count - len(picked))
            picked.extend([w['id'] for w in extra if w['id'] not in exclude_ids and w['id'] not in picked])
        return picked[:count]
