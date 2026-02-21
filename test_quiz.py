from services.assessment_service import AssessmentService


def test_generate_quiz_returns_expected_count_and_options(monkeypatch):
    fake_pool = [
        {"id": 1, "de": "Haus", "uz": "uy"},
        {"id": 2, "de": "Baum", "uz": "daraxt"},
        {"id": 3, "de": "Buch", "uz": "kitob"},
        {"id": 4, "de": "Auto", "uz": "mashina"},
        {"id": 5, "de": "Stadt", "uz": "shahar"},
        {"id": 6, "de": "Wasser", "uz": "suv"},
        {"id": 7, "de": "Brot", "uz": "non"},
        {"id": 8, "de": "Tag", "uz": "kun"},
    ]

    monkeypatch.setattr("services.assessment_service.get_random_words", lambda level, limit: fake_pool[:limit])
    questions = AssessmentService.generate_quiz("A1", length=3)

    assert questions is not None
    assert len(questions) == 3
    for q in questions:
        assert "correct_answer" in q
        assert q["correct_answer"] in q["options"]
        assert len(q["options"]) >= 2


def test_generate_quiz_returns_none_when_pool_too_small(monkeypatch):
    monkeypatch.setattr(
        "services.assessment_service.get_random_words",
        lambda level, limit: [{"id": 1, "de": "Haus", "uz": "uy"}],
    )
    assert AssessmentService.generate_quiz("A1", length=10) is None


def test_validate_answer_case_insensitive():
    assert AssessmentService.validate_answer("Kitob", "kitob")
    assert not AssessmentService.validate_answer("kitob", "daftar")
