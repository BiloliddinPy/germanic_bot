from handlers.daily import _current_time_slot
from handlers.dictionary import _parse_dict_next_callback


def test_parse_dict_next_callback_normal_level():
    parsed = _parse_dict_next_callback("dict_next_A1_20")
    assert parsed == ("A1", 40, None)


def test_parse_dict_next_callback_letter_mode():
    parsed = _parse_dict_next_callback("dict_next_letter_B_A2_20")
    assert parsed == ("A2", 40, "B")


def test_parse_dict_next_callback_rejects_invalid_shapes():
    assert _parse_dict_next_callback("dict_next_letter_B_A2") is None
    assert _parse_dict_next_callback("dict_next_A1_x") is None
    assert _parse_dict_next_callback("dict_prev_A1_0") is None


def test_current_time_slot_format():
    slot = _current_time_slot()
    assert len(slot) == 5
    assert slot[2:] == ":00"
    hour = int(slot[:2])
    assert 0 <= hour <= 23
