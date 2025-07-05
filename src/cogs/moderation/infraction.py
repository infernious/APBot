import nextcord
from nextcord import slash_command, Permissions, Interaction, User, Embed, Member, TextChannel, Object, Color
from nextcord.ext import commands
from typing import Optional
from bot_base import APBot
from datetime import datetime, timedelta


class Infraction(commands.Cog):
    def __init__(self, bot: APBot) -> None:
        self.bot = bot

    @slash_command(
        name="warnings",
        description="Show infraction history of a member.",
        default_member_permissions=Permissions(moderate_members=True)
    )
    async def warnings(self, inter: Interaction, member: Member):
        await inter.response.defer(with_message=False)  # No "Bot is thinking..." message

        infractions = await self.bot.db.base_db.get_user_infractions(member.id)
        inf_points = await self.bot.db.base_db.add_inf_points(member.id, 0)

        if not infractions:
            await inter.followup.send(f"{member.mention} has no infractions.")
            return

        # Send fetching message and keep reference to reply later
        fetching_msg = await inter.channel.send(f"Fetching {member.mention}'s warnings...")

        color_map = {
            "warn": self.bot.colors.get("yellow", Color.yellow()),
            "mute": self.bot.colors.get("orange", Color.orange()),
            "pseudo-mute": self.bot.colors.get("light_orange", Color.orange()),
            "kick": self.bot.colors.get("dark_orange", Color.orange()),
            "ban": self.bot.colors.get("red", Color.red()),
            "force-ban": self.bot.colors.get("red", Color.red()),
            "unmute": self.bot.colors.get("green", Color.green()),
        }

        total = len(infractions)

        for index, inf in enumerate(infractions, start=1):
            action = inf.actiontype.capitalize().replace("-", " ")
            reason = inf.reason or "No reason provided"

            mod = inter.guild.get_member(inf.moderator) or await self.bot.fetch_user(inf.moderator)
            mod_tag = f"{mod.global_name}#{mod.discriminator}" if hasattr(mod, "global_name") else f"{mod.name}#{mod.discriminator}"
            mod_line = f"{mod.mention if mod else f'<@{inf.moderator}>'} ({mod_tag})"

            # Parse timestamp
            time = inf.actiontime
            if isinstance(time, str):
                try:
                    time = datetime.fromisoformat(time)
                except ValueError:
                    time = datetime.utcfromtimestamp(float(time))

            timestamp = (
                f"Yesterday at {time.strftime('%I:%M %p').lstrip('0')}"
                if (datetime.now() - time).days < 1
                else time.strftime("%-m/%-d/%Y %-I:%M %p").replace(" 0", "")
            )

            # Handle duration safely
            duration_line = ""
            if inf.duration:
                try:
                    duration_seconds = int(inf.duration.total_seconds()) if isinstance(inf.duration, timedelta) else int(inf.duration)
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
                color=color_map.get(inf.actiontype, Color.gold())
            )

            await inter.channel.send(embed=embed)

        await fetching_msg.reply(
            f"Complete, all infractions shown! {member.mention} has `{inf_points}` infraction point(s)."
        )



    @slash_command(
        name="editip",
        description="Edit a member's infraction points.",
        default_member_permissions=Permissions(moderate_members=True)
    )
    async def editip(self, interaction: Interaction, member: Member, change: int):
        """
        Edit a member's infraction points.
        """
        new_inf_points = await self.bot.db.base_db.add_inf_points(member.id, change)

        await interaction.response.send_message(
            f"Added {change} to {member.mention}'s infraction points, they now have {new_inf_points} total."
        )

        if new_inf_points < 30:
            return

        # Notify ban review channel
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

        # Also ping Chat Moderator in #important-updates
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

    @slash_command(name="userip", description="View a member's infraction points.", default_member_permissions=Permissions(moderate_members=True))
    async def userip(self, interaction: Interaction, member: Member):
        """
        Displays current infraction points of a user.
        """
        inf_points = await self.bot.db.base_db.add_inf_points(member.id, 0)

        if inf_points == 0:
            await interaction.response.send_message(f"{member.mention} has no infraction points.")
        elif inf_points == 1:
            await interaction.response.send_message(f"{member.mention} has 1 infraction point.")
        else:
            await interaction.response.send_message(f"{member.mention} has {inf_points} infraction points.")


    @slash_command(name="infpoints", description="View how many infraction points you have.")
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
