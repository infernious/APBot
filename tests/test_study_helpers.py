import asyncio

from cogs.study import MAX_STUDY_SECONDS, MIN_STUDY_SECONDS, get_study_delay_seconds, send_study_role_dm, validate_study_duration


class FakeMember:
    def __init__(self):
        self.sent = None

    async def send(self, content):
        self.sent = content


def test_validate_study_duration_accepts_bounds():
    assert validate_study_duration("10m") == (MIN_STUDY_SECONDS, None)
    assert validate_study_duration("168h") == (MAX_STUDY_SECONDS, None)
    assert validate_study_duration("1w") == (MAX_STUDY_SECONDS, None)


def test_validate_study_duration_rejects_out_of_range():
    assert validate_study_duration("9m")[0] is None
    assert validate_study_duration("169h")[0] is None


def test_send_study_role_dm_sends_message():
    member = FakeMember()

    result = asyncio.run(send_study_role_dm(member, 1234567890))

    assert result is True
    assert "Study Mode" in member.sent
    assert "<t:1234567890:R>" in member.sent


def test_get_study_delay_seconds():
    assert get_study_delay_seconds(1000, now=900) == 100
    assert get_study_delay_seconds(1000, now=1000) == 0
    assert get_study_delay_seconds(1000, now=1100) == 0
