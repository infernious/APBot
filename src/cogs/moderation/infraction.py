from nextcord import slash_command, Permissions, Interaction, User, Embed, Member, TextChannel, Object, Color
from nextcord.ext import commands
from typing import Optional
from bot_base import APBot
from datetime import datetime, timedelta


class Infraction(commands.Cog):
    def __init__(self, bot: APBot) -> None:
        self.bot = bot

    @slash_command(name="warnings", description="Show infraction history of a member.", default_member_permissions=Permissions(moderate_members=True))
    async def warnings(self, inter: Interaction, member: Member):
        await inter.response.defer(ephemeral=False)  # Make the response visible to everyone

        infraction_details = {
            "warn": ("Warning", Color.from_rgb(255, 255, 0)),  # Yellow
            "mute": ("Mute", Color.from_rgb(255, 165, 0)),   # Orange
            "pseudo-mute": ("Pseudo-Mute", Color.from_rgb(255, 223, 186)),  # Light Orange
            "unmute": ("Unmute", Color.from_rgb(0, 255, 0)),  # Green
            "kick": ("Kick", Color.from_rgb(255, 140, 0)),    # Dark Orange
            "ban": ("Ban", Color.from_rgb(255, 0, 0)),        # Red
            "force-ban": ("Force-Ban", Color.from_rgb(255, 0, 0))  # Red
        }

        # Retrieve infractions from the database
        infractions = await self.bot.db.base_db.get_user_infractions(member.id)

        if not infractions:
            await inter.followup.send(f"{member.mention} has no infractions.", ephemeral=False)  # Make this message visible to everyone
            return

        # Prepare a list to hold all embeds
        embeds = []

        # Loop through the infractions, building embeds for each
        for index, infraction in enumerate(infractions):
            infraction_name, infraction_color = infraction_details.get(infraction.actiontype, ("Infraction", Color.default()))

            # Convert actiontime to datetime if it's stored as a string
            if isinstance(infraction.actiontime, str):
                try:
                    infraction.actiontime = datetime.fromisoformat(infraction.actiontime)
                except ValueError:
                    infraction.actiontime = datetime.utcfromtimestamp(float(infraction.actiontime))

            # Retrieve moderator details
            moderator_id = infraction.moderator
            moderator = inter.guild.get_member(moderator_id) or await self.bot.fetch_user(moderator_id)
            moderator_name = moderator.display_name if moderator else "Unknown"
            moderator_mention = moderator.mention if moderator else "Unknown"

            # Build the infraction message
            infraction_message = (
                f"**Infraction:** {infraction_name}\n"
                f"**Reason:** {infraction.reason}\n"
                f"**Responsible Moderator:** {moderator_name} ({moderator_mention})\n"
                f"**Date:** {infraction.actiontime.strftime('%Y-%m-%d %H:%M:%S')}\n"
            )

            if infraction.duration:
                mute_end = int((infraction.actiontime + timedelta(seconds=infraction.duration)).timestamp())
                infraction_message += f"**Unmute:** <t:{mute_end}:f> (<t:{mute_end}:R>)\n"

            if infraction.attachment_url:
                infraction_message += f"**Attachment:** [Link]({infraction.attachment_url})\n"

            # Create a new embed for this specific infraction
            embed = Embed(
                title=f"Infraction #{index + 1}",
                description=infraction_message,
                color=infraction_color
            )

            # Add the embed to the list
            embeds.append(embed)

        # Send embeds in groups of 10 (Discord's limit for embeds in one message)
        for i in range(0, len(embeds), 10):
            await inter.followup.send(embeds=embeds[i:i+10], ephemeral=False)  # Send visible embeds





    @slash_command(name="editip", description="Edit a member's infraction points.", default_member_permissions=Permissions(moderate_members=True))
    async def editip(self, interaction: Interaction, member: Member, change: int):
        """
        Edit a member's infraction points.
            - Retrieves and adds specified amount to infraction points.
            - Checks if infraction points exceed 30.
        """

        new_inf_points = await self.bot.db.add_inf_points(member.id, change)

        await interaction.response.send_message(f"Added {change} to {member.mention}'s infraction points, they now have {new_inf_points} total.")

        if new_inf_points < 30:
            return

        ch: Optional[TextChannel] = await self.bot.getch_channel(self.bot.config.get("ban_review_channel-id"))
        if not ch:
            return

        await ch.send(
            content=f"<@&{self.bot.config.get('mod_role_id')}>",
            embed=Embed(
                title="Member has reached 30 inf points",
                description=f"{member.mention} has {new_inf_points} IPs and should be reviewed for a ban.",
                color=self.bot.colors.get("red")
            )
        )

    @slash_command(name="update", description="Update a member's infraction history.", default_member_permissions=Permissions(moderate_members=True))
    async def update(self, interaction: Interaction, user:  User, infraction: int, update: str):
        member_config = await self.bot.read_user_config(user.id)
        infractions = member_config["infractions"]
        infraction_update = infractions[infraction + 1]

        if infraction_update['update'] is None:
            infraction_update['update'] = []

        update_dict = {
            "moderator": interaction.user.mention,
            "update": update,
            "date": datetime.datetime.utcnow()
        }

        infraction_update['update'].append(update_dict)


    @slash_command(name="userip", description="View a member's infraction points.", default_member_permissions=Permissions(moderate_members=True))
    async def userip(self, interaction: Interaction, member: Member):
        """
        Displays current infraction points of a user.
        """
        inf_points = len(self.bot.db.base_db.get_user_infractions(member.id))
        if inf_points == 0:
            await interaction.response.send_message(f"{member.mention} has no infraction points.")
        elif inf_points == 1:
            await interaction.response.send_message(f"{member.mention} has 1 infraction point.")
        else:
            await interaction.response.send_message(f"{member.mention} has {inf_points} infraction points.")


    @slash_command(name="infpoints", description="View how many infraction points you have.")
    async def infpoints(self, interaction: Interaction, member: Member):
        """
        Returns command's user infraction points.
        """
        if member and not interaction.user.guild_permissions.moderate_members:
            return await interaction.response.send_message("You do not have permission to check other's infraction points!")
        if not member:
            inf_points = len(self.bot.db.base_db.get_user_infractions(interaction.user.id))
            if inf_points == 0:
                await interaction.response.send_message(f"You have no infraction points.")
            elif inf_points == 1:
                await interaction.response.send_message(f"You have 1 infraction point.")
            else:
                await interaction.response.send_message(f"You have {inf_points} infraction points.")
            return

        inf_points = len(self.bot.db.base_db.get_user_infractions(member.id))
        if inf_points == 0:
            await interaction.response.send_message(f"{member.mention} has no infraction points.")
        elif inf_points == 1:
            await interaction.response.send_message(f"{member.mention} has 1 infraction point.")
        else:
            await interaction.response.send_message(f"{member.mention} has {inf_points} infraction points.")


async def setup(bot: APBot) -> None:
    bot.add_cog(Infraction(bot))
