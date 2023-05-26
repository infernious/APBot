import datetime

import discord
from discord import Message, Reaction, TextChannel, Thread, User, app_commands
from discord.ext import commands, tasks

from bot_base import APBot


class Modmail(commands.Cog):
    """Read and send messages to other users"""

    def __init__(self, bot: APBot) -> None:
        self.bot = bot
        self.delay_loop.start()

    @tasks.loop(minutes=5)
    async def delay_loop(self):
        """
        Clears list of people who have DMed the bot in the past 5 minutes to reset the cooldown.
        """

        bot_config = await self.bot.read_user_config(self.bot.application_id)
        bot_config["modmail_users"].clear()
        await self.bot.update_user_config(self.bot.application_id, bot_config)

    @delay_loop.before_loop
    async def delay_before_loop(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        """
        Sends messages sent to the bot's DMs to the modmail channel.
            - Checks if the message is not from the bot and if the message is not from a server.
            - Creates a modmail embed to send in thread.
        """

        if message.guild or message.author == self.bot.user:
            return

        bot_config = await self.bot.read_user_config(self.bot.application_id)
        if message.author.id in bot_config["modmail_users"]:
            return await message.author.send(
                f"Please wait for {discord.utils.format_dt(self.delay_loop.next_iteration, style='R')} before contacting modmail again."
            )

        await message.author.send("Your message has been sent to the mod inbox. We will contact you if needed.")

        modmail_embed = discord.Embed(title="", color=self.bot.colors["blue"], timestamp=datetime.datetime.now())
        modmail_embed.add_field(name="", value=f"{message.content}\n - {message.author.mention}", inline=False)

        if message.attachments:
            modmail_embed.set_image(url=message.attachments[0].proxy_url)

        guild = self.bot.get_guild(self.bot.guild_id)
        user_config = await self.bot.read_user_config(message.author.id)

        try:
            guild = await self.bot.getch_guild(self.bot.guild_id)
            thread = await guild.fetch_channel(user_config["modmail_id"])
            await thread.send(embed=modmail_embed)
            await thread.starter_message.clear_reactions()
        except (KeyError, discord.errors.NotFound, discord.errors.Forbidden):
            modmail: TextChannel = await self.bot.getch_channel(self.bot.config.get("modmail_channel"))
            create_thread: Thread = await modmail.create_thread(
                name=f"{message.author}: {message.author.id}", embed=modmail_embed
            )
            thread = create_thread.thread

            user_config["modmail_id"] = thread.id
            await self.bot.update_user_config(message.author.id, user_config)

        if len(message.attachments) > 1:
            attachments_count = 1
            for attachment in message.attachments:
                attachment_embed = discord.Embed(title="", color=self.bot.colors["blue"])

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
    async def on_reaction_add(self, reaction: Reaction, user: User):
        try:
            if reaction.message.channel.parent.name == "modmail":
                await reaction.message.channel.edit(archived=True)
        except AttributeError:
            return

    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.command(name="send", description="Send messages to other members through modmail.")
    async def send(
        self, interaction: discord.Interaction, member: discord.User, *, message: str, attachment: discord.Attachment = None
    ):
        """
        Send messages to server members (cannot send message to users not in a server with the bot).
            - Generates a response/member embed.
            - Checks if member is in the cooldown list and removes them if so.
        """

        send_embed = discord.Embed(title="", color=self.bot.colors["orange"], timestamp=datetime.datetime.now())
        send_embed.add_field(name="Message from the mods!", value=f"{message} \u200b")
        if attachment:
            send_embed.set_image(url=attachment.proxy_url)
        await member.send(embed=send_embed)

        response_embed = discord.Embed(title="", color=self.bot.colors["orange"], timestamp=datetime.datetime.now())
        response_embed.add_field(name=f"Message sent to {member}!", value=f"```\n{message}\n```")
        if attachment:
            response_embed.set_image(url=attachment.proxy_url)
        await interaction.response.send_message(embed=response_embed)

        bot_config = await self.bot.read_user_config(self.bot.application_id)
        if member.id in bot_config["modmail_users"]:
            bot_config["modmail_users"].remove(member.id)
            await self.bot.update_user_config(self.bot.application_id, bot_config)


async def setup(bot: APBot):
    await bot.add_cog(Modmail(bot), guilds=[discord.Object(id=bot.guild_id)])
