"""Ban appeals: persistent deadlines, staff voting and bounded applicant updates."""
import asyncio
import hashlib
import logging
import time
from datetime import datetime, timezone

import nextcord
from nextcord import ButtonStyle, Embed, Interaction, Object, TextInputStyle, ui, slash_command
from nextcord.ext import commands

from bot_base import APBot
from config_handler import Config
from utils.appeal_policy import (AppealPolicy, PROD_COOLDOWN, PROD_REVIEW, PROD_REMINDER, deadline, reminder_at,
                                 reminder_due, reappeal_at, vote_result, duration_text, previous_appeals,
                                 moderator_role, eligible_voter)

log = logging.getLogger(__name__)
conf = Config("config.json")
APPEAL_GUILD_IDS = [int(conf.get("ban_appeal_server"))] if conf.get("ban_appeal_server") else []


def none_mentions():
    return nextcord.AllowedMentions.none()


def ban_fingerprint(ban):
    return hashlib.sha256(str(ban.reason or "").encode("utf-8")).hexdigest()


def clean(value, limit):
    return str(value or "").replace("\x00", "").strip()[:limit]


def appeal_code_block(value, limit):
    """Render applicant text literally inside a Discord fenced code block."""
    text = clean(value, limit)
    # Separate adjacent pairs so user-supplied backticks cannot close the fence.
    text = text.replace("``", "``\u200b")
    # Discord limits field values to 1024 characters, including the fence.
    if len(text) > 1016:
        text = text[:1015] + "…"
    return f"```\n{text}\n```"


class AppealService:
    def __init__(self, bot):
        self.bot = bot
        self.collection = bot.db.appeal.ban_appeals
        self.policy = AppealPolicy.load(bot.config, bot.db.appeal.database.name)
        self.main_id = int(bot.config.get("guild_id"))
        self.appeal_id = int(bot.config.get("ban_appeal_server"))
        self.channel_id = int(bot.config.get("appeals_channel_id"))
        if getattr(bot, "_appeal_decision_lock", None) is None:
            bot._appeal_decision_lock = asyncio.Lock()
        self.lock = bot._appeal_decision_lock

    async def environment(self):
        if self.bot.user.id != self.policy.application_id:
            raise RuntimeError("Bot identity does not match application_id; appeal processing disabled")
        guild = self.bot.get_guild(self.main_id)
        channel = await self.bot.getch_channel(self.channel_id)
        if guild is None or not channel or channel.guild.id != guild.id:
            raise RuntimeError("Appeal staff channel not in configured main guild")
        if channel.permissions_for(guild.default_role).view_channel:
            raise RuntimeError("Appeal staff channel is visible to @everyone")
        if self.bot.get_guild(self.appeal_id) is None:
            raise RuntimeError("Bot is not in the configured appeal server")
        role = moderator_role(guild)
        return guild, channel, role

    def belongs(self, record):
        # Legacy production records had no guild/channel metadata.
        if self.policy.testing and (record.get("guild_id") != self.main_id or record.get("channel_id") != self.channel_id):
            return False
        return (record.get("guild_id", self.main_id) == self.main_id
                and record.get("channel_id", self.channel_id) == self.channel_id)

    async def lookup(self, uid):
        return await self.collection.find_one({"user_id": uid}) or {}

    async def current_ban(self, guild, uid):
        try:
            return await guild.fetch_ban(Object(id=uid))
        except nextcord.NotFound as exc:
            if exc.code != 10026:
                raise
            return None

    async def thread_for(self, message, channel):
        thread = message.thread or channel.guild.get_thread(message.id)
        if thread is None:
            try:
                thread = await self.bot.fetch_channel(message.id)
            except nextcord.NotFound:
                return None
        if getattr(thread, "parent_id", None) != channel.id:
            raise RuntimeError("Appeal thread parent mismatch")
        return thread

    async def history(self, thread, uid, prior):
        # The message snowflake preserves its creation time even for legacy records.
        # Only use records from this staff channel, deduplicated by message ID.
        records = {}
        for row in prior:
            if row.get("channel_id") != self.channel_id:
                continue
            raw_id = row.get("message_id")
            if isinstance(raw_id, bool) or not isinstance(raw_id, (str, int)):
                continue
            try:
                message_id = int(raw_id)
            except ValueError:
                continue
            if not 0 < message_id < (1 << 64):
                continue
            records[message_id] = row
        ordered = sorted(records, reverse=True)
        total = len(ordered)
        if total:
            noun = "appeal" if total == 1 else "appeals"
            lines = [f"{total} previous {noun} on record."]
            for index, message_id in enumerate(ordered[:8]):
                decision = records[message_id].get("decision")
                status = ("🟢 Accepted" if decision is True else
                          "🔴 Rejected" if decision is False else "⚪ Closed/unknown")
                submitted = ((message_id >> 22) + 1420070400000) // 1000
                url = f"https://discord.com/channels/{self.main_id}/{self.channel_id}/{message_id}"
                lines.append(f"**#{total - index} • {status}**\nSubmitted: <t:{submitted}:D>\n[View previous appeal]({url})")
            if total > 8:
                lines.append(f"*+{total - 8} older {'appeal' if total - 8 == 1 else 'appeals'} not shown.*")
            description = "\n\n".join(lines)
        else:
            description = "No previous appeals recorded by this system."
        # Keep the standard /warnings output separate and unchanged.
        emb = Embed(title="Previous Appeals", description=description,
                    color=self.bot.colors["light_orange"])
        await thread.send(embed=emb, allowed_mentions=none_mentions())
        try:
            warnings = self.bot.get_cog("Infraction")
            if warnings is None:
                raise RuntimeError("Infraction cog not loaded")
            await warnings.post_appeal_warnings(thread, uid, self.bot.get_guild(self.main_id))
        except Exception:
            log.exception("Could not post moderation history for appeal %s", uid)
            await thread.send("Could not display the full moderation history. Staff should check /warnings manually.", allowed_mentions=none_mentions())

    def submission_block_reason(self, record, now):
        if record and not self.belongs(record):
            return "Your appeal record belongs to a different environment. Contact staff."
        if record.get("message_id") and record.get("decision") is None:
            return "Your last appeal is still being considered. Use Add Information to submit an update."
        until = reappeal_at(record)
        if until is not None and now < until:
            return f"Your previous appeal was denied. You may appeal again <t:{int(until)}:R> (<t:{int(until)}:F>)."
        return None

    async def submission_preflight(self, inter):
        """Read-only eligibility check before opening a modal; submit rechecks under lock."""
        if inter.guild_id != self.appeal_id:
            return "Please submit in the configured appeal server."
        guild, _, _ = await self.environment()
        if await self.current_ban(guild, inter.user.id) is None:
            return "You are not currently banned from the main server."
        record = await self.lookup(inter.user.id)
        return self.submission_block_reason(record, time.time())

    async def submit(self, inter, appeal, media, misc):
        if inter.guild_id != self.appeal_id:
            return "Please submit in the configured appeal server."
        async with self.lock:
            guild, channel, _ = await self.environment()
            uid = inter.user.id
            current_ban = await self.current_ban(guild, uid)
            if current_ban is None:
                return "You are not currently banned from the main server."
            record = await self.lookup(uid)
            now = time.time()
            blocked = self.submission_block_reason(record, now)
            if blocked is not None:
                return blocked
            prior = previous_appeals(record, self.channel_id)
            snapshot = self.policy.snapshot(now)
            emb = Embed(title="Ban Appeal", color=self.bot.colors["light_orange"], timestamp=datetime.now(timezone.utc))
            emb.add_field(name="User Info", value=f"User: {clean(inter.user, 100)}\nID: {uid}", inline=False)
            emb.add_field(name="Ban Appeal", value=appeal_code_block(appeal, 750), inline=False)
            if media.strip():
                emb.add_field(name="Supporting Media", value=appeal_code_block(media, 150), inline=False)
            if misc.strip():
                emb.add_field(name="Additional Information", value=appeal_code_block(misc, 750), inline=False)
            emb.add_field(name="Decision deadline", value=f"<t:{int(snapshot['deadline_at'])}:F> (<t:{int(snapshot['deadline_at'])}:R>)", inline=False)
            message = await channel.send(embed=emb, allowed_mentions=none_mentions())
            try:
                await message.add_reaction("🟢")
                await message.add_reaction("🟡")
                await message.add_reaction("🔴")
                thread = await message.create_thread(name=f"{datetime.now(timezone.utc):%m/%d/%Y} - {clean(inter.user.name, 65)}")
            except Exception:
                try:
                    await message.delete()
                except Exception:
                    log.exception("Could not clean up incomplete appeal message %s", message.id)
                raise
            fields = {"user_id":uid, "submission_time":now, "message_id":message.id, "decision":None,
                      "guild_id":self.main_id, "channel_id":self.channel_id, "thread_id":thread.id,
                      "previous_appeals":prior, "updates_count":0, "ban_fingerprint":ban_fingerprint(current_ban), **snapshot}
            # Never reset an existing active appeal. Single-process lock protects callbacks.
            await self.collection.update_one({"user_id":uid}, {"$set":fields, "$unset":{
                "reminder_claimed_at":"", "reminder_checked_at":"", "reappeal_at":"", "decided_at":"", "last_update_at":"", "hold_reason":""}}, upsert=True)
        # History may involve Discord API calls; don't block unrelated decisions or updates.
        try:
            await self.history(thread, uid, prior)
        except Exception:
            log.exception("Failed to post history for appeal %s", message.id)
        return f"Your appeal has been sent. Its decision is scheduled for <t:{int(snapshot['deadline_at'])}:F> (<t:{int(snapshot['deadline_at'])}:R>)."

    async def add_information(self, inter, expected_id, information):
        if inter.guild_id != self.appeal_id:
            return "Please use the configured appeal server."
        async with self.lock:
            _, channel, _ = await self.environment()
            record = await self.lookup(inter.user.id)
            now = time.time()
            if (not record or not self.belongs(record) or record.get("message_id") != expected_id
                    or record.get("decision") is not None or now >= deadline(record)):
                return "That appeal is no longer open for updates."
            if record.get("updates_count", 0) >= 5:
                return "You have reached the limit of five updates. Contact staff if necessary."
            if now - record.get("last_update_at", 0) < 60:
                return "Please wait one minute between updates."
            message = await channel.fetch_message(expected_id)
            thread = await self.thread_for(message, channel)
            if thread is None or thread.locked:
                return "The appeal discussion is unavailable. Contact staff."
            # Claim before sending; this prevents retries from spamming during an uncertain send.
            result = await self.collection.update_one({"user_id":inter.user.id, "message_id":expected_id, "decision":None},
                {"$set":{"last_update_at":now}, "$inc":{"updates_count":1}})
            if not result.modified_count:
                return "That appeal is no longer open."
            try:
                emb = Embed(title="Ban Appeal Update", color=self.bot.colors["light_orange"],
                            timestamp=datetime.now(timezone.utc))
                emb.add_field(name="User Info", value=f"User: {clean(inter.user, 100)}\nID: {inter.user.id}", inline=False)
                emb.add_field(name="Additional Information", value=appeal_code_block(information, 1000), inline=False)
                emb.add_field(name="Decision deadline", value=f"<t:{int(deadline(record))}:F> (<t:{int(deadline(record))}:R>)", inline=False)
                await thread.send(embed=emb, allowed_mentions=none_mentions())
            except Exception:
                log.exception("Appeal update delivery uncertain for %s", expected_id)
                return "The update could not be confirmed. Contact staff before retrying. Your deadline has not changed."
            return f"Your update was added. The original deadline remains <t:{int(deadline(record))}:F>."

    async def ballots(self, message, guild):
        choices = {"🟢":set(), "🔴":set(), "🟡":set()}
        eligibility = {}
        for reaction in message.reactions:
            emoji = str(reaction.emoji)
            if emoji not in choices:
                continue
            async for user in reaction.users():
                if user.bot:
                    continue
                if user.id not in eligibility:
                    member = guild.get_member(user.id)
                    if member is None:
                        try:
                            member = await guild.fetch_member(user.id)
                        except nextcord.NotFound:
                            eligibility[user.id] = False
                            continue
                    eligibility[user.id] = eligible_voter(member)
                if eligibility[user.id]:
                    choices[emoji].add(user.id)
        return vote_result(choices["🟢"], choices["🔴"], choices["🟡"])

    async def process(self, uid, mid):
        async with self.lock:
            record = await self.lookup(uid)
            if (record.get("message_id") != mid or record.get("decision") is not None
                    or not self.belongs(record) or record.get("hold_reason")):
                return
            now = time.time()
            due = now >= deadline(record)
            if not due and (record.get("reminder_checked_at") or record.get("reminder_claimed_at") or now < reminder_at(record)):
                return
            guild, channel, role = await self.environment()
            try:
                message = await channel.fetch_message(mid)
            except nextcord.NotFound as exc:
                if exc.code != 10008:
                    raise
                await self.collection.update_one({"user_id":uid,"message_id":mid,"decision":None},
                    {"$set":{"hold_reason":"Appeal message missing; staff review required"}})
                log.error("Appeal %s missing; held for staff review, no automatic decision", mid)
                return
            if message.author.id != self.bot.user.id:
                log.error("Appeal %s does not belong to this bot; skipping", mid)
                return
            accepted, voters = await self.ballots(message, guild)
            thread = await self.thread_for(message, channel)
            now = time.time()
            if now < deadline(record):
                if voters > record.get("reminder_max_votes", 3):
                    await self.collection.update_one({"user_id":uid,"message_id":mid,"decision":None},
                        {"$set":{"reminder_checked_at":now}})
                    return
                if not reminder_due(record, now, voters) or thread is None or thread.locked:
                    return
                claim = await self.collection.update_one({"user_id":uid,"message_id":mid,"decision":None,
                    "reminder_claimed_at":{"$exists":False}}, {"$set":{"reminder_claimed_at":now, "reminder_checked_at":now}})
                if claim.modified_count:
                    # Claim persists across restart; intentionally no duplicate ping on ambiguous network errors.
                    participation = ("No staff members have voted on this appeal yet." if voters == 0 else
                        "Only **1 staff member** has voted on this appeal so far." if voters == 1 else
                        f"Only **{voters} staff members** have voted on this appeal so far.")
                    await thread.send(f"{role.mention} {participation} Please review the appeal and cast your vote before it closes <t:{int(deadline(record))}:R>.",
                        allowed_mentions=nextcord.AllowedMentions(everyone=False, users=False, roles=[role], replied_user=False))
                return
            # Preserve majority rule and the earlier Unknown Ban fix.
            ban = await self.current_ban(guild, uid)
            if ban is not None and record.get("ban_fingerprint") and record["ban_fingerprint"] != ban_fingerprint(ban):
                await self.collection.update_one({"user_id":uid,"message_id":mid,"decision":None},
                    {"$set":{"hold_reason":"Ban reason changed since submission; staff review required"}})
                if thread is not None:
                    await thread.send("Automatic decision paused: the ban reason changed after submission. Staff review required.", allowed_mentions=none_mentions())
                return
            already_unbanned = ban is None
            lifted = False
            if accepted and not already_unbanned:
                try:
                    await guild.unban(Object(id=uid), reason=f"Ban appeal {mid} accepted")
                    lifted = True
                except nextcord.NotFound as exc:
                    if exc.code != 10026:
                        raise
                    already_unbanned = True
            accepted = accepted or already_unbanned
            decided = time.time()
            fields = {"decision":accepted, "decided_at":decided, "submission_time":decided}
            if not accepted:
                fields["reappeal_at"] = decided + record.get("cooldown_seconds", PROD_COOLDOWN)
            result = await self.collection.update_one({"user_id":uid,"message_id":mid,"decision":None}, {"$set":fields})
            if not result.modified_count:
                return
            if lifted or not accepted:
                try:
                    user = await self.bot.getch_user(uid)
                    if user:
                        title = "Ban Lifted." if lifted else "Ban Appeal Denied."
                        desc = "Your ban has been lifted. Welcome back!" if lifted else f"Your appeal was denied. You may appeal again <t:{int(fields['reappeal_at'])}:R> (<t:{int(fields['reappeal_at'])}:F>)."
                        await user.send(embed=Embed(title=title, description=desc, color=self.bot.colors["green" if lifted else "red"]), allowed_mentions=none_mentions())
                except Exception:
                    log.exception("Decision recorded; DM delivery failed for appeal %s", mid)
            if thread is not None:
                try:
                    text = "Member already unbanned; appeal closed." if already_unbanned else ("Member unbanned." if accepted else "Member will remain banned.")
                    await thread.send(embed=Embed(title="Appeal decision", description=text, color=self.bot.colors["green" if accepted else "red"]), allowed_mentions=none_mentions())
                    await thread.edit(archived=True, locked=True)
                except Exception:
                    log.exception("Decision recorded; staff thread update failed for appeal %s", mid)

    async def tick(self):
        # Cursor instead of one timer/task per appeal. Legacy records use original production deadlines.
        now = time.time()
        query = {"decision":None,"message_id":{"$exists":True,"$ne":None},"hold_reason":{"$exists":False},
            "$or":[{"deadline_at":{"$lte":now}},
                    {"reminder_at":{"$lte":now}, "reminder_checked_at":{"$exists":False}},
                    {"deadline_at":{"$exists":False}, "submission_time":{"$lte":now-PROD_REVIEW}},
                    {"deadline_at":{"$exists":False}, "reminder_checked_at":{"$exists":False},
                     "submission_time":{"$lte":now-PROD_REVIEW+PROD_REMINDER}}]}
        async for row in self.collection.find(query, {"user_id":1,"message_id":1}):
            try:
                await self.process(row["user_id"], row["message_id"])
            except Exception:
                log.exception("Appeal processing failed; retry on next scan: %s", row.get("message_id"))

    async def worker(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                await self.tick()
            except Exception:
                log.exception("Appeal scan failed; will retry")
            await asyncio.sleep(self.policy.poll)


class BanAppealModal(ui.Modal):
    def __init__(self, service):
        self.service = service
        super().__init__(title="Ban Appeal", custom_id="appeal_modal", timeout=600)
        self.appeal = ui.TextInput(label="Ban Appeal", style=TextInputStyle.paragraph, min_length=100, max_length=750, required=True)
        self.media = ui.TextInput(label="Supporting Media", style=TextInputStyle.paragraph, required=False, max_length=150)
        self.misc = ui.TextInput(label="Anything else?", style=TextInputStyle.paragraph, required=False, max_length=750)
        for item in (self.appeal, self.media, self.misc):
            self.add_item(item)

    async def callback(self, inter: Interaction):
        await inter.response.defer(ephemeral=True, with_message=True)
        try:
            reply = await self.service.submit(inter, self.appeal.value, self.media.value or "", self.misc.value or "")
        except Exception:
            log.exception("Appeal submission failed")
            reply = "Your submission could not be confirmed. Please contact staff before retrying."
        await inter.followup.send(reply, ephemeral=True)


class AppealUpdateModal(ui.Modal):
    def __init__(self, service, message_id):
        self.service, self.message_id = service, message_id
        super().__init__(title="Add appeal information", timeout=600)
        self.info = ui.TextInput(label="Additional information", style=TextInputStyle.paragraph, min_length=10, max_length=1000, required=True)
        self.add_item(self.info)

    async def callback(self, inter: Interaction):
        await inter.response.defer(ephemeral=True, with_message=True)
        try:
            reply = await self.service.add_information(inter, self.message_id, self.info.value)
        except Exception:
            log.exception("Appeal update failed")
            reply = "Your update could not be confirmed. Please contact staff."
        await inter.followup.send(reply, ephemeral=True)


class BanAppealView(ui.View):
    def __init__(self, service):
        self.service = service
        super().__init__(timeout=None)

    @ui.button(label="Appeal Ban", style=ButtonStyle.blurple, custom_id="appeal")
    async def callback(self, button: ui.Button, inter: Interaction):
        if inter.guild_id != self.service.appeal_id:
            return await inter.response.send_message("Use the configured appeal server.", ephemeral=True)
        try:
            # Discord requires a prompt initial interaction response. Do not defer a modal.
            blocked = await asyncio.wait_for(self.service.submission_preflight(inter), timeout=2.0)
            if blocked is not None:
                return await inter.response.send_message(blocked, ephemeral=True)
            await inter.response.send_modal(BanAppealModal(self.service))
        except asyncio.TimeoutError:
            if not inter.response.is_done():
                await inter.response.send_message("Could not check your appeal eligibility in time. Please try again.", ephemeral=True)
        except Exception:
            log.exception("Could not open ban appeal modal")
            if not inter.response.is_done():
                await inter.response.send_message("Could not check your appeal eligibility. Please try again or contact staff.", ephemeral=True)

    @ui.button(label="Add Information", style=ButtonStyle.gray, custom_id="appeal_add_information_v1")
    async def add_information(self, button: ui.Button, inter: Interaction):
        if inter.guild_id != self.service.appeal_id:
            return await inter.response.send_message("Use the configured appeal server.", ephemeral=True)
        try:
            record = await asyncio.wait_for(self.service.lookup(inter.user.id), timeout=1.5)
            if (not record.get("message_id") or record.get("decision") is not None
                    or not self.service.belongs(record) or time.time() >= deadline(record)):
                return await inter.response.send_message("You do not have an open appeal.", ephemeral=True)
            await inter.response.send_modal(AppealUpdateModal(self.service, record["message_id"]))
        except Exception:
            log.exception("Could not open appeal update modal")
            if not inter.response.is_done():
                await inter.response.send_message("Could not open your appeal. Please try again.", ephemeral=True)


class BanAppeal(commands.Cog):
    def __init__(self, bot: APBot):
        self.bot = bot
        self.service = AppealService(bot)
        self.view = BanAppealView(self.service)
        self.task = bot.loop.create_task(self.start())

    async def start(self):
        await self.bot.wait_until_ready()
        try:
            await self.service.environment()
        except Exception:
            log.exception("Appeal environment failed safety checks; restart after correcting configuration")
            return
        self.bot.add_view(self.view)
        print(f"Appeals ready: database={self.bot.db.appeal.database.name} "
              f"moderation_database={self.bot.db.base_db.database.name} "
              f"testing={self.service.policy.testing} review={self.service.policy.review}s "
              f"reminder={self.service.policy.reminder}s cooldown={self.service.policy.cooldown}s")
        await self.service.worker()

    def cog_unload(self):
        self.task.cancel()
        self.view.stop()

    @slash_command(name="appealbutton", default_member_permissions=0x8, guild_ids=APPEAL_GUILD_IDS)
    async def send_appeal_button(self, inter: Interaction):
        if inter.guild_id != self.service.appeal_id:
            return await inter.send("Use the configured appeal server.", ephemeral=True)
        await self.service.environment()
        p = self.service.policy
        await inter.send(embed=Embed(title="Ban Appeal", description=(
            "**To begin the appeal process, click Appeal Ban.**\n\n"
            f"Appeals are reviewed **{duration_text(p.review)} after submission**. "
            "Use Add Information to provide additional details while your appeal is open. This does not change the deadline.\n\n"
            f"**Decisions are automated.** If rejected, you may appeal again after **{duration_text(p.cooldown)}**."),
            color=self.bot.colors["blue"]), view=BanAppealView(self.service))


def setup(bot: APBot):
    bot.add_cog(BanAppeal(bot))
