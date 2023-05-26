import time
from datetime import datetime
from typing import Optional, Union

import discord
import motor.motor_asyncio as motor
from discord import Guild, Member, Message, Role, User
from discord.abc import GuildChannel
from discord.ext import commands

from config_handler import Config


class APBot(commands.Bot):
    def __init__(self, db):
        self.config = Config()
        self.db = db
        self.user_config = db["user_config"]
        self.guild_id = self.config.get("guild_id")

        if not self.guild_id:
            print("No guild ID found in config.json")
            raise SystemExit

        default_colors = {
            "yellow": 0xFFFF00,
            "orange": 0xFFA500,
            "light_orange": 0xFFA07A,
            "dark_orange": 0xFF5733,
            "red": 0xFF0000,
            "green": 0x00FF00,
            "blue": 0x00FFFF,
        }

        self.colors = default_colors.update({i: hex(int(j, 16)) for i, j in self.config.get("colors", {})})

        super().__init__(
            command_prefix=self.config.get("command_prefix", "ap:"),
            intents=discord.Intents.all(),
            activity=discord.Activity(type=discord.ActivityType.playing, name="DM me to contact mods!"),
        )

    async def setup_hook(self) -> None:
        initial_extensions = [
            "cogs.errorhandler",
            "cogs.events",
            "cogs.moderation.appeal",
            "cogs.moderation.commands",
            "cogs.moderation.decay",
            "cogs.modmail",
            "cogs.rolereact",
            "cogs.study",
            # 'cogs.threads',
        ]

        for extension in initial_extensions:
            await self.load_extension(extension)

        await self.tree.sync(guild=discord.Object(id=self.guild_id))

    async def on_ready(self):
        self.guild = await self.getch_guild(self.guild_id)
        if not self.guild:
            print("Guild not found")
            raise SystemExit

        print(f'Logged in as {self.user} at {datetime.fromtimestamp(time.time()).strftime(r"%d-%b-%y, %H:%M:%S")} (GMT)')

    async def read_user_config(self, user_id: int):
        config_from_db = await self.db["user_config"].find_one({"user_id": user_id})

        if config_from_db is None:
            config_from_db = {"user_id": user_id, "infraction_points": 0, "infractions": []}
            await self.db["user_config"].insert_one(config_from_db)

        return config_from_db

    async def update_user_config(self, user_id: int, new_config):
        old_config = await self.db["user_config"].find_one({"user_id": user_id})

        if old_config is None:
            config = {"user_id": user_id, "infraction_points": 0, "infractions": []}
            old_config = await self.db["user_config"].insert_one(config)

        _id = old_config["_id"]
        await self.db["user_config"].replace_one({"_id": _id}, new_config)

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
        guild: Optional[Guild] = self.getch_guild(guild_id)
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
