from __future__ import annotations

import io
import json
from datetime import datetime, timezone, timedelta
from typing import Any, Iterable, Optional

import aiohttp
import nextcord
from nextcord.ext import commands

from bot_base import APBot


LOG_CHANNEL_NAME = "server-log"
LOG_CHANNEL_CONFIG_KEYS = (
    "server_log_channel",
    "server_logs_channel",
    "logs_channel",
)

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".bmp")
GIF_EXTENSIONS = (".gif",)
VIDEO_EXTENSIONS = (".mp4", ".mov", ".webm", ".m4v", ".mkv")
PREVIEW_URL_EXTENSIONS = (
    ".gif",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".mp4",
    ".mov",
    ".webm",
)


class ServerLog(commands.Cog):
    def __init__(self, bot: APBot) -> None:
        self.bot = bot

        # message_id -> raw poll payload
        self.poll_cache: dict[int, dict[str, Any]] = {}

    def get_log_channel(self, guild: nextcord.Guild) -> Optional[nextcord.TextChannel]:
        configured_channel_id = self.configured_log_channel_id()

        if configured_channel_id is not None:
            channel = self.bot.get_channel(configured_channel_id)

            if isinstance(channel, nextcord.TextChannel):
                return channel

        channel = nextcord.utils.get(guild.text_channels, name=LOG_CHANNEL_NAME)
        return channel if isinstance(channel, nextcord.TextChannel) else None

    def configured_log_channel_id(self) -> Optional[int]:
        config = getattr(self.bot, "config", None)

        if config is None:
            return None

        for key in LOG_CHANNEL_CONFIG_KEYS:
            value = config.get(key)

            if value is None:
                continue

            try:
                return int(value)
            except (TypeError, ValueError):
                continue

        return None

    def clip(self, text: str, limit: int) -> str:
        if len(text) <= limit:
            return text

        return text[: limit - 20] + "\n... *(cut off)*"

    def attachment_kind(self, attachment: nextcord.Attachment) -> str:
        content_type = (attachment.content_type or "").lower()
        filename = attachment.filename.lower()

        if content_type.startswith("video/") or filename.endswith(VIDEO_EXTENSIONS):
            return "video"

        if "gif" in content_type or filename.endswith(GIF_EXTENSIONS):
            return "gif"

        if content_type.startswith("image/") or filename.endswith(IMAGE_EXTENSIONS):
            return "image"

        return "file"

    def is_visual_attachment(self, attachment: nextcord.Attachment) -> bool:
        return self.attachment_kind(attachment) in {"image", "gif"}

    def is_previewable_attachment(self, attachment: nextcord.Attachment) -> bool:
        return True

    def attachment_url(self, attachment: nextcord.Attachment) -> str:
        return attachment.proxy_url or attachment.url

    def find_preview_url_in_content(self, content: str) -> Optional[str]:
        if not content:
            return None

        for raw_part in content.split():
            part = raw_part.strip("<>()[]{}.,!?")
            lowered = part.lower()

            if "tenor.com/view/" in lowered:
                return part

            if "giphy.com/gifs/" in lowered:
                return part

            if "media.discordapp.net/" in lowered or "cdn.discordapp.com/" in lowered:
                return part

            if lowered.startswith(("http://", "https://")) and lowered.endswith(PREVIEW_URL_EXTENSIONS):
                return part

        return None

    def should_send_link_preview_message(self, url: Optional[str]) -> bool:
        if not url:
            return False

        lowered = url.lower()

        return (
            "tenor.com/view/" in lowered
            or "giphy.com/gifs/" in lowered
        )

    def format_attachments(
        self,
        message: nextcord.Message,
        previewed_names: Optional[set[str]] = None,
    ) -> str:
        if not message.attachments:
            return "None"

        previewed_names = previewed_names or set()
        lines = []

        for attachment in message.attachments:
            kind = self.attachment_kind(attachment)
            size_kb = attachment.size / 1024

            if kind == "image":
                label = "Image"
            elif kind == "gif":
                label = "GIF"
            elif kind == "video":
                label = "Video"
            else:
                label = "File"

            preview_text = " — `preview attached`" if attachment.filename in previewed_names else ""

            lines.append(
                f"• [{attachment.filename}]({self.attachment_url(attachment)}) "
                f"— `{label}` `{size_kb:.1f} KB`{preview_text}"
            )

        return self.clip("\n".join(lines), 1000)

    def format_raw_poll(
        self,
        poll: dict[str, Any],
    ) -> Optional[str]:
        """
        Clean poll logger from raw Discord gateway payloads.

        Logs:
        - question
        - single/multiple choice
        - end time
        - answer choices

        Vote counts are intentionally not logged because Discord/Nextcord may not
        reliably send live poll result updates.
        """
        if not poll:
            return None

        question = poll.get("question") or {}
        question_text = question.get("text") or "Unknown poll question"

        allow_multiselect = bool(poll.get("allow_multiselect", False))
        choice_type = "Multiple choice" if allow_multiselect else "Single choice"

        expiry = poll.get("expiry")

        answers = poll.get("answers") or []
        answer_lines: list[str] = []

        for index, answer in enumerate(answers, start=1):
            media = answer.get("poll_media") or {}
            answer_text = media.get("text") or f"Option {index}"

            emoji = media.get("emoji")
            emoji_text = ""

            if isinstance(emoji, dict):
                emoji_name = emoji.get("name")
                emoji_id = emoji.get("id")

                if emoji_id and emoji_name:
                    emoji_text = f"<:{emoji_name}:{emoji_id}> "
                elif emoji_name:
                    emoji_text = f"{emoji_name} "

            answer_lines.append(
                f"`{index}.` {emoji_text}**{answer_text}**"
            )

        lines = [
            "📊 **Poll Deleted**",
            f"**Question:** {question_text}",
            f"**Type:** {choice_type}",
        ]

        if expiry:
            lines.append(f"**Ends:** `{expiry}`")

        if answer_lines:
            lines.append("")
            lines.append("**Answers:**")
            lines.extend(answer_lines)

        return self.clip("\n".join(lines), 1000)

    def format_poll(self, message: nextcord.Message) -> Optional[str]:
        """
        Best-effort poll logger using nextcord's Message.poll if available.
        """
        poll = getattr(message, "poll", None)

        if poll is None:
            return None

        def get_any(obj, *names):
            for name in names:
                if isinstance(obj, dict) and name in obj:
                    return obj.get(name)

                value = getattr(obj, name, None)

                if value is not None:
                    return value

            return None

        lines: list[str] = []

        question = get_any(poll, "question", "title", "prompt")
        question_text = None

        if question is not None:
            if isinstance(question, str):
                question_text = question
            else:
                question_text = get_any(question, "text", "title", "label", "name")

                if question_text is None and isinstance(question, dict):
                    question_text = question.get("text") or question.get("title")

                if question_text is None:
                    question_text = str(question)

        if question_text:
            lines.append("📊 **Poll Deleted**")
            lines.append(f"**Question:** {question_text}")

        allow_multiselect = get_any(
            poll,
            "allow_multiselect",
            "allow_multiselects",
            "multiple",
            "multiselect",
            "allow_multiple",
        )

        if allow_multiselect is not None:
            choice_type = "Multiple choice" if bool(allow_multiselect) else "Single choice"
            lines.append(f"**Type:** {choice_type}")

        expires_at = get_any(poll, "expires_at", "expiry", "end_time", "ends_at")

        if isinstance(expires_at, datetime):
            lines.append(f"**Ends:** <t:{int(expires_at.timestamp())}:f>")
        elif expires_at:
            lines.append(f"**Ends:** `{expires_at}`")

        answers = get_any(poll, "answers", "options", "choices", "poll_answers") or []

        answer_lines: list[str] = []

        for index, answer in enumerate(answers, start=1):
            media = get_any(answer, "poll_media", "media")

            answer_text = None
            emoji = None

            if media is not None:
                answer_text = get_any(media, "text", "label", "name", "value")
                emoji = get_any(media, "emoji")

            if answer_text is None:
                answer_text = get_any(answer, "text", "label", "name", "value", "title")

            if emoji is None:
                emoji = get_any(answer, "emoji")

            if answer_text is None and isinstance(answer, dict):
                answer_text = (
                    answer.get("text")
                    or answer.get("label")
                    or answer.get("name")
                    or str(answer)
                )

            if answer_text is None:
                answer_text = str(answer)

            prefix = f"{emoji} " if emoji else ""

            answer_lines.append(
                f"`{index}.` {prefix}**{answer_text}**"
            )

        if answer_lines:
            lines.append("")
            lines.append("**Answers:**")
            lines.extend(answer_lines)

        if not lines:
            return "*Poll detected, but poll details were not exposed by nextcord.*"

        return self.clip("\n".join(lines), 1000)

    def message_content(self, message: nextcord.Message) -> str:
        cached_poll = self.poll_cache.pop(message.id, None)

        if cached_poll:
            formatted = self.format_raw_poll(cached_poll)

            if formatted:
                return formatted

            return "*Poll detected, but poll details could not be formatted.*"

        poll_text = self.format_poll(message)

        if poll_text:
            return poll_text

        content = message.content or ""

        if not content and message.embeds:
            content = "*No text content. Message had embed(s), a poll, or another special Discord message type.*"

        if not content and message.attachments:
            content = "*No text content. Message had attachment(s).*"

        if not content:
            content = "*No message content found.*"

        return self.clip(content, 3900)

    def attachment_signature(self, message: nextcord.Message) -> tuple:
        return tuple(
            (attachment.filename, attachment.size, attachment.content_type or "")
            for attachment in message.attachments
        )

    async def attachment_to_file(
        self,
        attachment: nextcord.Attachment,
        *,
        guild_filesize_limit: int,
    ) -> Optional[nextcord.File]:
        if attachment.size > guild_filesize_limit:
            return None

        try:
            return await attachment.to_file(use_cached=True)
        except Exception:
            pass

        try:
            data = await attachment.read(use_cached=True)

            if data:
                return nextcord.File(
                    io.BytesIO(data),
                    filename=attachment.filename,
                    spoiler=attachment.is_spoiler(),
                )
        except Exception:
            pass

        urls = []

        if attachment.proxy_url:
            urls.append(attachment.proxy_url)

        if attachment.url:
            urls.append(attachment.url)

        for url in urls:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status != 200:
                            continue

                        data = await response.read()

                        if not data:
                            continue

                        if len(data) > guild_filesize_limit:
                            continue

                        return nextcord.File(
                            io.BytesIO(data),
                            filename=attachment.filename,
                            spoiler=attachment.is_spoiler(),
                        )

            except Exception:
                continue

        return None

    async def external_direct_media_to_file(
        self,
        url: Optional[str],
        *,
        guild_filesize_limit: int,
    ) -> Optional[nextcord.File]:
        if not url:
            return None

        lowered = url.lower().split("?")[0]

        if not lowered.endswith((".gif", ".mp4", ".webm", ".mov", ".png", ".jpg", ".jpeg", ".webp")):
            return None

        if lowered.endswith(".gif"):
            filename = "deleted-link.gif"
        elif lowered.endswith(".mp4"):
            filename = "deleted-link.mp4"
        elif lowered.endswith(".webm"):
            filename = "deleted-link.webm"
        elif lowered.endswith(".mov"):
            filename = "deleted-link.mov"
        elif lowered.endswith(".png"):
            filename = "deleted-link.png"
        elif lowered.endswith(".webp"):
            filename = "deleted-link.webp"
        else:
            filename = "deleted-link.jpg"

        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0 Safari/537.36"
                )
            }

            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(url, timeout=15) as response:
                    if response.status != 200:
                        return None

                    content_length = response.headers.get("Content-Length")

                    if content_length and int(content_length) > guild_filesize_limit:
                        return None

                    data = await response.read()

            if not data:
                return None

            if len(data) > guild_filesize_limit:
                return None

            return nextcord.File(
                io.BytesIO(data),
                filename=filename,
            )

        except Exception:
            return None

    async def build_preview_files(
        self,
        log_channel: nextcord.TextChannel,
        attachments: list[nextcord.Attachment],
        *,
        limit: int = 4,
    ) -> tuple[list[nextcord.File], set[str]]:
        files: list[nextcord.File] = []
        previewed_names: set[str] = set()

        guild_limit = getattr(log_channel.guild, "filesize_limit", 8 * 1024 * 1024)

        for attachment in attachments:
            if not self.is_previewable_attachment(attachment):
                continue

            file = await self.attachment_to_file(
                attachment,
                guild_filesize_limit=guild_limit,
            )

            if file is None:
                continue

            files.append(file)
            previewed_names.add(attachment.filename)

            if len(files) >= limit:
                break

        return files, previewed_names

    async def find_message_deleter(
        self,
        message: nextcord.Message,
    ) -> Optional[nextcord.User | nextcord.Member]:
        guild = message.guild

        if guild is None:
            return None

        me = guild.me

        if me is None or not me.guild_permissions.view_audit_log:
            return None

        try:
            now = datetime.now(timezone.utc)

            async for entry in guild.audit_logs(
                limit=8,
                action=nextcord.AuditLogAction.message_delete,
            ):
                if entry.target is None:
                    continue

                if getattr(entry.target, "id", None) != message.author.id:
                    continue

                extra = entry.extra

                if getattr(extra, "channel", None) and extra.channel.id != message.channel.id:
                    continue

                if entry.created_at and now - entry.created_at > timedelta(seconds=15):
                    continue

                return entry.user

        except Exception:
            return None

        return None

    async def find_bulk_deleter(
        self,
        guild: nextcord.Guild,
        channel: nextcord.abc.GuildChannel,
    ) -> Optional[nextcord.User | nextcord.Member]:
        me = guild.me

        if me is None or not me.guild_permissions.view_audit_log:
            return None

        try:
            now = datetime.now(timezone.utc)

            async for entry in guild.audit_logs(
                limit=8,
                action=nextcord.AuditLogAction.message_bulk_delete,
            ):
                extra = entry.extra

                if getattr(extra, "channel", None) and extra.channel.id != channel.id:
                    continue

                if entry.created_at and now - entry.created_at > timedelta(seconds=30):
                    continue

                return entry.user

        except Exception:
            return None

        return None

    def deleted_message_jump_link(self, message: nextcord.Message) -> str:
        if message.guild:
            return f"https://discord.com/channels/{message.guild.id}/{message.channel.id}/{message.id}"

        return message.jump_url

    async def send_link_preview_if_needed(
        self,
        log_channel: nextcord.TextChannel,
        preview_url: Optional[str],
    ) -> None:
        if not preview_url:
            return

        if not self.should_send_link_preview_message(preview_url):
            return

        try:
            await log_channel.send(
                content=preview_url,
                allowed_mentions=nextcord.AllowedMentions.none(),
            )
        except Exception as exc:
            print(f"[ServerLog] Failed to send GIF/link preview message: {exc}")

    async def cache_poll_from_gateway_payload(self, payload: dict[str, Any]) -> None:
        event_type = payload.get("t")
        data = payload.get("d") or {}

        if event_type not in {"MESSAGE_CREATE", "MESSAGE_UPDATE"}:
            return

        message_id = data.get("id")
        poll = data.get("poll")

        if not message_id or not poll:
            return

        try:
            message_id_int = int(message_id)

            # Store the newest poll payload.
            self.poll_cache[message_id_int] = poll

            print(f"[ServerLog] Cached/refreshed poll for message {message_id}")
        except Exception as exc:
            print(f"[ServerLog] Failed to cache poll data: {exc}")

    @commands.Cog.listener()
    async def on_socket_response(self, payload: dict[str, Any]) -> None:
        await self.cache_poll_from_gateway_payload(payload)

    @commands.Cog.listener()
    async def on_socket_raw_receive(self, msg: str) -> None:
        try:
            payload = json.loads(msg)
        except Exception:
            return

        await self.cache_poll_from_gateway_payload(payload)

    @commands.Cog.listener()
    async def on_message_delete(self, message: nextcord.Message) -> None:
        if message.guild is None:
            return

        if message.author.bot:
            return

        log_channel = self.get_log_channel(message.guild)

        if log_channel is None:
            return

        if message.channel.id == log_channel.id:
            return

        deleted_by = await self.find_message_deleter(message)

        preview_files, previewed_names = await self.build_preview_files(
            log_channel,
            list(message.attachments),
        )

        preview_url = self.find_preview_url_in_content(message.content or "")

        external_file = None

        if preview_url and not self.should_send_link_preview_message(preview_url):
            guild_limit = getattr(log_channel.guild, "filesize_limit", 8 * 1024 * 1024)
            external_file = await self.external_direct_media_to_file(
                preview_url,
                guild_filesize_limit=guild_limit,
            )

        embed = nextcord.Embed(
            title="Message Deleted",
            color=self.bot.colors.get("red", nextcord.Color.red()),
            timestamp=datetime.now(timezone.utc),
        )

        embed.set_author(
            name=str(message.author),
            icon_url=message.author.display_avatar.url,
        )

        embed.description = (
            f"Message sent by {message.author.mention} deleted in {message.channel.mention} "
            f"[Jump to surrounding]({self.deleted_message_jump_link(message)})"
        )

        embed.add_field(
            name="Message Content",
            value=self.message_content(message),
            inline=False,
        )

        embed.add_field(
            name="Attachments",
            value=self.format_attachments(message, previewed_names),
            inline=False,
        )

        embed.add_field(
            name="Author",
            value=f"{message.author.mention} (`{message.author.id}`)",
            inline=True,
        )

        embed.add_field(
            name="Message ID",
            value=f"`{message.id}`",
            inline=True,
        )

        embed.add_field(
            name="Deleted At",
            value=f"<t:{int(datetime.now(timezone.utc).timestamp())}:f>",
            inline=True,
        )

        if deleted_by is not None and deleted_by.id != message.author.id:
            embed.add_field(
                name="Deleted By",
                value=f"{deleted_by.mention} (`{deleted_by.id}`)",
                inline=False,
            )

        first_visual = next(
            (
                attachment
                for attachment in message.attachments
                if self.is_visual_attachment(attachment)
            ),
            None,
        )

        if first_visual is not None:
            if first_visual.filename in previewed_names:
                embed.set_image(url=f"attachment://{first_visual.filename}")
            else:
                embed.set_image(url=self.attachment_url(first_visual))

        files_to_send: list[nextcord.File] = []

        if external_file is not None:
            files_to_send.append(external_file)

        files_to_send.extend(preview_files)

        await self.send_link_preview_if_needed(log_channel, preview_url)

        if files_to_send:
            await log_channel.send(embed=embed, files=files_to_send)
        else:
            await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages: list[nextcord.Message]) -> None:
        if not messages:
            return

        first = messages[0]

        if first.guild is None:
            return

        log_channel = self.get_log_channel(first.guild)

        if log_channel is None:
            return

        if first.channel.id == log_channel.id:
            return

        human_messages = [message for message in messages if not message.author.bot]

        if not human_messages:
            return

        deleted_by = await self.find_bulk_deleter(first.guild, first.channel)

        author_counts: dict[int, tuple[str, int]] = {}

        for message in human_messages:
            user_id = message.author.id
            username = str(message.author)

            if user_id not in author_counts:
                author_counts[user_id] = (username, 0)

            old_username, count = author_counts[user_id]
            author_counts[user_id] = (old_username, count + 1)

        if len(author_counts) == 1:
            username, count = next(iter(author_counts.values()))
            description = f"**{count}** messages from **{username}** were bulk deleted."
        else:
            lines = []

            for username, count in sorted(
                author_counts.values(),
                key=lambda item: item[1],
                reverse=True,
            )[:10]:
                lines.append(f"• **{username}**: `{count}` messages")

            description = (
                f"**{len(human_messages)}** messages from **{len(author_counts)} users** were bulk deleted.\n\n"
                + "\n".join(lines)
            )

        embed = nextcord.Embed(
            title="Bulk Message Delete",
            description=description,
            color=self.bot.colors.get("red", nextcord.Color.red()),
            timestamp=datetime.now(timezone.utc),
        )

        if deleted_by is not None:
            embed.add_field(
                name="Deleted By",
                value=f"{deleted_by.mention} (`{deleted_by.id}`)",
                inline=False,
            )

        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message_edit(
        self,
        before: nextcord.Message,
        after: nextcord.Message,
    ) -> None:
        if before.guild is None:
            return

        if before.author.bot:
            return

        log_channel = self.get_log_channel(before.guild)

        if log_channel is None:
            return

        if before.channel.id == log_channel.id:
            return

        content_changed = before.content != after.content
        attachments_changed = self.attachment_signature(before) != self.attachment_signature(after)

        if not content_changed and not attachments_changed:
            return

        preview_files, previewed_names = await self.build_preview_files(
            log_channel,
            list(after.attachments),
        )

        preview_url = self.find_preview_url_in_content(after.content or "")

        external_file = None

        if preview_url and not self.should_send_link_preview_message(preview_url):
            guild_limit = getattr(log_channel.guild, "filesize_limit", 8 * 1024 * 1024)
            external_file = await self.external_direct_media_to_file(
                preview_url,
                guild_filesize_limit=guild_limit,
            )

        before_content = before.content or "*No previous text content.*"
        after_content = after.content or "*No new text content.*"

        before_content = self.clip(before_content, 1800)
        after_content = self.clip(after_content, 1800)

        embed = nextcord.Embed(
            title="Message Edited",
            color=self.bot.colors.get("yellow", nextcord.Color.yellow()),
            timestamp=datetime.now(timezone.utc),
        )

        embed.set_author(
            name=str(before.author),
            icon_url=before.author.display_avatar.url,
        )

        embed.description = (
            f"Message sent by {before.author.mention} edited in {before.channel.mention} "
            f"[Jump to message]({after.jump_url})"
        )

        embed.add_field(
            name="Before",
            value=before_content,
            inline=False,
        )

        embed.add_field(
            name="After",
            value=after_content,
            inline=False,
        )

        if before.attachments or after.attachments:
            embed.add_field(
                name="Before Attachments",
                value=self.format_attachments(before),
                inline=False,
            )

            embed.add_field(
                name="After Attachments",
                value=self.format_attachments(after, previewed_names),
                inline=False,
            )

        embed.add_field(
            name="Author",
            value=f"{before.author.mention} (`{before.author.id}`)",
            inline=True,
        )

        embed.add_field(
            name="Message ID",
            value=f"`{before.id}`",
            inline=True,
        )

        embed.add_field(
            name="Edited At",
            value=f"<t:{int(datetime.now(timezone.utc).timestamp())}:f>",
            inline=True,
        )

        first_visual = next(
            (
                attachment
                for attachment in after.attachments
                if self.is_visual_attachment(attachment)
            ),
            None,
        )

        if first_visual is not None:
            if first_visual.filename in previewed_names:
                embed.set_image(url=f"attachment://{first_visual.filename}")
            else:
                embed.set_image(url=self.attachment_url(first_visual))

        files_to_send: list[nextcord.File] = []

        if external_file is not None:
            files_to_send.append(external_file)

        files_to_send.extend(preview_files)

        await self.send_link_preview_if_needed(log_channel, preview_url)

        if files_to_send:
            await log_channel.send(embed=embed, files=files_to_send)
        else:
            await log_channel.send(embed=embed)

    def colors(self, name: str, fallback: nextcord.Color) -> nextcord.Color | int:
        return getattr(self.bot, "colors", {}).get(name, fallback)

    def utcnow(self) -> datetime:
        return datetime.now(timezone.utc)

    def format_timestamp(self, value: Optional[datetime]) -> str:
        if value is None:
            return "Unknown"

        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)

        unix = int(value.timestamp())
        return f"<t:{unix}:F> (<t:{unix}:R>)"

    def format_entity(self, entity: Any, *, include_name: bool = False) -> str:
        if entity is None:
            return "Unknown"

        entity_id = getattr(entity, "id", None)
        mention = getattr(entity, "mention", None)

        if include_name and mention:
            value = f"{mention} ({entity})"
        else:
            value = mention or str(entity)

        if entity_id is None:
            return value

        return f"{value} (`{entity_id}`)"

    def format_channel(self, channel: Any) -> str:
        return self.format_entity(channel)

    def format_role(self, role: Any) -> str:
        return self.format_entity(role)

    def format_bool(self, value: Optional[bool]) -> str:
        if value is None:
            return "Unknown"

        return "Yes" if value else "No"

    def format_role_list(self, roles: Iterable[nextcord.Role], *, limit: int = 15) -> str:
        visible_roles = [
            role
            for role in roles
            if getattr(role, "name", None) != "@everyone"
        ]

        if not visible_roles:
            return "None"

        lines = [self.format_role(role) for role in visible_roles[:limit]]

        if len(visible_roles) > limit:
            lines.append(f"... and {len(visible_roles) - limit} more")

        return self.clip("\n".join(lines), 1000)

    def format_permission_names(self, permissions: nextcord.Permissions) -> str:
        important_permissions = (
            "administrator",
            "manage_guild",
            "manage_roles",
            "manage_channels",
            "manage_messages",
            "moderate_members",
            "ban_members",
            "kick_members",
            "mention_everyone",
            "view_audit_log",
        )
        enabled = [
            name.replace("_", " ").title()
            for name in important_permissions
            if getattr(permissions, name, False)
        ]

        if not enabled:
            return "No high-risk permissions enabled"

        return self.clip(", ".join(enabled), 1000)

    def diff_roles(
        self,
        before_roles: Iterable[nextcord.Role],
        after_roles: Iterable[nextcord.Role],
    ) -> tuple[list[nextcord.Role], list[nextcord.Role]]:
        before_by_id = {role.id: role for role in before_roles}
        after_by_id = {role.id: role for role in after_roles}

        added = [
            role
            for role_id, role in after_by_id.items()
            if role_id not in before_by_id
        ]
        removed = [
            role
            for role_id, role in before_by_id.items()
            if role_id not in after_by_id
        ]

        return added, removed

    def changed_text(self, before: Any, after: Any, attributes: tuple[tuple[str, str], ...]) -> str:
        lines: list[str] = []

        for attribute, label in attributes:
            before_value = getattr(before, attribute, None)
            after_value = getattr(after, attribute, None)

            if before_value == after_value:
                continue

            lines.append(f"**{label}:** `{before_value}` -> `{after_value}`")

        if not lines:
            return "No tracked fields changed."

        return self.clip("\n".join(lines), 1000)

    async def send_server_log(self, guild: nextcord.Guild, embed: nextcord.Embed) -> None:
        log_channel = self.get_log_channel(guild)

        if log_channel is None:
            return

        try:
            await log_channel.send(embed=embed)
        except Exception as exc:
            print(f"[ServerLog] Failed to send server log: {exc}")

    async def find_recent_audit_entry(
        self,
        guild: nextcord.Guild,
        action: Optional[nextcord.AuditLogAction],
        *,
        target_id: Optional[int] = None,
        channel_id: Optional[int] = None,
        seconds: int = 30,
    ) -> Optional[Any]:
        if action is None:
            return None

        me = guild.me

        if me is None or not me.guild_permissions.view_audit_log:
            return None

        now = self.utcnow()

        try:
            async for entry in guild.audit_logs(limit=8, action=action):
                if entry.created_at and now - entry.created_at > timedelta(seconds=seconds):
                    continue

                if target_id is not None and getattr(entry.target, "id", None) != target_id:
                    continue

                extra = getattr(entry, "extra", None)

                if channel_id is not None:
                    audit_channel = getattr(extra, "channel", None)

                    if audit_channel is not None and getattr(audit_channel, "id", None) != channel_id:
                        continue

                return entry
        except Exception as exc:
            print(f"[ServerLog] Failed to fetch audit log entry: {exc}")

        return None

    def add_audit_fields(self, embed: nextcord.Embed, entry: Optional[Any]) -> None:
        if entry is None:
            return

        user = getattr(entry, "user", None)
        reason = getattr(entry, "reason", None)

        if user is not None:
            embed.add_field(
                name="Responsible User",
                value=self.format_entity(user, include_name=True),
                inline=False,
            )

        if reason:
            embed.add_field(
                name="Reason",
                value=self.clip(str(reason), 1000),
                inline=False,
            )

    async def on_basic_audit_event(
        self,
        guild: nextcord.Guild,
        *,
        title: str,
        description: str,
        color: nextcord.Color | int,
        action: Optional[nextcord.AuditLogAction],
        target_id: Optional[int] = None,
        fields: Optional[list[tuple[str, str, bool]]] = None,
    ) -> None:
        entry = await self.find_recent_audit_entry(guild, action, target_id=target_id)

        embed = nextcord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=self.utcnow(),
        )

        for name, value, inline in fields or []:
            embed.add_field(name=name, value=value, inline=inline)

        self.add_audit_fields(embed, entry)
        await self.send_server_log(guild, embed)

    @commands.Cog.listener()
    async def on_member_join(self, member: nextcord.Member) -> None:
        embed = nextcord.Embed(
            title="Member Joined",
            description=f"{member.mention} joined the server.",
            color=self.colors("green", nextcord.Color.green()),
            timestamp=self.utcnow(),
        )
        embed.set_author(name=str(member), icon_url=member.display_avatar.url)
        embed.add_field(name="Member", value=self.format_entity(member, include_name=True), inline=False)
        embed.add_field(name="Account Created", value=self.format_timestamp(member.created_at), inline=False)
        await self.send_server_log(member.guild, embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: nextcord.Member) -> None:
        entry = await self.find_recent_audit_entry(
            member.guild,
            nextcord.AuditLogAction.kick,
            target_id=member.id,
            seconds=30,
        )

        title = "Member Kicked" if entry else "Member Left"
        description = (
            f"{member.mention} was kicked from the server."
            if entry
            else f"{member.mention} left the server."
        )

        embed = nextcord.Embed(
            title=title,
            description=description,
            color=self.colors("red", nextcord.Color.red()),
            timestamp=self.utcnow(),
        )
        embed.set_author(name=str(member), icon_url=member.display_avatar.url)
        embed.add_field(name="Member", value=self.format_entity(member, include_name=True), inline=False)
        embed.add_field(name="Roles", value=self.format_role_list(member.roles), inline=False)
        self.add_audit_fields(embed, entry)
        await self.send_server_log(member.guild, embed)

    @commands.Cog.listener()
    async def on_member_ban(self, guild: nextcord.Guild, user: nextcord.User) -> None:
        await self.on_basic_audit_event(
            guild,
            title="Member Banned",
            description=f"{self.format_entity(user, include_name=True)} was banned.",
            color=self.colors("red", nextcord.Color.red()),
            action=nextcord.AuditLogAction.ban,
            target_id=user.id,
        )

    @commands.Cog.listener()
    async def on_member_unban(self, guild: nextcord.Guild, user: nextcord.User) -> None:
        await self.on_basic_audit_event(
            guild,
            title="Member Unbanned",
            description=f"{self.format_entity(user, include_name=True)} was unbanned.",
            color=self.colors("green", nextcord.Color.green()),
            action=nextcord.AuditLogAction.unban,
            target_id=user.id,
        )

    @commands.Cog.listener()
    async def on_member_update(self, before: nextcord.Member, after: nextcord.Member) -> None:
        added_roles, removed_roles = self.diff_roles(before.roles, after.roles)

        if added_roles or removed_roles:
            entry = await self.find_recent_audit_entry(
                after.guild,
                nextcord.AuditLogAction.member_role_update,
                target_id=after.id,
            )

            embed = nextcord.Embed(
                title="Member Roles Updated",
                description=f"Roles changed for {after.mention}.",
                color=self.colors("blue", nextcord.Color.blue()),
                timestamp=self.utcnow(),
            )
            embed.set_author(name=str(after), icon_url=after.display_avatar.url)
            embed.add_field(name="Member", value=self.format_entity(after, include_name=True), inline=False)
            embed.add_field(name="Added Roles", value=self.format_role_list(added_roles), inline=False)
            embed.add_field(name="Removed Roles", value=self.format_role_list(removed_roles), inline=False)
            self.add_audit_fields(embed, entry)
            await self.send_server_log(after.guild, embed)

        if before.nick != after.nick:
            entry = await self.find_recent_audit_entry(
                after.guild,
                nextcord.AuditLogAction.member_update,
                target_id=after.id,
            )
            embed = nextcord.Embed(
                title="Nickname Changed",
                description=f"Nickname changed for {after.mention}.",
                color=self.colors("yellow", nextcord.Color.gold()),
                timestamp=self.utcnow(),
            )
            embed.set_author(name=str(after), icon_url=after.display_avatar.url)
            embed.add_field(name="Before", value=f"`{before.nick or before.name}`", inline=True)
            embed.add_field(name="After", value=f"`{after.nick or after.name}`", inline=True)
            self.add_audit_fields(embed, entry)
            await self.send_server_log(after.guild, embed)

        before_timeout = getattr(before, "communication_disabled_until", None)
        after_timeout = getattr(after, "communication_disabled_until", None)

        if before_timeout != after_timeout:
            entry = await self.find_recent_audit_entry(
                after.guild,
                nextcord.AuditLogAction.member_update,
                target_id=after.id,
            )
            embed = nextcord.Embed(
                title="Member Timeout Updated",
                description=f"Timeout status changed for {after.mention}.",
                color=self.colors("orange", nextcord.Color.orange()),
                timestamp=self.utcnow(),
            )
            embed.set_author(name=str(after), icon_url=after.display_avatar.url)
            embed.add_field(name="Before", value=self.format_timestamp(before_timeout), inline=False)
            embed.add_field(name="After", value=self.format_timestamp(after_timeout), inline=False)
            self.add_audit_fields(embed, entry)
            await self.send_server_log(after.guild, embed)

    def channel_type_name(self, channel: Any) -> str:
        return channel.__class__.__name__.replace("Channel", " Channel")

    def channel_update_details(self, before: nextcord.abc.GuildChannel, after: nextcord.abc.GuildChannel) -> str:
        changes = self.changed_text(
            before,
            after,
            (
                ("name", "Name"),
                ("topic", "Topic"),
                ("slowmode_delay", "Slowmode"),
                ("nsfw", "NSFW"),
                ("bitrate", "Bitrate"),
                ("user_limit", "User Limit"),
                ("position", "Position"),
                ("default_auto_archive_duration", "Default Archive Duration"),
            ),
        )

        extra_lines = []

        before_category = getattr(before, "category", None)
        after_category = getattr(after, "category", None)

        if before_category != after_category:
            extra_lines.append(
                f"**Category:** `{before_category}` -> `{after_category}`"
            )

        if getattr(before, "overwrites", None) != getattr(after, "overwrites", None):
            extra_lines.append("**Permission Overwrites:** changed")

        if changes == "No tracked fields changed." and not extra_lines:
            return changes

        if changes == "No tracked fields changed.":
            return self.clip("\n".join(extra_lines), 1000)

        if extra_lines:
            return self.clip(changes + "\n" + "\n".join(extra_lines), 1000)

        return changes

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: nextcord.abc.GuildChannel) -> None:
        await self.on_basic_audit_event(
            channel.guild,
            title="Channel Created",
            description=f"{self.format_channel(channel)} was created.",
            color=self.colors("green", nextcord.Color.green()),
            action=nextcord.AuditLogAction.channel_create,
            target_id=channel.id,
            fields=[("Type", self.channel_type_name(channel), True)],
        )

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: nextcord.abc.GuildChannel) -> None:
        await self.on_basic_audit_event(
            channel.guild,
            title="Channel Deleted",
            description=f"`#{channel.name}` was deleted.",
            color=self.colors("red", nextcord.Color.red()),
            action=nextcord.AuditLogAction.channel_delete,
            target_id=channel.id,
            fields=[("Type", self.channel_type_name(channel), True)],
        )

    @commands.Cog.listener()
    async def on_guild_channel_update(
        self,
        before: nextcord.abc.GuildChannel,
        after: nextcord.abc.GuildChannel,
    ) -> None:
        details = self.channel_update_details(before, after)

        if details == "No tracked fields changed.":
            return

        await self.on_basic_audit_event(
            after.guild,
            title="Channel Updated",
            description=f"{self.format_channel(after)} was updated.",
            color=self.colors("yellow", nextcord.Color.gold()),
            action=nextcord.AuditLogAction.channel_update,
            target_id=after.id,
            fields=[("Changes", details, False)],
        )

    @commands.Cog.listener()
    async def on_thread_create(self, thread: nextcord.Thread) -> None:
        if thread.guild is None:
            return

        await self.on_basic_audit_event(
            thread.guild,
            title="Thread Created",
            description=f"{self.format_channel(thread)} was created in {self.format_channel(thread.parent)}.",
            color=self.colors("green", nextcord.Color.green()),
            action=getattr(nextcord.AuditLogAction, "thread_create", None),
            target_id=thread.id,
        )

    @commands.Cog.listener()
    async def on_thread_delete(self, thread: nextcord.Thread) -> None:
        if thread.guild is None:
            return

        await self.on_basic_audit_event(
            thread.guild,
            title="Thread Deleted",
            description=f"`{thread.name}` was deleted.",
            color=self.colors("red", nextcord.Color.red()),
            action=getattr(nextcord.AuditLogAction, "thread_delete", None),
            target_id=thread.id,
        )

    @commands.Cog.listener()
    async def on_thread_update(self, before: nextcord.Thread, after: nextcord.Thread) -> None:
        details = self.changed_text(
            before,
            after,
            (
                ("name", "Name"),
                ("archived", "Archived"),
                ("locked", "Locked"),
                ("slowmode_delay", "Slowmode"),
                ("auto_archive_duration", "Auto Archive Duration"),
            ),
        )

        if details == "No tracked fields changed.":
            return

        await self.on_basic_audit_event(
            after.guild,
            title="Thread Updated",
            description=f"{self.format_channel(after)} was updated.",
            color=self.colors("yellow", nextcord.Color.gold()),
            action=getattr(nextcord.AuditLogAction, "thread_update", None),
            target_id=after.id,
            fields=[("Changes", details, False)],
        )

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: nextcord.Role) -> None:
        await self.on_basic_audit_event(
            role.guild,
            title="Role Created",
            description=f"{self.format_role(role)} was created.",
            color=self.colors("green", nextcord.Color.green()),
            action=nextcord.AuditLogAction.role_create,
            target_id=role.id,
            fields=[("Permissions", self.format_permission_names(role.permissions), False)],
        )

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: nextcord.Role) -> None:
        await self.on_basic_audit_event(
            role.guild,
            title="Role Deleted",
            description=f"`{role.name}` was deleted.",
            color=self.colors("red", nextcord.Color.red()),
            action=nextcord.AuditLogAction.role_delete,
            target_id=role.id,
            fields=[("Permissions", self.format_permission_names(role.permissions), False)],
        )

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: nextcord.Role, after: nextcord.Role) -> None:
        details = self.changed_text(
            before,
            after,
            (
                ("name", "Name"),
                ("color", "Color"),
                ("hoist", "Displayed Separately"),
                ("mentionable", "Mentionable"),
                ("position", "Position"),
            ),
        )

        if before.permissions != after.permissions:
            permission_before = self.format_permission_names(before.permissions)
            permission_after = self.format_permission_names(after.permissions)
            permission_line = f"**Permissions:** `{permission_before}` -> `{permission_after}`"

            if details == "No tracked fields changed.":
                details = permission_line
            else:
                details = details + "\n" + permission_line

            details = self.clip(
                details,
                1000,
            )

        if details == "No tracked fields changed.":
            return

        await self.on_basic_audit_event(
            after.guild,
            title="Role Updated",
            description=f"{self.format_role(after)} was updated.",
            color=self.colors("yellow", nextcord.Color.gold()),
            action=nextcord.AuditLogAction.role_update,
            target_id=after.id,
            fields=[("Changes", details, False)],
        )

    @commands.Cog.listener()
    async def on_guild_update(self, before: nextcord.Guild, after: nextcord.Guild) -> None:
        details = self.changed_text(
            before,
            after,
            (
                ("name", "Name"),
                ("verification_level", "Verification Level"),
                ("explicit_content_filter", "Explicit Content Filter"),
                ("mfa_level", "MFA Level"),
                ("afk_timeout", "AFK Timeout"),
            ),
        )

        if getattr(before, "afk_channel", None) != getattr(after, "afk_channel", None):
            afk_line = (
                f"**AFK Channel:** `{before.afk_channel}` -> `{after.afk_channel}`"
            )

            if details == "No tracked fields changed.":
                details = afk_line
            else:
                details += "\n" + afk_line

        if getattr(before, "system_channel", None) != getattr(after, "system_channel", None):
            system_line = (
                f"**System Channel:** `{before.system_channel}` -> `{after.system_channel}`"
            )

            if details == "No tracked fields changed.":
                details = system_line
            else:
                details += "\n" + system_line

        details = self.clip(details, 1000)

        if details == "No tracked fields changed.":
            return

        await self.on_basic_audit_event(
            after,
            title="Server Updated",
            description="Server settings were updated.",
            color=self.colors("yellow", nextcord.Color.gold()),
            action=nextcord.AuditLogAction.guild_update,
            target_id=after.id,
            fields=[("Changes", details, False)],
        )

    def summarize_named_object_changes(self, before: Iterable[Any], after: Iterable[Any]) -> tuple[list[Any], list[Any], list[tuple[Any, Any]]]:
        before_by_id = {item.id: item for item in before}
        after_by_id = {item.id: item for item in after}

        added = [
            item
            for item_id, item in after_by_id.items()
            if item_id not in before_by_id
        ]
        removed = [
            item
            for item_id, item in before_by_id.items()
            if item_id not in after_by_id
        ]
        renamed = [
            (before_by_id[item_id], after_by_id[item_id])
            for item_id in before_by_id.keys() & after_by_id.keys()
            if getattr(before_by_id[item_id], "name", None) != getattr(after_by_id[item_id], "name", None)
        ]

        return added, removed, renamed

    async def log_named_object_changes(
        self,
        guild: nextcord.Guild,
        *,
        title: str,
        object_label: str,
        before: Iterable[Any],
        after: Iterable[Any],
    ) -> None:
        added, removed, renamed = self.summarize_named_object_changes(before, after)

        if not added and not removed and not renamed:
            return

        lines = []

        for item in added[:10]:
            lines.append(f"**Added {object_label}:** `{item.name}` (`{item.id}`)")

        for item in removed[:10]:
            lines.append(f"**Removed {object_label}:** `{item.name}` (`{item.id}`)")

        for old_item, new_item in renamed[:10]:
            lines.append(
                f"**Renamed {object_label}:** `{old_item.name}` -> `{new_item.name}` (`{new_item.id}`)"
            )

        embed = nextcord.Embed(
            title=title,
            description=self.clip("\n".join(lines), 1000),
            color=self.colors("yellow", nextcord.Color.gold()),
            timestamp=self.utcnow(),
        )
        await self.send_server_log(guild, embed)

    @commands.Cog.listener()
    async def on_guild_emojis_update(
        self,
        guild: nextcord.Guild,
        before: list[nextcord.Emoji],
        after: list[nextcord.Emoji],
    ) -> None:
        await self.log_named_object_changes(
            guild,
            title="Server Emojis Updated",
            object_label="emoji",
            before=before,
            after=after,
        )

    @commands.Cog.listener()
    async def on_guild_stickers_update(
        self,
        guild: nextcord.Guild,
        before: list[nextcord.GuildSticker],
        after: list[nextcord.GuildSticker],
    ) -> None:
        await self.log_named_object_changes(
            guild,
            title="Server Stickers Updated",
            object_label="sticker",
            before=before,
            after=after,
        )

    @commands.Cog.listener()
    async def on_invite_create(self, invite: nextcord.Invite) -> None:
        guild = invite.guild

        if guild is None:
            return

        embed = nextcord.Embed(
            title="Invite Created",
            description=f"Invite `{invite.code}` was created.",
            color=self.colors("green", nextcord.Color.green()),
            timestamp=self.utcnow(),
        )
        embed.add_field(name="Channel", value=self.format_channel(invite.channel), inline=True)
        embed.add_field(name="Inviter", value=self.format_entity(invite.inviter, include_name=True), inline=True)
        embed.add_field(name="Max Uses", value=f"`{invite.max_uses or 'Unlimited'}`", inline=True)
        embed.add_field(name="Max Age", value=f"`{invite.max_age or 'Never expires'}`", inline=True)
        await self.send_server_log(guild, embed)

    @commands.Cog.listener()
    async def on_invite_delete(self, invite: nextcord.Invite) -> None:
        guild = invite.guild

        if guild is None:
            return

        await self.on_basic_audit_event(
            guild,
            title="Invite Deleted",
            description=f"Invite `{invite.code}` was deleted.",
            color=self.colors("red", nextcord.Color.red()),
            action=getattr(nextcord.AuditLogAction, "invite_delete", None),
            fields=[("Channel", self.format_channel(invite.channel), True)],
        )

    async def voice_audit_entry(
        self,
        member: nextcord.Member,
        action: Optional[nextcord.AuditLogAction],
        *,
        seconds: int = 8,
    ) -> Optional[Any]:
        return await self.find_recent_audit_entry(
            member.guild,
            action,
            target_id=member.id,
            seconds=seconds,
        )

    async def send_voice_log(
        self,
        member: nextcord.Member,
        *,
        title: str,
        description: str,
        color: nextcord.Color | int,
        entry: Optional[Any] = None,
    ) -> None:
        embed = nextcord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=self.utcnow(),
        )
        embed.set_author(name=str(member), icon_url=member.display_avatar.url)
        embed.add_field(name="Member", value=self.format_entity(member, include_name=True), inline=False)
        self.add_audit_fields(embed, entry)
        await self.send_server_log(member.guild, embed)

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: nextcord.Member,
        before: nextcord.VoiceState,
        after: nextcord.VoiceState,
    ) -> None:
        before_channel = before.channel
        after_channel = after.channel

        if before_channel is None and after_channel is not None:
            await self.send_voice_log(
                member,
                title="Voice Channel Joined",
                description=f"{member.mention} joined {self.format_channel(after_channel)}.",
                color=self.colors("green", nextcord.Color.green()),
            )
        elif before_channel is not None and after_channel is None:
            entry = await self.voice_audit_entry(
                member,
                nextcord.AuditLogAction.member_disconnect,
                seconds=8,
            )
            title = "Voice Channel Disconnected" if entry else "Voice Channel Left"
            description = (
                f"{member.mention} was disconnected from {self.format_channel(before_channel)}."
                if entry
                else f"{member.mention} left {self.format_channel(before_channel)}."
            )
            await self.send_voice_log(
                member,
                title=title,
                description=description,
                color=self.colors("red", nextcord.Color.red()),
                entry=entry,
            )
        elif before_channel is not None and after_channel is not None and before_channel != after_channel:
            entry = await self.voice_audit_entry(
                member,
                nextcord.AuditLogAction.member_move,
                seconds=8,
            )
            await self.send_voice_log(
                member,
                title="Voice Channel Moved",
                description=(
                    f"{member.mention} moved from {self.format_channel(before_channel)} "
                    f"to {self.format_channel(after_channel)}."
                ),
                color=self.colors("blue", nextcord.Color.blue()),
                entry=entry,
            )

        voice_flags = (
            ("mute", "Server Muted", "Server Unmuted"),
            ("deaf", "Server Deafened", "Server Undeafened"),
            ("self_stream", "Started Streaming", "Stopped Streaming"),
            ("self_video", "Camera Enabled", "Camera Disabled"),
            ("suppress", "Suppressed", "Unsuppressed"),
        )

        for attribute, enabled_title, disabled_title in voice_flags:
            before_value = getattr(before, attribute, None)
            after_value = getattr(after, attribute, None)

            if before_value == after_value:
                continue

            entry = None

            if attribute in {"mute", "deaf", "suppress"}:
                entry = await self.voice_audit_entry(
                    member,
                    nextcord.AuditLogAction.member_update,
                    seconds=8,
                )

            title = enabled_title if after_value else disabled_title
            channel = after_channel or before_channel
            description = f"{member.mention}: {title.lower()}."

            if channel is not None:
                description += f"\nChannel: {self.format_channel(channel)}"

            await self.send_voice_log(
                member,
                title=title,
                description=description,
                color=self.colors("orange", nextcord.Color.orange()),
                entry=entry,
            )


def setup(bot: APBot) -> None:
    bot.add_cog(ServerLog(bot))
