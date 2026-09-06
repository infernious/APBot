import nextcord
from nextcord import Interaction, SlashOption, slash_command
from nextcord.ext import commands

from app_config import get_command_guild_ids, load_optional_config
from bot_base import APBot


conf = load_optional_config()
COMMAND_GUILD_IDS = get_command_guild_ids(conf)
ALLOWED_ROLE_NAMES = {"Chat Moderator", "Admin"}


def has_data_deletion_role(member) -> bool:
    return bool(
        member
        and any(
            getattr(role, "name", None) in ALLOWED_ROLE_NAMES
            for role in getattr(member, "roles", [])
        )
    )


def parse_discord_user_id(value: str) -> int | None:
    value = str(value or "").strip()

    if not value.isdigit() or not 17 <= len(value) <= 20:
        return None

    return int(value)


class PrivacyCommands(commands.Cog):
    def __init__(self, bot: APBot) -> None:
        self.bot = bot

    @slash_command(
        name="deleteuserdata",
        description="Permanently delete a user's data from APBot's MongoDB database.",
        guild_ids=COMMAND_GUILD_IDS,
    )
    async def delete_user_data(
        self,
        inter: Interaction,
        user_id: str = SlashOption(
            description="Discord user ID whose APBot database data will be deleted",
            required=True,
        ),
        confirmation: str = SlashOption(
            description="Type DELETE to confirm this permanent action",
            required=True,
        ),
    ):
        if inter.guild is None or not has_data_deletion_role(inter.user):
            await inter.response.send_message(
                "You need the **Chat Moderator** or **Admin** role to use this command.",
                ephemeral=True,
            )
            return

        target_id = parse_discord_user_id(user_id)

        if target_id is None:
            await inter.response.send_message(
                "Enter a valid 17-20 digit Discord user ID.",
                ephemeral=True,
            )
            return

        if confirmation != "DELETE":
            await inter.response.send_message(
                "Deletion cancelled. Enter `DELETE` exactly in the confirmation field.",
                ephemeral=True,
            )
            return

        # No ephemeral=True, so the result will be visible to everyone.
        await inter.response.defer()

        try:
            await self.bot.db.base_db.delete_all_user_data(target_id)
        except Exception as exc:
            print(
                f"Failed to delete user data for {target_id}: "
                f"{type(exc).__name__}: {exc}"
            )
            await inter.followup.send(
                "Failed to delete the user's data. Check the console for the error."
            )
            return

        embed = nextcord.Embed(
            title="APBot database deletion complete",
            description=(
                f"Deleted MongoDB data linked to user ID `{target_id}`."
            ),
            color=nextcord.Color.green(),
        )

        # No ephemeral=True, so everyone can see this embed.
        await inter.followup.send(embed=embed)


def setup(bot: APBot) -> None:
    bot.add_cog(PrivacyCommands(bot))
