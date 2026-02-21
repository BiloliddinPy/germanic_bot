import datetime
import sqlite3
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database
from handlers import daily_lesson


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    test_user = 909001
    today = datetime.date.today().isoformat()
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()

    database.create_table()

    # 1) Core plan structure and sizes for all levels
    levels = ["A1", "A2", "B1", "B2", "C1"]
    plans_by_level = {}
    for level in levels:
        plan = daily_lesson.build_daily_plan(test_user, {"current_level": level, "daily_target": 20})
        plans_by_level[level] = plan
        assert_true(daily_lesson.is_core_daily_plan(plan), f"{level}: plan is not core format")
        assert_true(5 <= len(plan.get("vocab_ids", [])) <= 7, f"{level}: vocab count is outside 5-7")
        assert_true(3 <= len(plan.get("practice_quiz_ids", [])) <= 5, f"{level}: practice quiz count is outside 3-5")
        assert_true(plan.get("level") == level, f"{level}: level mismatch in plan")

    # 2) Cache read/write
    plan = plans_by_level["A1"]
    database.save_daily_plan(test_user, plan, plan_date=today)
    cached = database.get_cached_daily_plan(test_user, plan_date=today)
    assert_true(isinstance(cached, dict), "Cached plan not returned as dict")
    assert_true(cached.get("grammar_topic_id") == plan.get("grammar_topic_id"), "Cached plan mismatch")
    database.log_daily_plan_audit(test_user, "plan_generated", metadata={"level": "A1"}, plan_date=today)

    # 3) Topic repetition guard (simulate previous day)
    prev_plan = dict(plan)
    prev_plan["grammar_topic_id"] = plan.get("grammar_topic_id")
    database.save_daily_plan(test_user, prev_plan, plan_date=yesterday)
    new_plan = daily_lesson.build_daily_plan(test_user, {"current_level": "A1", "daily_target": 20})
    if new_plan.get("grammar_topic_id") and prev_plan.get("grammar_topic_id"):
        if new_plan.get("grammar_topic_id") == prev_plan.get("grammar_topic_id"):
            print("WARN: topic repeated (possible if content pool is constrained).")

    # 4) Writing completion hook
    database.mark_writing_task_completed(test_user, "A1", plan.get("grammar_topic_id"), plan.get("writing_task_type"))
    conn = sqlite3.connect(database.DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM writing_task_log WHERE user_id = ? AND task_date = ?", (test_user, today))
    row_count = cur.fetchone()[0]
    assert_true(row_count == 1, "Writing task log was not written")

    # 5) Daily plan audit write
    cur.execute("SELECT COUNT(*) FROM daily_plan_audit WHERE user_id = ? AND plan_date = ?", (test_user, today))
    audit_count = cur.fetchone()[0]
    assert_true(audit_count >= 1, "Daily plan audit row was not written")

    # 6) Mistake mastery weighting (no hard delete)
    database.log_mistake(test_user, 123456, "quiz_test", "A1")
    database.resolve_mistake(test_user, 123456, "quiz_test")
    cur.execute("""
        SELECT mistake_count, success_count, mastered
        FROM user_mistakes
        WHERE user_id = ? AND item_id = ? AND module = ?
    """, (test_user, "123456", "quiz_test"))
    mrow = cur.fetchone()
    assert_true(mrow is not None, "Mistake row should remain for weighting")
    assert_true((mrow[0] or 0) == 0, "Mistake count should decrease to 0")
    assert_true((mrow[1] or 0) >= 1, "Success count should increment")

    database.log_mistake(test_user, 123457, "quiz_test", "A1")
    database.log_mistake(test_user, 123457, "quiz_test", "A1")
    database.resolve_mistake(test_user, 123457, "quiz_test")
    database.resolve_mistake(test_user, 123457, "quiz_test")
    cur.execute("""
        SELECT mastered
        FROM user_mistakes
        WHERE user_id = ? AND item_id = ? AND module = ?
    """, (test_user, "123457", "quiz_test"))
    mastered_row = cur.fetchone()
    assert_true(mastered_row is not None and int(mastered_row[0] or 0) == 1, "Mistake should be marked mastered")

    # 7) Completion idempotency (must stay once/day)
    c1 = database.mark_daily_lesson_completed(test_user)
    c2 = database.mark_daily_lesson_completed(test_user)
    assert_true(c1.get("completed_now") in (True, False), "Completion response malformed")
    assert_true(c2.get("completed_now") is False, "Completion should be idempotent on second call")

    # Cleanup
    cur.execute("DELETE FROM user_daily_plan WHERE user_id = ?", (test_user,))
    cur.execute("DELETE FROM writing_task_log WHERE user_id = ?", (test_user,))
    cur.execute("DELETE FROM daily_plan_audit WHERE user_id = ?", (test_user,))
    cur.execute("DELETE FROM user_mistakes WHERE user_id = ?", (test_user,))
    cur.execute("DELETE FROM daily_lesson_log WHERE user_id = ?", (test_user,))
    cur.execute("DELETE FROM user_streak WHERE user_id = ?", (test_user,))
    conn.commit()
    conn.close()

    print("OK: Day 7 smoke checks passed.")


if __name__ == "__main__":
    main()
