"""Evidence role access must not alter moderation immunity."""
from types import SimpleNamespace as NS
import pytest
from test_scam_image_detector import harness, Role
from cogs import scam_image_detector as cog

@pytest.mark.parametrize("name", ["Bot Staff", "Senior Bot Staff", "bOt StAfF"])
def test_bot_staff_may_view_evidence(harness, name):
    detector, message, _, review, _ = harness
    guild = message.guild
    role = Role(42, name)
    guild.roles.append(role)
    review.permissions_for = lambda who: NS(view_channel=who is guild.me or who is role, send_messages=True, embed_links=True, attach_files=True)
    assert detector.private_review(guild) is review
    message.author.roles = [role]
    assert cog.review_staff(message.author)
    assert not cog.staff(message.author)
    review.overwrites = {message.author: NS(view_channel=True)}
    assert detector.private_review(guild) is review

@pytest.mark.parametrize("name", ["Bot Staff Fan", "Senior Bot Staff Club", "Member"])
def test_other_roles_still_block_evidence(harness, name):
    detector, message, _, review, _ = harness
    guild = message.guild
    role = Role(42, name)
    guild.roles.append(role)
    review.permissions_for = lambda who: NS(view_channel=who is guild.me or who is role, send_messages=True, embed_links=True, attach_files=True)
    assert detector.private_review(guild) is None
    message.author.roles = [role]
    assert not cog.review_staff(message.author)
    review.permissions_for = lambda who: NS(view_channel=who is guild.me, send_messages=True, embed_links=True, attach_files=True)
    review.overwrites = {message.author: NS(view_channel=True)}
    assert detector.private_review(guild) is None

def test_everyone_access_still_blocks(harness):
    detector, message, _, review, _ = harness
    review.permissions_for = lambda who: NS(view_channel=True, send_messages=True, embed_links=True, attach_files=True)
    assert detector.private_review(message.guild) is None
