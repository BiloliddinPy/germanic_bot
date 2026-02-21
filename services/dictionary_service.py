from database.repositories.word_repository import (
    get_words_by_level, 
    get_words_by_level_and_letter,
    get_total_words_count,
    get_total_words_count_by_letter
)
from core.config import settings

class DictionaryService:
    @staticmethod
    def get_page(level: str, offset: int = 0, letter: str | None = None):
        limit = settings.page_size
        
        if letter:
            words = get_words_by_level_and_letter(level, letter, limit=limit, offset=offset)
            total = get_total_words_count_by_letter(level, letter)
        else:
            words = get_words_by_level(level, limit=limit, offset=offset)
            total = get_total_words_count(level)
            
        has_next = (offset + limit) < total
        return {
            "words": words,
            "total": total,
            "has_next": has_next,
            "limit": limit
        }

    @staticmethod
    def get_alphabet():
        return list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
