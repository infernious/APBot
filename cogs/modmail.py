import discord
from discord import app_commands
from discord.ext import tasks, commands

import datetime

modmail_id = 1060459641244500038
blue = 0x00ffff
orange = 0xffa07a


class Modmail(commands.Cog):
    """Read and send messages to other users"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.delay.start()

    @tasks.loop(minutes=5)
    async def delay(self):
        """
        Clears list of people who have DMed the bot in the past 5 minutes to reset the cooldown.
        """
        bot_config = await self.bot.read_user_config(self.bot.application_id)
        bot_config["modmail_users"].clear()
        await self.bot.update_user_config(self.bot.application_id, bot_config)

    @commands.Cog.listener()
    async def on_message(self, message):

        """
        Sends messages sent to the bot's DMs to the modmail channel.
            - Checks if the message is not from the bot and if the message is not from a server.
            - Creates a modmail embed to send in thread.
        """

        if message.author != self.bot.user:

            if message.guild:
                return

            bot_config = await self.bot.read_user_config(self.bot.application_id)
            if message.author.id in bot_config["modmail_users"]:
                await message.author.send(
                    f"You have already contacted the mods recently. You are able to send another message "
                    f"{discord.utils.format_dt(self.delay.next_iteration, style='R')}.")

            elif isinstance(message.channel, discord.DMChannel) and message.author != self.bot.user:

                await message.author.send("Your message has been sent to the mod inbox. We will contact you if needed.")

                modmail_embed = discord.Embed(title="", color=blue)
                modmail_embed.add_field(name=f"", value=f'{message.content}\n - {message.author.mention}',
                                        inline=False)
                modmail_embed.timestamp = datetime.datetime.now()

                if message.attachments:
                    modmail_embed.set_image(url=message.attachments[0].proxy_url)

                guild = self.bot.get_guild(self.bot.guild_id)
                user_config = await self.bot.read_user_config(message.author.id)

                try:
                    thread = await guild.fetch_channel(user_config["modmail_id"])
                    await thread.send(embed=modmail_embed)
                except (KeyError, discord.errors.NotFound, discord.errors.Forbidden):
                    modmail = discord.utils.get(guild.channels, name="modmail")
                    create_thread = await modmail.create_thread(
                        name=f"{message.author.name}#{message.author.discriminator}: {message.author.id}",
                        embed=modmail_embed)
                    thread = create_thread.thread

                    user_config["modmail_id"] = thread.id
                    await self.bot.update_user_config(message.author.id, user_config)

                if len(message.attachments) > 1:

                    attachments_count = 1

                    for attachment in message.attachments:

                        attachment_embed = discord.Embed(title="", color=blue)

                        try:
                            attachment_embed.set_image(url=message.attachments[attachments_count].proxy_url)
                            attachment_embed.set_footer(text=f"{attachments_count + 1}/{len(message.attachments)} attachments")
                        except IndexError:
                            break

                        attachments_count += 1
                        await thread.send(embed=attachment_embed)

                bot_config = await self.bot.read_user_config(self.bot.application_id)
                bot_config["modmail_users"].append(message.author.id)
                await self.bot.update_user_config(self.bot.application_id, bot_config)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        try:
            if reaction.emoji == "✅":
                if reaction.message.channel.parent.name == "modmail":
                    await reaction.message.channel.edit(archived=True)
        except AttributeError:
            return

    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.command(name='send', description='Send messages to other members through modmail.')
    async def send(self, interaction: discord.Interaction, message: str, member: discord.User = None,
                   attachment: discord.Attachment = None):

        """
        Send messages to server members (cannot send message to users not in a server with the bot).
            - Generates a response/member embed.
            - Checks if member is in the cooldown list and removes them if so.
        """

        if member is None:
            try:
                if interaction.channel.parent.name == "modmail":
                    member = self.bot.get_user(interaction.channel.name.split()[-1])
                    if member is None:
                        member = await self.bot.fetch_user(interaction.channel.name.split()[-1])
            except AttributeError:
                raise app_commands.AppCommandError("Please specify a user or use the command in a modmail thread.")

        send_embed = discord.Embed(title="", color=orange)
        send_embed.add_field(name="Message from the mods!", value=f"{message} \u200b")
        send_embed.timestamp = datetime.datetime.now()
        if attachment:
            send_embed.set_image(url=attachment.proxy_url)
        await member.send(embed=send_embed)

        response_embed = discord.Embed(title="", color=orange)
        response_embed.add_field(name=f"Message sent to {member.name}#{member.discriminator}!",
                                 value=f"```{message}```")
        response_embed.timestamp = datetime.datetime.now()
        if attachment:
            response_embed.set_image(url=attachment.proxy_url)
        await interaction.response.send_message(embed=response_embed)

        bot_config = await self.bot.read_user_config(self.bot.application_id)
        if member.id in bot_config["modmail_users"]:
            bot_config["modmail_users"].remove(member.id)
            await self.bot.update_user_config(self.bot.application_id, bot_config)


async def setup(bot):
    await bot.add_cog(Modmail(bot), guilds=[discord.Object(id=bot.guild_id)])
