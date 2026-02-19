import json
import os
from database.repositories.progress_repository import mark_grammar_topic_seen, update_module_progress, log_event
from database.repositories.stats_repository import get_recent_topic_mistake_scores # Need to create stats_repository

class GrammarService:
    DATA_DIR = "data"

    @staticmethod
    def load_grammar():
        file_path = f"{GrammarService.DATA_DIR}/grammar.json"
        if not os.path.exists(file_path):
            return {}
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def get_topics_by_level(level: str):
        data = GrammarService.load_grammar()
        return data.get(level, [])

    @staticmethod
    def get_topic_by_id(topic_id: str):
        data = GrammarService.load_grammar()
        for level, topics in data.items():
            for topic in topics:
                if topic.get("id") == topic_id:
                    return topic, level
        return None, None

    @staticmethod
    def mark_completed(user_id: int, topic_id: str, level: str):
        mark_grammar_topic_seen(user_id, topic_id, level)
        update_module_progress(user_id, "grammar", level, completed=True)
        log_event(user_id, "grammar_topic_opened", section_name="grammar", level=level, metadata={"topic_id": topic_id})

    @staticmethod
    def get_recommendation(user_id: int, level: str):
        # This needs the stats repository which I'll merge into progress/stats
        from database.repositories.progress_repository import get_recent_topic_mistake_scores
        try:
            weak_topics = get_recent_topic_mistake_scores(user_id, level, days=14, limit=1)
            if weak_topics:
                topic_id = weak_topics[0][0]
                topics = GrammarService.get_topics_by_level(level)
                for t in topics:
                    if t.get("id") == topic_id:
                        return t
        except Exception:
            pass
        return None
