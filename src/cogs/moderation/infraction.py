import nextcord
import re
from nextcord import slash_command, Permissions, Interaction, User, Embed, Member, TextChannel, Object, Color
from nextcord.ext import commands
from typing import Optional
from bot_base import APBot
from app_config import get_command_guild_ids, load_optional_config
from datetime import datetime, timedelta
from datetime import timezone

conf = load_optional_config()
COMMAND_GUILD_IDS = get_command_guild_ids(conf)


def to_snowflake(value):
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        m = re.search(r"\d{17,20}", value)
        if m:
            return int(m.group(0))
    return None

class Infraction(commands.Cog):
    def __init__(self, bot: APBot) -> None:
        self.bot = bot

    def has_mod_role(self, member: Member) -> bool:
        allowed_roles = {"Trial Chat Moderator", "Chat Moderator", "Admin"}
        return any(role.name in allowed_roles for role in member.roles)

    @slash_command(
        name="warnings",
        description="Show infraction history of a member.",
        guild_ids=COMMAND_GUILD_IDS,
        default_member_permissions=Permissions(moderate_members=True),
    )
    async def warnings(self, inter: Interaction, member: Member):
        if not self.has_mod_role(inter.user):
            await inter.response.send_message(
                "You do not have permission to use this command.", ephemeral=True
            )
            return

        await inter.response.defer(with_message=False)

        infractions = await self.bot.db.base_db.get_user_infractions(member.id)
        inf_points = await self.bot.db.base_db.add_inf_points(member.id, 0)

        if not infractions:
            await inter.followup.send(f"{member.mention} has no infractions.")
            return

        fetching_msg = await inter.channel.send(f"Fetching {member.mention}'s warnings...")

        color_map = {
            "warn": self.bot.colors.get("yellow", Color.yellow()),
            "mute": self.bot.colors.get("orange", Color.orange()),
            "pseudo-mute": self.bot.colors.get("light_orange", Color.orange()),
            "kick": self.bot.colors.get("dark_orange", Color.orange()),
            "ban": self.bot.colors.get("red", Color.red()),
            "force-ban": self.bot.colors.get("red", Color.red()),
            "unmute": self.bot.colors.get("green", Color.green()),
            "unban": self.bot.colors.get("green", Color.green()),
            "note": Color.purple()
        }

        total = len(infractions)

        for index, inf in enumerate(infractions, start=1):
            action = (
                    "Internal Note"
                    if inf.actiontype == "note"
                    else (inf.actiontype or "unknown").capitalize().replace("-", " ")
                )
            reason = inf.reason or "No reason provided"

            # ---- Moderator lookup (fixed) ----
            raw_mod = getattr(inf, "moderator", None)
            moderator_id = to_snowflake(raw_mod)

            mod = None
            if moderator_id:
                # Try guild cache first (only if in a guild)
                if inter.guild is not None:
                    mod = inter.guild.get_member(moderator_id)

                # Fallback to API fetch
                if mod is None:
                    try:
                        mod = await self.bot.fetch_user(moderator_id)
                    except nextcord.HTTPException:
                        mod = None

            # Build moderator display:
            # - If we found the user => mention + display name
            # - If not => still mention the ID if we have one, else show whatever was stored
            if mod:
                display = getattr(mod, "global_name", None) or mod.name
                mod_line = f"{mod.mention} ({display})"
            else:
                if moderator_id:
                    mod_line = f"<@{moderator_id}> (unknown)"
                else:
                    mod_line = f"{raw_mod} (unknown)" if raw_mod else "Unknown moderator"
            # -------------------------------



            time_val = getattr(inf, "actiontime", None)

            # if DB accidentally returned a string sometimes, parse it
            if isinstance(time_val, str):
                try:
                    time_val = datetime.fromisoformat(time_val)
                except ValueError:
                    time_val = datetime.now(timezone.utc)

            if not isinstance(time_val, datetime):
                time_val = datetime.now(timezone.utc)

            # if naive, assume UTC
            if time_val.tzinfo is None:
                time_val = time_val.replace(tzinfo=timezone.utc)

            unix = int(time_val.timestamp())
            timestamp = f"<t:{unix}:F> (<t:{unix}:R>)"


            # ---- Duration ----
            duration_line = ""
            if getattr(inf, "duration", None):
                try:
                    dur = inf.duration
                    duration_seconds = (
                        int(dur.total_seconds()) if isinstance(dur, timedelta) else int(dur)
                    )
                    hours = duration_seconds // 3600
                    duration_line = f"Duration: {hours}h\n"
                except (ValueError, TypeError, AttributeError):
                    pass

            embed = Embed(
                title=action,
                description=(
                    f"Reason: {reason}\n"
                    f"{duration_line}"
                    f"Responsible Mod: {mod_line}\n"
                    f"{index}/{total} infractions • {timestamp}"
                ),
                color=color_map.get(getattr(inf, "actiontype", ""), Color.gold()),
            )


            await inter.channel.send(embed=embed)

        await fetching_msg.reply(
            f"Complete, all infractions shown! {member.mention} has `{inf_points}` infraction point(s)."
        )
        
    @slash_command(
        name="editip",
        description="Edit a member's infraction points.",
        default_member_permissions=Permissions(moderate_members=True),
        guild_ids=COMMAND_GUILD_IDS
    )
    async def editip(self, interaction: Interaction, member: Member, change: int):
        if not self.has_mod_role(interaction.user):
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return

        new_inf_points = await self.bot.db.base_db.add_inf_points(member.id, change)

        await interaction.response.send_message(
            f"Added {change} to {member.mention}'s infraction points, they now have {new_inf_points} total."
        )

        if new_inf_points < 30:
            return

        ch: Optional[TextChannel] = await self.bot.getch_channel(self.bot.config.get("ban_review_channel-id"))
        if ch:
            await ch.send(
                content=f"<@&{self.bot.config.get('mod_role_id')}>",
                embed=Embed(
                    title="Member has reached 30 inf points",
                    description=f"{member.mention} has {new_inf_points} IPs and should be reviewed for a ban.",
                    color=self.bot.colors.get("red")
                )
            )

        updates_channel = nextcord.utils.get(interaction.guild.text_channels, name="important-updates")
        if updates_channel:
            mod_role = nextcord.utils.get(interaction.guild.roles, name="Chat Moderator")
            await updates_channel.send(
                content=mod_role.mention if mod_role else None,
                embed=Embed(
                    title="Member has reached 30 infraction points!",
                    description=f"{member.mention} has `{new_inf_points}` infraction points and should be reviewed for a ban.",
                    color=self.bot.colors.get("red")
                )
            )

# Work on later
#    @slash_command(name="update", description="Update a member's infraction history.", default_member_permissions=Permissions(moderate_members=True))
#    async def update(self, interaction: Interaction, user:  User, infraction: int, update: str):
#        member_config = await self.bot.db.base_db.read_user_config(user.id)
#        infractions = member_config["infractions"]
#        infraction_update = infractions[infraction]

#        if infraction_update.get('update') is None:
#            infraction_update['update'] = []

#        update_dict = {
#            "moderator": interaction.user.mention,
#            "update": update,
#            "date": datetime.utcnow()
#        }

#        infraction_update['update'].append(update_dict)

#        await self.bot.db.base_db.update_user_config(user.id, member_config)  # Save changes

#        await interaction.response.send_message("Infraction updated successfully.", ephemeral=True)

    @slash_command(name="userip", description="View a member's infraction points.", default_member_permissions=Permissions(moderate_members=True), guild_ids=COMMAND_GUILD_IDS)
    async def userip(self, interaction: Interaction, member: Member):
        if not self.has_mod_role(interaction.user):
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return

        inf_points = await self.bot.db.base_db.add_inf_points(member.id, 0)

        if inf_points == 0:
            await interaction.response.send_message(f"{member.mention} has no infraction points.")
        elif inf_points == 1:
            await interaction.response.send_message(f"{member.mention} has 1 infraction point.")
        else:
            await interaction.response.send_message(f"{member.mention} has {inf_points} infraction points.")


    @slash_command(name="infpoints", description="View how many infraction points you have.", guild_ids=COMMAND_GUILD_IDS)
    async def infpoints(self, interaction: Interaction):
        target_id = interaction.user.id

        inf_points = await self.bot.db.base_db.add_inf_points(target_id, 0)

        if inf_points == 0:
            await interaction.response.send_message("You have no infraction points.", ephemeral=True)
        elif inf_points == 1:
            await interaction.response.send_message("You have 1 infraction point.", ephemeral=True)
        else:
            await interaction.response.send_message(f"You have {inf_points} infraction points.", ephemeral=True)




def setup(bot: APBot) -> None:
    bot.add_cog(Infraction(bot))
