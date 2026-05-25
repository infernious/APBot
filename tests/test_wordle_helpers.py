from cogs.wordle import format_wordle_leaderboard, is_wordle_summary_message, parse_date, parse_wordle_result


def test_parse_wordle_result_normal():
    result = parse_wordle_result("Wordle 1801 4/6")

    assert result["puzzle"] == 1801
    assert result["tries"] == 4
    assert result["failed"] is False
    assert result["hard_mode"] is False
    assert result["score"] == 4


def test_parse_wordle_result_hard_mode_with_comma():
    result = parse_wordle_result("Wordle 1,800 3/6*")

    assert result["puzzle"] == 1800
    assert result["tries"] == 3
    assert result["failed"] is False
    assert result["hard_mode"] is True
    assert result["score"] == 2


def test_parse_wordle_result_failed():
    result = parse_wordle_result("Wordle 1801 X/6")

    assert result["puzzle"] == 1801
    assert result["tries"] is None
    assert result["failed"] is True
    assert result["hard_mode"] is False
    assert result["score"] == 7


def test_parse_wordle_result_invalid():
    assert parse_wordle_result("push was playing") is None


def test_is_wordle_summary_message():
    assert is_wordle_summary_message("Your group is on a 7 day streak. Here are yesterday's results") is True
    assert is_wordle_summary_message("push was playing") is False


def test_parse_date():
    assert parse_date("2026-05-25").isoformat() == "2026-05-25"
    assert parse_date("05/25/2026") is None


def test_format_wordle_leaderboard():
    rows = [
        {"user_id": 1, "total_score": 6, "games": 2, "hard_games": 1, "failures": 0},
        {"user_id": 2, "total_score": 7, "games": 1, "hard_games": 0, "failures": 1},
    ]

    text = format_wordle_leaderboard(rows)

    assert "<@1>" in text
    assert "6 pts" in text
    assert "<@2>" in text
    assert "failed" in text
