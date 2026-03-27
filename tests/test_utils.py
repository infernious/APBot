from cogs.utils import convert_time


def test_convert_time_combines_multiple_units():
    assert convert_time("1h30m15s") == 5415


def test_convert_time_supports_weeks():
    assert convert_time("2w") == 1209600


def test_convert_time_rejects_invalid_unit():
    assert convert_time("5x") == "x is an invalid time-key! s/sec/m/min/h/hour/d/day are valid!"


def test_convert_time_rejects_empty_duration():
    assert convert_time("") == " is not a valid duration!"
