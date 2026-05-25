import asyncio
import nextcord
from nextcord import Interaction, Embed, Object, ui, Color
from nextcord.ext import commands
from nextcord import slash_command

blue = Color.teal()
QOTD_CHANNEL_NAME = "qotd"
QOTD_CURATOR_ROLE_NAME = "QOTD Curator"
QOTD_THREAD_CONFIG_NAME = "qotd_thread_check"


def is_qotd_thread(thread: nextcord.Thread) -> bool:
    parent = getattr(thread, "parent", None)
    return (getattr(parent, "name", "") or "").lower() == QOTD_CHANNEL_NAME


def has_qotd_curator_role(member) -> bool:
    return any(getattr(role, "name", None) == QOTD_CURATOR_ROLE_NAME for role in getattr(member, "roles", []))


def thread_created_at(thread: nextcord.Thread):
    return getattr(thread, "created_at", None) or getattr(thread, "archive_timestamp", None)


def is_thread_closed(thread: nextcord.Thread) -> bool:
    return bool(getattr(thread, "archived", False))

""" Under work for later updates """
class PingHelpers(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Ping Helpers!", style=nextcord.ButtonStyle.red)
    async def ping_helpers(self, button: ui.Button, interaction: Interaction):
        """
        Confirm mention after command is used as to avoid accidental pings.
        - Currently uses subject tags to find the helper role
        """
        button.style = nextcord.ButtonStyle.green
        button.emoji = "✅"
        button.label = "Helpers pinged!"
        button.disabled = True
        self.dismiss.disabled = True

        await interaction.response.edit_message(view=self)

        helpers = []
        for tag in interaction.channel.applied_tags:
            role = nextcord.utils.get(interaction.guild.roles, name=f"{tag.name} Helper")
            if role:
                helpers.append(role)

        try:
            pins = await interaction.channel.pins()
            if helpers:
                await pins[0].reply(f"{helpers[0].mention}, a question has been asked!")
                self.stop()
            else:
                await interaction.followup.send("No helper roles found for the tag.", ephemeral=True)
        except Exception:
            await interaction.followup.send(
                "Please edit your post to have a subject tag first.", ephemeral=True
            )

    @ui.button(label="Dismiss", style=nextcord.ButtonStyle.grey, custom_id="dismiss_button")
    async def dismiss(self, button: ui.Button, interaction: Interaction):
        """
        Dismiss options to ping helpers.
        """
        await interaction.message.delete()
        await interaction.response.send_message(
            "Please add the `✅ Resolved` tag to your post.", ephemeral=True
        )


class Dismiss(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Dismiss", style=nextcord.ButtonStyle.grey, custom_id="dismiss_initial")
    async def dismiss(self, button: ui.Button, interaction: Interaction):
        """
        Dismiss the initial thread message.
        """
        await interaction.message.delete()


class Threads(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def get_thread_owner(self, thread: nextcord.Thread):
        owner = getattr(thread, "owner", None)
        if owner:
            return owner

        owner_id = getattr(thread, "owner_id", None)
        guild = getattr(thread, "guild", None)
        if not owner_id or guild is None:
            return None

        member = guild.get_member(owner_id)
        if member:
            return member

        try:
            return await guild.fetch_member(owner_id)
        except (nextcord.NotFound, nextcord.Forbidden, nextcord.HTTPException):
            return None

    async def qotd_initial_check_done(self) -> bool:
        config = await self.bot.db.base_db.read_bot_config(QOTD_THREAD_CONFIG_NAME)
        return bool(config and config.get("initial_check_done"))

    async def mark_qotd_initial_check_done(self) -> None:
        config = await self.bot.db.base_db.read_bot_config(QOTD_THREAD_CONFIG_NAME) or {
            "name": QOTD_THREAD_CONFIG_NAME,
        }
        config["initial_check_done"] = True
        await self.bot.db.base_db.update_bot_config(config)

    async def close_thread_if_open(self, thread: nextcord.Thread) -> bool:
        if is_thread_closed(thread):
            return False

        try:
            await thread.edit(archived=True)
            return True
        except (nextcord.Forbidden, nextcord.HTTPException):
            return False

    async def active_qotd_threads(self, parent, current_thread: nextcord.Thread) -> list[nextcord.Thread]:
        return [
            candidate
            for candidate in getattr(parent, "threads", [])
            if candidate.id != current_thread.id
        ]

    async def archived_qotd_threads(
        self,
        parent,
        current_thread: nextcord.Thread,
        *,
        limit: int | None,
    ) -> list[nextcord.Thread]:
        if not hasattr(parent, "archived_threads"):
            return []

        threads = []
        try:
            async for candidate in parent.archived_threads(limit=limit):
                if candidate.id != current_thread.id:
                    threads.append(candidate)
        except (nextcord.Forbidden, nextcord.HTTPException):
            return []

        return threads

    def dedupe_threads(self, threads: list[nextcord.Thread]) -> list[nextcord.Thread]:
        deduped = {}
        for thread in threads:
            deduped[thread.id] = thread
        return list(deduped.values())

    async def get_all_previous_qotd_threads(self, thread: nextcord.Thread) -> list[nextcord.Thread]:
        parent = thread.parent
        candidates = await self.active_qotd_threads(parent, thread)
        candidates.extend(await self.archived_qotd_threads(parent, thread, limit=None))
        return self.dedupe_threads(candidates)

    async def get_most_recent_previous_qotd_thread(self, thread: nextcord.Thread):
        parent = thread.parent
        candidates = await self.active_qotd_threads(parent, thread)

        if not candidates:
            candidates.extend(await self.archived_qotd_threads(parent, thread, limit=1))

        candidates = self.dedupe_threads(candidates)
        if not candidates:
            return None

        return max(candidates, key=lambda candidate: thread_created_at(candidate) or candidate.id)

    async def close_qotd_threads_for_new_thread(self, thread: nextcord.Thread) -> None:
        if await self.qotd_initial_check_done():
            previous_thread = await self.get_most_recent_previous_qotd_thread(thread)
            if previous_thread:
                await self.close_thread_if_open(previous_thread)
            return

        previous_threads = await self.get_all_previous_qotd_threads(thread)
        for previous_thread in previous_threads:
            await self.close_thread_if_open(previous_thread)

        await self.mark_qotd_initial_check_done()

    async def handle_qotd_thread_create(self, thread: nextcord.Thread) -> bool:
        if not is_qotd_thread(thread):
            return False

        owner = await self.get_thread_owner(thread)
        if owner and has_qotd_curator_role(owner):
            await self.close_qotd_threads_for_new_thread(thread)

        return True

    @slash_command(name="resolve", description="Mark a thread as resolved and archive it.")
    async def resolve(self, interaction: Interaction):
        """
        Mark a thread as resolved to archive it.
        Works in both forum threads and text channel threads.
        """
        if not isinstance(interaction.channel, nextcord.Thread):
            await interaction.response.send_message(
                "This command can only be used inside a thread.",
                ephemeral=True
            )
            return

        embed = Embed(title="", color=blue)
        embed.add_field(
            name="Resolved ✅",
            value=f"Post marked as resolved by {interaction.user.mention}."
        )

        await interaction.response.send_message(embed=embed)

        parent = interaction.channel.parent
        resolved_tag = None

        # Only try to get forum tag if parent has tags
        if hasattr(parent, "available_tags"):
            resolved_tag = nextcord.utils.get(parent.available_tags, name="Resolved")

        if resolved_tag:
            try:
                await interaction.channel.add_tags(resolved_tag)
            except Exception:
                pass  # Tag might not be applicable or may already exist

        try:
            await interaction.channel.edit(archived=True)
        except Exception:
            await interaction.followup.send("Failed to archive the thread.", ephemeral=True)


    @commands.Cog.listener()
    async def on_thread_create(self, thread: nextcord.Thread):
        """
        - Sends initial message in forum post when created with option to dismiss.
        - After 10 minutes, provides an option to ping helpers.
        """
        if await self.handle_qotd_thread_create(thread):
            return

        if thread.parent.name in ["modmail", "important-updates"]:
            return

        await asyncio.sleep(1)
        try:
            await thread.starter_message.pin()
        except Exception:
            pass

        thread_embed = Embed(title="", color=blue)
        thread_embed.add_field(
            name="Guidelines",
            value=(
                "Be sure you are following our rules and guidelines!\n"
                "- If you haven't already, send your attempts at a solution.\n"
                "- Also be sure that your title is following the `[Topic] question` format."
            ),
            inline=False
        )
        thread_embed.add_field(
            name="Resolved",
            value="Once your question has been answered, please mark your thread as `✅ Resolved`.",
            inline=False
        )
        thread_embed.add_field(
            name="Help",
            value="You will be able to ping helpers after 10 minutes.",
            inline=False
        )

        await thread.send(embed=thread_embed, view=Dismiss())

        await asyncio.sleep(600)  # 10 minutes
        help_embed = Embed(color=blue)
        help_embed.add_field(
            name="",
            value="If help is still needed, you may ping helpers now.",
            inline=False
        )

        await thread.starter_message.reply(embed=help_embed, view=PingHelpers())

    @commands.Cog.listener()
    async def on_thread_update(self, before: nextcord.Thread, after: nextcord.Thread):
        """
        If thread is updated with "Resolved" tag, then thread is archived.
        """
        if not after.applied_tags:
            return  # Not a forum thread, or no tags available

        tag_names = [tag.name for tag in after.applied_tags]
        if "Resolved" in tag_names:
            await after.edit(archived=True)



def setup(bot: commands.Bot):
    bot.add_cog(Threads(bot))
