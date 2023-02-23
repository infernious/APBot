import discord
from discord import app_commands
from discord.ext import tasks, commands

import datetime

modmail_id = 1060459641244500038
blue = 0x00ffff


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
            - Creates a modmail embed to send.
        """

        if message.author != self.bot.user:

            if message.guild:
                return

            bot_config = await self.bot.read_user_config(self.bot.application_id)
            if message.author.id in bot_config["modmail_users"]:
                await message.author.send(f"You have already contacted the mods recently. "
                                          f"You are able to send another message "
                                          f"{discord.utils.format_dt(self.delay.next_iteration, style='R')}.")

            else:

                modmail_embed = discord.Embed(title="", color=blue)
                modmail_embed.add_field(
                    name=f"Message from {message.author.display_name}#{message.author.discriminator}"
                         f" (ID: {message.author.id})",
                    value=f'{message.content} \u200b\n - {message.author.mention}', inline=False)
                modmail_embed.timestamp = datetime.datetime.now()
                guild = self.bot.get_guild(self.bot.guild_id)
                modmail = discord.utils.get(guild.channels, name="modmail")

                attachments_boolean = False
                attachments_count = 1
                attachment_embeds = []
                # Check if the message has any attachments or image URLs
                if message.attachments:
                    # If it does, add the URLs to the string
                    if len(message.attachments) > 1:

                        attachments_boolean = True

                        for attachment in message.attachments:
                            attachment_embed = discord.Embed(title="", color=blue)
                            attachment_embed.set_image(url=attachment.proxy_url)
                            attachment_embed.set_footer(
                                text=f"{attachments_count + 1}/{len(message.attachments) + 1} attachments | "
                                     f"{message.author.display_name}#{message.author.discriminator}")
                            attachment_embeds.append(attachment_embed)
                            attachments_count += 1

                    else:
                        modmail_embed.set_footer(text="1/1 attachment")
                        modmail_embed.set_image(url=message.attachments[0].proxy_url)

                await modmail.send(embed=modmail_embed)

                if attachments_boolean:
                    for attachment_embed in attachment_embeds:
                        await modmail.send(embed=attachment_embed)

                await message.author.send("Your message has been sent to the mod inbox. We will contact you if needed.")
                bot_config = await self.bot.read_user_config(self.bot.application_id)
                bot_config["modmail_users"].append(message.author.id)
                await self.bot.update_user_config(self.bot.application_id, bot_config)

    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.command(name='send', description='Send messages to other members through modmail.')
    async def send(self, interaction: discord.Interaction, member: discord.User, *, message: str, attachment: discord.Attachment = None):

        """
        Send messages to server members (cannot send message to users not in a server with the bot).
            - Generates a response/member embed.
            - Checks if member is in the cooldown list and removes them if so.
        """

        send_embed = discord.Embed(title="", color=blue)
        send_embed.add_field(name="Message from the mods!", value=f"{message} \u200b")
        send_embed.timestamp = datetime.datetime.now()
        if attachment:
            send_embed.set_image(url=attachment.proxy_url)
        await member.send(embed=send_embed)

        response_embed = discord.Embed(title="", color=blue)
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
