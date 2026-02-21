import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import create_table
from database.repositories.lesson_repository import get_last_daily_plan, save_daily_plan
from database.repositories.progress_repository import log_mistake, update_module_progress
from database.repositories.session_repository import (
    delete_daily_lesson_state,
    get_daily_lesson_state,
    save_daily_lesson_state,
)
from database.connection import get_connection
from services.learning_service import LearningService


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    test_user = 909001
    create_table()

    levels = ["A1", "A2", "B1", "B2", "C1"]
    for level in levels:
        plan = LearningService.create_daily_plan(
            test_user,
            {"current_level": level, "daily_time_minutes": 20},
        )
        assert_true(plan.get("level") == level, f"{level}: plan level mismatch")
        assert_true(isinstance(plan.get("vocab_ids"), list), f"{level}: vocab_ids missing")
        assert_true(isinstance(plan.get("practice_quiz_ids"), list), f"{level}: practice_quiz_ids missing")
        assert_true("grammar_topic_id" in plan, f"{level}: grammar_topic_id missing")
        save_daily_plan(test_user, plan)

    latest_plan = get_last_daily_plan(test_user)
    assert_true(isinstance(latest_plan, dict), "Latest daily plan not returned")
    assert_true(latest_plan.get("level") in levels, "Latest plan has invalid level")

    state = {"status": "in_progress", "step": 2, "results": {"quiz_correct": 1, "quiz_total": 2}}
    save_daily_lesson_state(test_user, state)
    loaded = get_daily_lesson_state(test_user)
    assert_true(isinstance(loaded, dict), "Daily lesson state not found")
    assert_true(int(loaded.get("step", 0)) == 2, "Daily lesson state mismatch")

    update_module_progress(test_user, "daily_lesson", "A1", completed=False)
    update_module_progress(test_user, "daily_lesson", "A1", completed=True)
    log_mistake(test_user, "smoke_word_1", "quiz_test", "vocab")
    log_mistake(test_user, "smoke_word_1", "quiz_test", "vocab")

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT completion_status
        FROM user_progress
        WHERE user_id = ? AND module_name = 'daily_lesson' AND level = 'A1'
        """,
        (test_user,),
    )
    progress_row = cur.fetchone()
    assert_true(progress_row is not None, "user_progress row missing")
    assert_true(int(progress_row[0] or 0) == 1, "user_progress completion_status should be 1")

    cur.execute(
        """
        SELECT mistake_count
        FROM user_mistakes
        WHERE user_id = ? AND item_id = ? AND module = ?
        """,
        (test_user, "smoke_word_1", "quiz_test"),
    )
    mistake_row = cur.fetchone()
    assert_true(mistake_row is not None, "user_mistakes row missing")
    assert_true(int(mistake_row[0] or 0) >= 2, "mistake_count should be >= 2")

    cur.execute("DELETE FROM daily_plans WHERE user_id = ?", (test_user,))
    cur.execute("DELETE FROM user_progress WHERE user_id = ?", (test_user,))
    cur.execute("DELETE FROM user_mistakes WHERE user_id = ?", (test_user,))
    cur.execute("DELETE FROM daily_lesson_sessions WHERE user_id = ?", (test_user,))
    conn.commit()
    conn.close()

    delete_daily_lesson_state(test_user)
    print("OK: Day 7 smoke checks passed.")


if __name__ == "__main__":
    main()
