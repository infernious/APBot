import asyncio
from types import SimpleNamespace

from cogs.wordle import (
    Wordle,
    date_in_season,
    format_wordle_leaderboard,
    is_wordle_summary_message,
    parse_date,
    parse_wordle_result,
    parse_wordle_summary_text,
    wordle_score,
)


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


def test_parse_wordle_summary_text():
    text = "Here are yesterday's results:\n3/6*: <@111>\n4/6 — <@222>, <@!333>\nX/6 <@444>"

    results = parse_wordle_summary_text(text)

    assert results[0]["user_id"] == 111
    assert results[0]["tries"] == 3
    assert results[0]["hard_mode"] is True
    assert results[0]["score"] == 2
    assert results[1]["user_id"] == 222
    assert results[1]["tries"] == 4
    assert results[1]["hard_mode"] is False
    assert results[1]["score"] == 4
    assert results[2]["user_id"] == 333
    assert results[3]["user_id"] == 444
    assert results[3]["failed"] is True
    assert results[3]["score"] == 7


def test_is_wordle_summary_message():
    assert is_wordle_summary_message("Your group is on a 7 day streak. Here are yesterday's results") is True
    assert is_wordle_summary_message("3/6: <@111>") is True
    assert is_wordle_summary_message("push was playing\n1 finished game of Wordle") is True
    assert is_wordle_summary_message("hello") is False


def test_wordle_score():
    assert wordle_score(3, False, False) == 3
    assert wordle_score(3, False, True) == 2
    assert wordle_score(None, True, False) == 7


def test_date_in_season():
    season = {"start_date": "2026-05-01", "end_date": "2026-05-31"}

    assert date_in_season("2026-05-01", season) is True
    assert date_in_season("2026-05-31", season) is True
    assert date_in_season("2026-06-01", season) is False


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


def test_resolve_username_fetches_member_when_not_cached():
    class FakeGuild:
        def get_member(self, user_id):
            return None

        async def fetch_member(self, user_id):
            return SimpleNamespace(display_name="Fetched Name")

    cog = Wordle(bot=object())

    assert asyncio.run(cog.resolve_username(FakeGuild(), 123)) == "Fetched Name"
