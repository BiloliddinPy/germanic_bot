import datetime

from handlers.daily import _current_time_slot, _daily_slot_key, _retry_delay_seconds
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


def test_daily_slot_key_format():
    key = _daily_slot_key(datetime.datetime(2026, 2, 21, 10, 35))
    assert key == "2026-02-21_10:00"


def test_retry_delay_seconds_growth_and_cap():
    assert _retry_delay_seconds(0) == 15
    assert _retry_delay_seconds(1) == 30
    assert _retry_delay_seconds(2) == 60
    assert _retry_delay_seconds(10) == 900
