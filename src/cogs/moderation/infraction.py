import nextcord
import datetime
from nextcord import app_commands
from nextcord.ext import tasks, commands


yellow = 0xffff00
orange = 0xffa500
light_orange = 0xffa07a
dark_orange = 0xff5733
red = 0xff0000
green = 0x00ff00


class Infraction(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.command(name='warnings', description="Show infraction history of a member.")
    async def warnings(self, interaction: nextcord.Interaction, user: nextcord.User):
        """
        Retrieve full infraction history of a member.
            - Reads each infraction in infraction history list.
            - Sends an embed for each infraction.
        """

        await interaction.response.send_message(f"Fetching {user.mention}'s warnings...")
        member_config = await self.bot.read_user_config(user.id)
        infractions = member_config["infractions"]
        count = 1
        for infraction in infractions:
            match infraction["type"]:
                # /warn
                case "warn":
                    infraction_embed = nextcord.Embed(title="", color=yellow)
                    infraction_embed.add_field(name="Warn", value=f"Reason: {infraction['reason']}\n"
                                                                  f"Responsible Mod: {infraction['moderator']}")
                # /wm (NOT /mute)
                case "mute":
                    infraction_embed = nextcord.Embed(title="", color=orange)
                    infraction_embed.add_field(name="Mute", value=f"Reason: {infraction['reason']}\n"
                                                                  f"Duration: {infraction['duration']}\n"
                                                                  f"Responsible Mod: {infraction['moderator']}")
                    try:
                        infraction_embed.add_field(name="Unmute", value=f"Reason: {infraction['unmute reason']}\n"
                                                                        f"Responsible Mod: {infraction['moderator']}")
                        infraction_embed.color = green
                    except KeyError:
                        pass
                case "kick":
                    infraction_embed = nextcord.Embed(title="", color=dark_orange)
                    infraction_embed.add_field(name="Warn", value=f"Reason: {infraction['reason']}\n"
                                                                  f"Responsible Mod: {infraction['moderator']}")
                # /ban
                case "ban":
                    infraction_embed = nextcord.Embed(title="", color=red)
                    infraction_embed.add_field(name="Ban", value=f"Reason: {infraction['reason']}\n"
                                                                 f"Responsible Mod: {infraction['moderator']}")
                # /forceban
                case "force-ban":
                    infraction_embed = nextcord.Embed(title="", color=red)
                    infraction_embed.add_field(name="Force-Ban", value=f"Reason: {infraction['reason']}\n"
                                                                       f"Responsible Mod: {infraction['moderator']}")

            infraction_embed.set_footer(text=f"{count}/{len(infractions)} infractions")
            count += 1
            infraction_embed.timestamp = infraction["date"]
            try:
                infraction_embed.set_image(url=infraction['attachment'])
            except KeyError:
                pass
            await interaction.channel.send(embed=infraction_embed)

        await interaction.followup.send(f"Complete, all infractions shown! {user.mention} has "
                                        f"{member_config['infraction_points']} infraction points.")

    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.command(name='editip', description="Edit a member's infraction points.")
    async def editip(self, interaction: nextcord.Interaction, member: nextcord.Member, change: int):
        """
        Edit a member's infraction points.
            - Retrieves and adds specified amount to infraction points.
            - Checks if infraction points exceed 30.
        """

        member_config = await self.bot.read_user_config(member.id)
        member_config["infraction_points"] += change
        await self.bot.update_user_config(member.id, member_config)

        await interaction.response.send_message(f"Adding {change} to {member.mention}'s infraction points, "
                                                f"they now have {member_config['infraction_points']} total.\n")

        if member_config["infraction_points"] >= 30:
            guild = self.bot.get_guild(self.bot.guild_id)
            update = nextcord.utils.get(guild.channels, name="important-updates")
            chat_mod = nextcord.utils.get(guild.roles, name='Chat Moderator')

            ban_warn_embed = nextcord.Embed(title='', color=red)
            ban_warn_embed.add_field(name='Member has reached 30 infraction points!',
                                     value=f'{member.mention} has {member_config["infraction_points"]} infraction points'
                                           f' and should be reviewed for a ban.')

            await update.send(f"{chat_mod.mention}", embed=ban_warn_embed)

    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.command(name='update', description="Update a member's infraction history.")
    async def update(self, interaction: nextcord.Interaction, user: nextcord.User, infraction: int, update: str):

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




    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.command(name='userip', description="View a member's infraction points.")
    async def userip(self, interaction: nextcord.Interaction, member: nextcord.Member):
        """
        Displays current infraction points of a user.
        """

        member_config = await self.bot.read_user_config(member.id)
        await interaction.response.send_message(
            f"{member.mention} has {member_config['infraction_points']} infraction point(s).")

    @app_commands.command(name='infpoints', description="View how many infraction points you have.")
    async def infpoints(self, interaction: nextcord.Interaction):
        """
        Returns command's user infraction points.
        """

        member_config = await self.bot.read_user_config(interaction.user.id)
        await interaction.response.send_message(
            f"You have **{member_config['infraction_points']} infraction point(s).**", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Infraction(bot), guilds=[nextcord.Object(id=bot.guild_id)])