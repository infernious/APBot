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

        await inter.response.defer(ephemeral=True)

        try:
            results = await self.bot.db.base_db.delete_all_user_data(target_id)
        except Exception as exc:
            await inter.followup.send(
                f"Data deletion failed: `{type(exc).__name__}`. No completion was certified.",
                ephemeral=True,
            )
            raise

        total_deleted = sum(
            count
            for name, count in results.items()
            if "anonymized" not in name
        )
        total_anonymized = sum(
            count
            for name, count in results.items()
            if "anonymized" in name
        )
        details = "\n".join(
            f"- `{name}`: {count}"
            for name, count in results.items()
            if count
        ) or "- No matching MongoDB records were found."

        embed = nextcord.Embed(
            title="APBot database deletion complete",
            description=(
                f"Deleted MongoDB data linked to user ID `{target_id}`.\n\n"
                f"**Records removed:** {total_deleted}\n"
                f"**Documents with moderator references anonymized:** {total_anonymized}\n\n"
                f"{details}\n\n"
                "This command does not delete Discord channel messages, audit logs, "
                "native bans, timeouts, or roles."
            ),
            color=nextcord.Color.green(),
        )
        await inter.followup.send(embed=embed, ephemeral=True)


def setup(bot: APBot) -> None:
    bot.add_cog(PrivacyCommands(bot))
