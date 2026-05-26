import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from cogs.helper_dm import HelperDMCog, HELPER_DM_MESSAGE


def role(role_id, name):
    return SimpleNamespace(id=role_id, name=name)


def member(roles, bot=False):
    return SimpleNamespace(roles=roles, bot=bot, send=AsyncMock())


def test_gained_helper_role_detects_new_helper_role():
    cog = HelperDMCog(bot=object())

    before = member([role(1, "Student")])
    after = member([role(1, "Student"), role(2, "Helper (Click on their names!)")])

    assert cog.gained_helper_role(before, after) is True


def test_gained_helper_role_ignores_existing_helper_role():
    cog = HelperDMCog(bot=object())

    before = member([role(2, "Helper (Click on their names!)")])
    after = member([role(2, "Helper (Click on their names!)")])

    assert cog.gained_helper_role(before, after) is False


def test_on_member_update_dms_new_helper():
    cog = HelperDMCog(bot=object())

    before = member([role(1, "Student")])
    after = member([role(1, "Student"), role(2, "Helper (Click on their names!)")])

    asyncio.run(cog.on_member_update(before, after))

    after.send.assert_awaited_once_with(HELPER_DM_MESSAGE)


def test_on_member_update_does_not_dm_bots():
    cog = HelperDMCog(bot=object())

    before = member([role(1, "Student")])
    after = member([role(1, "Student"), role(2, "Helper (Click on their names!)")], bot=True)

    asyncio.run(cog.on_member_update(before, after))

    after.send.assert_not_awaited()
