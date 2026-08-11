import traceback

import nextcord
from nextcord.ext import commands

from bot_base import APBot


PFP_LOGS_CHANNEL_ID = 1536898222017085480


class PfpLogCog(commands.Cog):
    def __init__(self, bot: APBot):
        self.bot = bot

    def config_get(self, key, default=None):
        config = getattr(self.bot, "config", None)
        if config is None:
            return default
        return config.get(key, default)

    def logs_channel_id(self):
        try:
            return int(self.config_get("pfp_logs_channel", PFP_LOGS_CHANNEL_ID))
        except (TypeError, ValueError):
            return None

    def avatar_url(self, user):
        avatar = getattr(user, "display_avatar", None) or getattr(user, "avatar", None)
        return getattr(avatar, "url", "") or ""

    def guild_avatar_url(self, member):
        avatar = getattr(member, "guild_avatar", None)
        return getattr(avatar, "url", "") or ""

    def display_name(self, user):
        return (
            getattr(user, "display_name", None)
            or getattr(user, "name", None)
            or str(getattr(user, "id", "Unknown"))
        )

    def footer_text(self, user):
        timestamp = nextcord.utils.utcnow().strftime("%Y-%m-%d %I:%M %p UTC")
        return f"User ID: {getattr(user, 'id', 'Unknown')} • {timestamp}"

    def set_author(self, embed, user):
        icon_url = self.avatar_url(user)
        if icon_url:
            embed.set_author(name=self.display_name(user), icon_url=icon_url)
        else:
            embed.set_author(name=self.display_name(user))

    def is_in_guild(self, user_id):
        guild_id = self.config_get("guild_id")
        get_guild = getattr(self.bot, "get_guild", None)
        if guild_id is None or get_guild is None:
            return True

        try:
            guild = get_guild(int(guild_id))
        except (TypeError, ValueError):
            return True

        if guild is None:
            return True

        return guild.get_member(user_id) is not None

    async def send_log(self, embed):
        channel_id = self.logs_channel_id()
        if not channel_id:
            return

        channel = self.bot.get_channel(channel_id)
        if channel is None:
            return

        try:
            await channel.send(embed=embed)
        except Exception:
            pass

    async def log_avatar_change(self, user, before_url, after_url, label):
        if after_url:
            description = f"{user.mention} changed their {label}"
            color = nextcord.Color.blue()
        else:
            description = f"{user.mention} removed their {label}"
            color = nextcord.Color.red()

        embed = nextcord.Embed(description=description, color=color)
        self.set_author(embed, user)

        if before_url:
            embed.add_field(name="Old", value=f"[Link]({before_url})", inline=True)
            embed.set_thumbnail(url=before_url)
        if after_url:
            embed.add_field(name="New", value=f"[Link]({after_url})", inline=True)
            embed.set_image(url=after_url)

        embed.set_footer(text=self.footer_text(user))
        await self.send_log(embed)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        try:
            if getattr(member, "bot", False):
                return

            avatar_url = self.avatar_url(member)
            embed = nextcord.Embed(
                description=f"{member.mention} joined with this profile picture",
                color=nextcord.Color.green(),
            )
            self.set_author(embed, member)

            if avatar_url:
                embed.add_field(name="Profile Picture", value=f"[Link]({avatar_url})", inline=True)
                embed.set_image(url=avatar_url)

            if getattr(member, "avatar", None) is None:
                embed.add_field(name="Note", value="Using the default Discord avatar", inline=True)

            created_at = getattr(member, "created_at", None)
            if created_at is not None:
                embed.add_field(
                    name="Account Created",
                    value=nextcord.utils.format_dt(created_at, "F"),
                    inline=False,
                )

            embed.set_footer(text=self.footer_text(member))
            await self.send_log(embed)
        except Exception as e:
            print(f"Error in on_member_join: {type(e).__name__}: {e}")
            traceback.print_exc()

    @commands.Cog.listener()
    async def on_user_update(self, before, after):
        try:
            if getattr(after, "bot", False):
                return

            before_url = self.avatar_url(before)
            after_url = self.avatar_url(after)
            if before_url == after_url:
                return

            if not self.is_in_guild(getattr(after, "id", None)):
                return

            await self.log_avatar_change(after, before_url, after_url, "profile picture")
        except Exception as e:
            print(f"Error in on_user_update: {type(e).__name__}: {e}")
            traceback.print_exc()

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        try:
            if getattr(after, "bot", False):
                return

            before_url = self.guild_avatar_url(before)
            after_url = self.guild_avatar_url(after)
            if before_url == after_url:
                return

            await self.log_avatar_change(after, before_url, after_url, "server profile picture")
        except Exception as e:
            print(f"Error in on_member_update: {type(e).__name__}: {e}")
            traceback.print_exc()


def setup(bot: APBot):
    bot.add_cog(PfpLogCog(bot))
