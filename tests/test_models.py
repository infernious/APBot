from datetime import datetime, timezone

from models import Infraction


def test_infraction_defaults_do_not_share_update_lists():
    first = Infraction(
        actiontype="warn",
        reason="Reason",
        moderator=1,
        actiontime=datetime.now(timezone.utc),
        duration=None,
        attachment_url=None,
    )
    second = Infraction(
        actiontype="warn",
        reason="Reason",
        moderator=2,
        actiontime=datetime.now(timezone.utc),
        duration=None,
        attachment_url=None,
    )

    first.update.append({"field": "value"})

    assert second.update == []
    assert first.date is None
