import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

from cogs.wordle import (
    Wordle,
    date_in_season,
    format_wordle_leaderboard,
    is_wordle_bot_author,
    is_wordle_summary_message,
    parse_date,
    parse_wordle_puzzle,
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


def test_parse_wordle_puzzle():
    assert parse_wordle_puzzle("Wordle 1,800\nHere are yesterday's results") == 1800
    assert parse_wordle_puzzle("Here are yesterday's results") is None


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


def test_is_wordle_bot_author_uses_bot_name():
    assert is_wordle_bot_author(SimpleNamespace(bot=True, name="Wordle")) is True
    assert is_wordle_bot_author(SimpleNamespace(bot=True, name="APBot")) is False
    assert is_wordle_bot_author(SimpleNamespace(bot=False, name="Wordle")) is False


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


def test_process_wordle_result_message_ignores_member_share():
    wordle_db = SimpleNamespace(
        get_active_season=AsyncMock(return_value={"start_date": "2026-05-25", "end_date": "2026-05-25"}),
        save_result=AsyncMock(),
    )
    bot = SimpleNamespace(db=SimpleNamespace(wordle=wordle_db))
    cog = Wordle(bot=bot)
    message = SimpleNamespace(
        guild=SimpleNamespace(id=1),
        author=SimpleNamespace(bot=False, id=111, display_name="Player"),
        channel=SimpleNamespace(id=10, name="wordle"),
        content="Wordle 1,800 3/6*",
        created_at=datetime(2026, 5, 25, tzinfo=timezone.utc),
        id=55,
    )

    processed = asyncio.run(cog.process_wordle_result_message(message))

    assert processed is False
    wordle_db.save_result.assert_not_awaited()


def test_process_wordle_summary_requires_wordle_bot():
    wordle_db = SimpleNamespace(
        get_active_season=AsyncMock(return_value={"start_date": "2026-05-25", "end_date": "2026-05-25"}),
        save_result=AsyncMock(),
    )
    bot = SimpleNamespace(db=SimpleNamespace(wordle=wordle_db))
    cog = Wordle(bot=bot)
    message = SimpleNamespace(
        guild=SimpleNamespace(id=1),
        author=SimpleNamespace(bot=True, name="APBot", display_name="APBot"),
        channel=SimpleNamespace(id=10, name="wordle"),
        content="Wordle 1,800\nHere are yesterday's results:\n3/6*: <@111>",
        embeds=[],
        created_at=datetime(2026, 5, 26, tzinfo=timezone.utc),
        id=56,
    )

    processed = asyncio.run(cog.process_wordle_summary_message(message))

    assert processed == 0
    wordle_db.save_result.assert_not_awaited()


def test_process_wordle_summary_records_puzzle_from_wordle_bot():
    guild = SimpleNamespace(
        id=1,
        get_member=lambda user_id: SimpleNamespace(display_name="Player"),
    )
    wordle_db = SimpleNamespace(
        get_active_season=AsyncMock(return_value={"start_date": "2026-05-25", "end_date": "2026-05-25"}),
        save_result=AsyncMock(),
    )
    bot = SimpleNamespace(db=SimpleNamespace(wordle=wordle_db))
    cog = Wordle(bot=bot)
    message = SimpleNamespace(
        guild=guild,
        author=SimpleNamespace(bot=True, name="Wordle", display_name="Wordle"),
        channel=SimpleNamespace(id=10, name="wordle"),
        content="Wordle 1,800\nHere are yesterday's results:\n3/6*: <@111>",
        embeds=[],
        created_at=datetime(2026, 5, 26, tzinfo=timezone.utc),
        id=57,
    )

    processed = asyncio.run(cog.process_wordle_summary_message(message))

    assert processed == 1
    kwargs = wordle_db.save_result.await_args.kwargs
    assert kwargs["user_id"] == 111
    assert kwargs["username"] == "Player"
    assert kwargs["puzzle"] == 1800
    assert kwargs["hard_mode"] is True
    assert kwargs["score"] == 2
    assert kwargs["played_date"] == "2026-05-25"
    assert kwargs["source"] == "wordle_bot_summary"
