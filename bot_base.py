from typing import Optional, Union

import motor.motor_asyncio as motor
from nextcord import Guild, Member, Message, Role, User
from nextcord.abc import GuildChannel
from nextcord.ext import commands

from config_handler import Config
from database_handler import Database


class APBot(commands.Bot):
    guild: Guild
    db: Database
    config: Config
    colors: dict
    rolemenu_view_set: bool

    async def getch_guild(self, guild_id: int) -> Optional[Guild]:
        """Looks up a guild in cache or fetches if not found."""
        guild: Union[Guild, None] = self.get_guild(guild_id)
        if guild:
            return guild

        try:
            guild: Union[Guild, None] = await self.fetch_guild(guild_id)
        except:
            return False
        return guild

    async def getch_role(self, guild_id: int, role_id: int) -> Optional[Role]:
        """Looks up a guild in cache or fetches if not found."""
        guild: Optional[Guild] = await self.getch_guild(guild_id)
        if not guild:
            return False
        role: Optional[Role] = guild.get_role(role_id)
        if role:
            return role
        else:
            try:
                role = await guild.fetch_role(role_id)
            except:
                return False
        return role

    async def getch_user(self, user_id: int) -> Optional[User]:
        """Looks up a user in cache or fetches if not found."""
        user: Union[User, None] = self.get_user(user_id)
        if user:
            return user
        try:
            user: Union[User, None] = await self.fetch_user(user_id)
        except:
            return False
        return user

    async def getch_member(self, guild_id: int, member_id: int) -> Optional[Member]:
        """Looks up a member in cache or fetches if not found."""

        guild: Union[Member, None] = await self.getch_guild(guild_id)
        if not guild:
            return False

        member: Union[Member, None] = guild.get_member(member_id)
        if member is not None:
            return member

        try:
            member: Union[Member, None] = await guild.fetch_member(member_id)
        except:
            return False

        return member

    async def getch_channel(self, channel_id: int) -> Optional[GuildChannel]:
        """Looks up a channel in cache or fetches if not found."""
        channel: Union[GuildChannel, None] = self.get_channel(channel_id)
        if channel:
            return channel

        try:
            channel: Union[GuildChannel, None] = await self.fetch_channel(channel_id)
        except:
            return False

        return channel

    async def getch_message(self, channel_id: int, message_id: int) -> Optional[Message]:
        """Looks up a channel in cache or fetches if not found."""
        channel = await self.getch_channel(channel_id)
        if not channel:
            return None

        try:
            message = await channel.fetch_message(message_id)
            return message
        except:
            return None

    async def resync_slash_commands(self) -> None:
        await self.guild.sync_application_commands()
