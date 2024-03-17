import datetime

from nextcord import slash_command, Permissions, Interaction, User, Embed, Member, TextChannel, Object
from nextcord.ext import commands
from typing import Optional
from bot_base import APBot


class Infraction(commands.Cog):
    def __init__(self, bot: APBot) -> None:
        self.bot = bot

    @slash_command(name="warnings", description="Show infraction history of a member.", default_member_permissions=Permissions(moderate_members=True))
    async def warnings(self, interaction: Interaction, user: User):
        """
        Retrieve full infraction history of a member.
            - Reads each infraction in infraction history list.
            - Sends an embed for each infraction.
        """
        await interaction.response.send_message(f"Fetching {user.mention}'s infractions...")

        infractions = await self.bot.db.get_user_infractions(user.id)
        count = 1

        for infraction in infractions:
            match infraction["type"]:
                # /warn
                case "warn":
                    infraction_embed = Embed(
                        title="",
                        color=self.bot.colors.get("yellow")
                    ).add_field(
                        name=f"Warn by {infraction['moderator']}",
                        value=f"**Reason:** {infraction['reason']}"
                    )

                # /wm (NOT /mute)
                case "mute":
                    infraction_embed = Embed(
                        title="",
                        color=self.bot.colors.get("orange")
                    ).add_field(
                        name=f"Mute by {infraction['mute_moderator']}",
                        value=f"**Reason:** {infraction['mute_reason']}\n**Duration:** {infraction['duration']}"
                    )
                    if infraction["unmute_moderator"]:
                        infraction_embed.add_field(
                            name=f"Unmute by {infraction_embed['unmute_moderator']}",
                            value=f"**Reason:** {infraction['unmute_reason']}"
                        )
                        infraction_embed.color = self.bot.colors.get("green")

                
                case "kick":
                    infraction_embed = Embed(
                        title="",
                        color=self.bot.colors.get("dark_orange")
                    ).add_field(
                        name=f"Kick by {infraction['moderator']}",
                        value=f"**Reason:** {infraction['reason']}"
                    )

                # /ban
                case "ban":
                    infraction_embed = Embed(
                        title="",
                        color=self.bot.colors.get("red")
                    ).add_field(
                        name=f"Ban by {infraction['moderator']}",
                        value=f"**Reason:** {infraction['reason']}"
                    )

                # /forceban
                case "force-ban":
                    infraction_embed = Embed(
                        title="",
                        color=self.bot.colors.get("red")
                    ).add_field(
                        name=f"Force-Ban by {infraction['moderator']}",
                        value=f"**Reason:** {infraction['reason']}"
                    )

            infraction_embed.set_footer(text=f"{count}/{len(infractions)} infractions")
            count += 1
            infraction_embed.timestamp = infraction["date"]

            if infraction["attachment"]:
                infraction_embed.set_image(url=infraction['attachment'])
            await interaction.channel.send(embed=infraction_embed)

        await interaction.followup.send(f"Complete, all infractions shown! {user.mention} has {len(infractions)} infraction points")

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
        inf_points = len(self.bot.db.get_user_infractions(member.id))
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
            inf_points = len(self.bot.db.get_user_infractions(interaction.user.id))
            if inf_points == 0:
                await interaction.response.send_message(f"You have no infraction points.")
            elif inf_points == 1:
                await interaction.response.send_message(f"You have 1 infraction point.")
            else:
                await interaction.response.send_message(f"You have {inf_points} infraction points.")
            return

        inf_points = len(self.bot.db.get_user_infractions(member.id))
        if inf_points == 0:
            await interaction.response.send_message(f"{member.mention} has no infraction points.")
        elif inf_points == 1:
            await interaction.response.send_message(f"{member.mention} has 1 infraction point.")
        else:
            await interaction.response.send_message(f"{member.mention} has {inf_points} infraction points.")


async def setup(bot: APBot):
    await bot.add_cog(Infraction(bot), guilds=[Object(id=bot.guild_id)])
