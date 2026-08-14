from __future__ import annotations

import io
import json
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

import aiohttp
import nextcord
from nextcord.ext import commands

from bot_base import APBot
from cogs.server_log.base import resolve_log_channel


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


class DeleteLog(commands.Cog):
    def __init__(self, bot: APBot) -> None:
        self.bot = bot

        # message_id -> raw poll payload
        self.poll_cache: dict[int, dict[str, Any]] = {}

    def get_log_channel(self, guild: nextcord.Guild) -> Optional[nextcord.TextChannel]:
        # Shared with the cogs.server_log cogs so `server_log_channel_id` moves
        # every server log at once, falling back to the `server-log` channel.
        return resolve_log_channel(self.bot, guild)

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
            print(f"[DeleteLog] Failed to send GIF/link preview message: {exc}")

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

            print(f"[DeleteLog] Cached/refreshed poll for message {message_id}")
        except Exception as exc:
            print(f"[DeleteLog] Failed to cache poll data: {exc}")

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


def setup(bot: APBot) -> None:
    bot.add_cog(DeleteLog(bot))
