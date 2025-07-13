import nextcord
from nextcord.ext import commands
import traceback
import sys
import json
import io
import asyncio
import threading
from bot_base import APBot

# Store original streams to prevent recursive redirection
original_stdout = sys.stdout
original_stderr = sys.stderr

# Avoid multiple logging instances
already_redirected = False


class StreamToDiscord(io.StringIO):
    def __init__(self, bot: commands.Bot, channel_id: int, stream_name: str):
        super().__init__()
        self.bot = bot
        self.channel_id = channel_id
        self.stream_name = stream_name
        self.buffer = ""
        self.lock = threading.Lock()
        self.flushing = False

    def write(self, message: str):
        with self.lock:
            self.buffer += message
            if "\n" in self.buffer and not self.flushing:
                self.flushing = True
                asyncio.run_coroutine_threadsafe(self.flush(), self.bot.loop)

    async def flush(self):
        await self.bot.wait_until_ready()
        with self.lock:
            msg = self.buffer.strip()
            self.buffer = ""
            self.flushing = False

        if not msg:
            return

        channel = self.bot.get_channel(self.channel_id)
        if channel:
            preview_msg = msg[:1900]
            embed = nextcord.Embed(
                title=f"🪵 {self.stream_name}",
                description=f"```py\n{preview_msg}```" + ("\n... (truncated)" if len(msg) > 1900 else ""),
                color=nextcord.Color.dark_purple()
            )
            try:
                if len(msg) > 1900:
                    file = nextcord.File(io.BytesIO(msg.encode()), filename=f"{self.stream_name.lower()}.log.txt")
                    await channel.send(embed=embed, file=file)
                else:
                    await channel.send(embed=embed)
            except Exception:
                pass


class Logs(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        with open("config.json", "r") as f:
            config = json.load(f)

        self.bot_logs_channel_id = config.get("bot_logs_channel")

        # Set global exception hook once
        sys.excepthook = self.handle_exception

        # Only redirect once globally
        global already_redirected
        if not already_redirected:
            self.bot.loop.create_task(self.redirect_output())
            already_redirected = True

    async def redirect_output(self):
        await self.bot.wait_until_ready()

        # Redirect stdout/stderr to Discord
        sys.stdout = StreamToDiscord(self.bot, self.bot_logs_channel_id, "STDOUT")
        sys.stderr = StreamToDiscord(self.bot, self.bot_logs_channel_id, "STDERR")

    def handle_exception(self, exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        self.bot.loop.create_task(self.send_error_to_channel(error_msg, title="🚨 Uncaught Exception"))

    async def send_error_to_channel(self, error_msg: str, title="⚠️ Error"):
        await self.bot.wait_until_ready()
        channel = self.bot.get_channel(self.bot_logs_channel_id)
        if channel:
            preview = error_msg[:1900]
            embed = nextcord.Embed(
                title=title,
                description=f"```py\n{preview}```" + ("\n... (truncated)" if len(error_msg) > 1900 else ""),
                color=nextcord.Color.red()
            )
            try:
                if len(error_msg) > 1900:
                    file = nextcord.File(io.BytesIO(error_msg.encode()), filename="error.log.txt")
                    await channel.send(embed=embed, file=file)
                else:
                    await channel.send(embed=embed)
            except Exception:
                pass

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: Exception):
        error_msg = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        await ctx.send("An error occurred. The developers have been notified.")
        await self.send_error_to_channel(error_msg, title="⚠️ Prefix Command Error")

    @commands.Cog.listener()
    async def on_application_command_error(self, interaction: nextcord.Interaction, error: Exception):
        error_msg = "".join(traceback.format_exception(type(error), error, error.__traceback__))

        try:
            await interaction.response.send_message(
                "An error occurred. The developers have been notified.", ephemeral=True
            )
        except nextcord.errors.InteractionResponded:
            pass

        await self.send_error_to_channel(error_msg, title="⚠️ Slash Command Error")


def setup(bot: APBot):
    bot.add_cog(Logs(bot))
