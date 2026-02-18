import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database
from handlers import daily_lesson


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    test_user = 909002
    database.create_table()

    # 1) Core plan structure stays valid and material lookup works
    for level in ["A1", "A2", "B1", "B2", "C1"]:
        plan = daily_lesson.build_daily_plan(test_user, {"current_level": level, "daily_target": 20})
        assert_true(daily_lesson.is_core_daily_plan(plan), f"{level}: invalid core plan")

        material = daily_lesson.get_material_by_id(plan.get("material_id"))
        assert_true(material is not None, f"{level}: material lookup failed")
        assert_true(bool(material.get("path")), f"{level}: material path missing")

        vocab_n = len(plan.get("vocab_ids", []))
        quiz_n = len(plan.get("practice_quiz_ids", []))
        assert_true(5 <= vocab_n <= 7, f"{level}: vocab count out of bounds ({vocab_n})")
        assert_true(3 <= quiz_n <= 5, f"{level}: quiz count out of bounds ({quiz_n})")

    # 2) Quiz counter helper regression
    session = {"quiz_correct": 0, "quiz_wrong": 0}
    daily_lesson.apply_quiz_result_to_session(session, True)
    daily_lesson.apply_quiz_result_to_session(session, False)
    daily_lesson.apply_quiz_result_to_session(session, False)
    assert_true(session["quiz_correct"] == 1, "quiz_correct counter broken")
    assert_true(session["quiz_wrong"] == 2, "quiz_wrong counter broken")

    # 3) Callback parser guard
    assert_true(
        daily_lesson.parse_indexed_callback("daily_quiz_5_2", "daily_quiz_", 2) == (5, 2),
        "daily quiz callback parser failed"
    )
    assert_true(
        daily_lesson.parse_indexed_callback("daily_quiz_5_bad", "daily_quiz_", 2) is None,
        "daily quiz callback parser should reject malformed payload"
    )
    assert_true(
        daily_lesson.parse_indexed_callback("review_ans_7_1", "review_ans_", 2) == (7, 1),
        "review callback parser failed"
    )

    # 4) Material lookup unknown id
    assert_true(daily_lesson.get_material_by_id("unknown") is None, "unknown material should be None")

    print("OK: Daily Lesson smoke checks passed.")


if __name__ == "__main__":
    main()
