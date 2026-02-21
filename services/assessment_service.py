import random
from database.repositories.word_repository import get_random_words

class AssessmentService:
    @staticmethod
    def generate_quiz(level: str, length: int = 10):
        # Fetch more words than needed to have distractor pool
        pool_size = min(length * 5, 100)
        word_pool = get_random_words(level, limit=pool_size)
        
        if len(word_pool) < 4:
            return None
            
        questions = []
        # Take first 'length' as correct answers
        correct_pool = word_pool[:length]
        distractor_pool = word_pool[length:] if len(word_pool) > length else word_pool
        
        for correct in correct_pool:
            # Pick 3 distractors
            distractors = random.sample(
                [w for w in distractor_pool if w['id'] != correct['id']], 
                k=min(3, len(distractor_pool)-1)
            )
            
            options = [correct['uz']] + [w['uz'] for w in distractors]
            random.shuffle(options)
            
            questions.append({
                "word_id": correct['id'],
                "de": correct['de'],
                "correct_answer": correct['uz'],
                "options": options
            })
            
        return questions

    @staticmethod
    def validate_answer(correct_answer: str, user_answer: str) -> bool:
        return correct_answer.strip().lower() == user_answer.strip().lower()
