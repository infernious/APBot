from types import SimpleNamespace

import nextcord

from cogs.server_log import ServerLog


def make_cog():
    bot = SimpleNamespace(colors={})
    return ServerLog(bot)


def role(role_id, name):
    return SimpleNamespace(id=role_id, name=name, mention=f"<@&{role_id}>")


def named_item(item_id, name):
    return SimpleNamespace(id=item_id, name=name)


def test_diff_roles_returns_added_and_removed_roles():
    cog = make_cog()
    student = role(1, "Student")
    helper = role(2, "Helper")
    moderator = role(3, "Moderator")

    added, removed = cog.diff_roles([student, helper], [helper, moderator])

    assert added == [moderator]
    assert removed == [student]


def test_format_role_list_omits_everyone_role():
    cog = make_cog()

    result = cog.format_role_list([
        role(1, "@everyone"),
        role(2, "Helper"),
    ])

    assert result == "<@&2> (`2`)"


def test_format_permission_names_lists_high_risk_permissions():
    cog = make_cog()
    permissions = nextcord.Permissions(administrator=True, ban_members=True)

    result = cog.format_permission_names(permissions)

    assert "Administrator" in result
    assert "Ban Members" in result


def test_summarize_named_object_changes_tracks_add_remove_and_rename():
    cog = make_cog()

    added, removed, renamed = cog.summarize_named_object_changes(
        [named_item(1, "old"), named_item(2, "removed")],
        [named_item(1, "new"), named_item(3, "added")],
    )

    assert [item.name for item in added] == ["added"]
    assert [item.name for item in removed] == ["removed"]
    assert [(before.name, after.name) for before, after in renamed] == [("old", "new")]
