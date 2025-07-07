import nextcord
from nextcord.ext import commands
from bot_base import APBot
from nextcord import Interaction, SelectOption, SlashOption, slash_command, TextInputStyle
from collections import defaultdict
from nextcord.ui import Select, View, Modal, TextInput, Button
from nextcord import Embed 
import logging

logger = logging.getLogger(__name__)


class Recurrent(commands.Cog):
    def __init__(self, bot: APBot):
        self.bot = bot
        self.message_count_cache = defaultdict(int)
        self.category_message_count_cache = defaultdict(lambda: defaultdict(int))  
        self.activity_threshold = 10  
        self.category_threshold = 10  
    def _is_authorized(self, inter: Interaction) -> bool:
        is_admin = any(role.name == "Admin" for role in inter.user.roles)
        is_specific_user  = inter.user.id == 707985260020760628
        return is_admin or is_specific_user

    @slash_command(name="recurrent", description="Manage recurring messages")
    async def _recurrent(self, inter: Interaction):
        await inter.response.send_message("Use subcommands to manage recurring messages.", ephemeral=True) 
        
    @_recurrent.subcommand(name="add", description="Add a recurring message to a channel")
    async def _recurrent_add(
        self,
        inter: Interaction,
        channel_id: str = SlashOption(description="ID of the channel where the message will be sent", required=True),
        message: str = SlashOption(description="Message to send", required=True),
        limit: int = SlashOption(description="Message count limit before sending a recurring message", required=True),
    ):
        if not self._is_authorized(inter):
            await inter.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return

        try:
            await inter.response.defer()
            channel_id = int(channel_id)
            channel = self.bot.get_channel(channel_id)
            if not channel:
                await inter.followup.send(f"Channel ID {channel_id} not found.")
                return

            self.activity_threshold = limit
            await self.bot.db.recurrent.add_message(channel_id, message, limit)

            # ✅ Send the message immediately
            await channel.send(embed=Embed(description=message))

            await inter.followup.send(
                f"Recurring message added and message sent immediately to <#{channel_id}> with limit {limit}."
            )
        except ValueError:
            await inter.followup.send("Invalid channel ID provided.")
        except Exception as e:
            await inter.followup.send(f"Error adding recurring message: {e}")




    @_recurrent.subcommand(name="list", description="List all recurring messages in a channel")
    async def _recurrent_list(
        self,
        inter: Interaction,
        channel_id: str = SlashOption(description="ID of the channel to list messages from", required=True)
    ):
        # ✅ Permission check at the top of the function
        if not self._is_authorized(inter):
            await inter.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return

        try:
            await inter.response.defer()
            channel_id = int(channel_id)
            messages = await self.bot.db.recurrent.get_messages(channel_id)
            if not messages:
                await inter.followup.send(f"No recurring messages found for channel <#{channel_id}>.")
                return

            message_list = "\n".join([f"{idx + 1}: {msg}" for idx, msg in enumerate(messages)])
            await inter.followup.send(f"Recurring messages for channel <#{channel_id}>:\n{message_list}")

        except ValueError:
            await inter.followup.send("Invalid channel ID provided.")
        except Exception as e:
            await inter.followup.send(f"Error listing recurring messages: {e}")

    @_recurrent.subcommand(name="remove", description="Remove a recurring message by index")
    async def _recurrent_remove(
        self,
        inter: Interaction,
        channel_id: str = SlashOption(description="ID of the channel to remove the message from", required=True),
        index: int = SlashOption(description="Index of the message to remove", required=True)
    ):
        # ✅ Add permission check first
        if not self._is_authorized(inter):
            await inter.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return

        try:
            await inter.response.defer()
            channel_id = int(channel_id)
            messages = await self.bot.db.recurrent.get_messages(channel_id)
            if not (0 < index <= len(messages)):
                await inter.followup.send(f"Invalid index provided. Please provide a number between 1 and {len(messages)}.")
                return

            await self.bot.db.recurrent.remove_message(channel_id, messages[index - 1])
            await inter.followup.send(f"Removed message {index} from channel <#{channel_id}>.")

        except ValueError:
            await inter.followup.send("Invalid channel ID or index provided.")
        except Exception as e:
            await inter.followup.send(f"Error removing recurring message: {e}")


    @_recurrent.subcommand(name="add_category", description="Add a recurring message to a category of channels with pagination")
    async def _recurrent_add_category(self, inter: Interaction):
        if not self._is_authorized(inter):
            await inter.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return

        class CategorySelect(Select):
            def __init__(self, bot: APBot):
                options = [
                    SelectOption(label=category.name, value=str(category.id))
                    for category in inter.guild.categories
                ]
                super().__init__(placeholder="Select a category", min_values=1, max_values=1, options=options)
                self.bot = bot

            async def callback(self, select_interaction: Interaction):
                selected_category_id = int(self.values[0])
                selected_category = next((cat for cat in inter.guild.categories if cat.id == selected_category_id), None)

                if not selected_category:
                    await select_interaction.response.send_message("Category not found.", ephemeral=True)
                    return

                class MessageLimitModal(Modal):
                    def __init__(self, bot: APBot, selected_category):
                        super().__init__(title="Enter Message and Limit")
                        self.bot = bot
                        self.selected_category = selected_category

                        self.message_input = TextInput(
                            label="Message to Send",
                            placeholder="Enter the message here...",
                            required=True,
                            max_length=2000,
                            style=TextInputStyle.paragraph
                        )
                        self.add_item(self.message_input)

                        self.limit_input = TextInput(
                            label="Send every N messages",
                            placeholder="Enter the limit here (number)...",
                            required=True,
                            style=TextInputStyle.short
                        )
                        self.add_item(self.limit_input)

                    async def callback(self, modal_interaction: Interaction):
                        try:
                            limit = int(self.limit_input.value)
                            if limit < 1:
                                raise ValueError()
                        except ValueError:
                            await modal_interaction.response.send_message("Invalid limit. Please enter a positive number.", ephemeral=True)
                            return

                        channels = [ch for ch in selected_category.channels if isinstance(ch, nextcord.TextChannel)]
                        pages = [channels[i:i + 25] for i in range(0, len(channels), 25)]

                        class ChannelPageView(View):
                            def __init__(self, bot, pages, message, limit, interaction):
                                super().__init__(timeout=300)
                                self.bot = bot
                                self.pages = pages
                                self.current_page = 0
                                self.message = message
                                self.limit = limit
                                self.excluded_ids = set()
                                self.interaction = interaction
                                self.select = None
                                self.update_select()

                            def update_select(self):
                                self.clear_items()
                                current_channels = self.pages[self.current_page]
                                options = [
                                    SelectOption(label=ch.name, value=str(ch.id)) for ch in current_channels
                                ]
                                self.select = Select(placeholder="Select channels to exclude", min_values=0, max_values=len(options), options=options)

                                async def select_callback(interaction: Interaction):
                                    self.excluded_ids.update(map(int, self.select.values))
                                    await interaction.response.send_message(
                                        f"Marked {len(self.select.values)} channel(s) for exclusion.",
                                        ephemeral=True
                                    )

                                self.select.callback = select_callback
                                self.add_item(self.select)

                                if self.current_page > 0:
                                    prev_button = Button(label="Previous", style=nextcord.ButtonStyle.secondary)
                                    async def prev_callback(interaction: Interaction):
                                        self.current_page -= 1
                                        self.update_select()
                                        await interaction.message.edit(view=self)
                                    prev_button.callback = prev_callback
                                    self.add_item(prev_button)

                                if self.current_page < len(self.pages) - 1:
                                    next_button = Button(label="Next", style=nextcord.ButtonStyle.secondary)
                                    async def next_callback(interaction: Interaction):
                                        self.current_page += 1
                                        self.update_select()
                                        await interaction.message.edit(view=self)
                                    next_button.callback = next_callback
                                    self.add_item(next_button)

                                confirm_button = Button(label="Confirm", style=nextcord.ButtonStyle.success)
                                async def confirm_callback(interaction: Interaction):
                                    await interaction.response.defer(ephemeral=False)
                                    all_channels = sum(self.pages, [])
                                    added = 0
                                    for ch in all_channels:
                                        if ch.id in self.excluded_ids:
                                            continue
                                        await self.bot.db.recurrent.add_message(ch.id, self.message, self.limit)
                                        try:
                                            await ch.send(embed=Embed(description=self.message))  # ✅ Send immediately
                                        except Exception as e:
                                            logger.warning(f"Failed to send initial message to #{ch.name}: {e}")
                                        added += 1

                                    await interaction.followup.send(
                                        f"Added recurring message to {added} channel(s) in '{selected_category.name}' with send interval every {self.limit} messages.",
                                        ephemeral=False
                                    )
                                confirm_button.callback = confirm_callback
                                self.add_item(confirm_button)

                        view = ChannelPageView(self.bot, pages, self.message_input.value, limit, modal_interaction)
                        await modal_interaction.response.send_message("Select channels to exclude:", view=view, ephemeral=False)

                modal = MessageLimitModal(self.bot, selected_category)
                await select_interaction.response.send_modal(modal)

        select = CategorySelect(self.bot)
        view = View(timeout=60)
        view.add_item(select)
        await inter.response.send_message("Please select a category:", view=view, ephemeral=False)


    @_recurrent.subcommand(
        name="remove_category", 
        description="Remove all recurring messages from a category of channels"
    )
    async def _recurrent_remove_category(self, inter: Interaction):
        # ✅ Authorization check
        if not self._is_authorized(inter):
            await inter.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return

        class CategorySelect(Select):
            def __init__(self, bot: APBot):
                options = [
                    SelectOption(label=category.name, value=str(category.id))
                    for category in inter.guild.categories
                ]
                super().__init__(placeholder="Select a category", min_values=1, max_values=1, options=options)
                self.bot = bot

            async def callback(self, select_interaction: Interaction):
                await select_interaction.response.defer(ephemeral=False)  # Make response visible to everyone

                selected_category_id = int(self.values[0])
                selected_category = next((cat for cat in inter.guild.categories if cat.id == selected_category_id), None)

                if not selected_category:
                    await select_interaction.followup.send("Category not found.", ephemeral=False)  # Visible to all
                    return

                # Remove recurring messages for all text channels in the category
                for channel in selected_category.channels:
                    if isinstance(channel, nextcord.TextChannel):
                        await self.bot.db.recurrent.clear_channel_data(channel.id)

                await select_interaction.followup.send(
                    f"Removed all recurring messages for category '{selected_category.name}'.",
                    ephemeral=False  # Visible to all
                )

        # Create and send the category select menu
        select = CategorySelect(self.bot)
        view = View(timeout=60)
        view.add_item(select)
        await inter.response.send_message("Please select a category:", view=view, ephemeral=False)




    @commands.Cog.listener("on_message")
    async def _recurrent_on_message(self, message):
        if message.author.bot:
            return  # avoid bots to prevent loops

        channel_id = message.channel.id
        channel_config = await self.bot.db.recurrent.get_channel_config(channel_id)

        messages = channel_config.get("messages", [])
        if not messages:
            return  # no recurring messages set for this channel

        limit = max(channel_config.get("limit", 1), 1)

        # Increment count of user messages in channel
        self.message_count_cache[channel_id] += 1 

        # If count hits limit, send the recurring message and reset counter
        if self.message_count_cache[channel_id] >= limit:
            self.message_count_cache[channel_id] = 0

            # Rotate through messages to send next one (optional)
            # Track last sent message index per channel in memory
            if not hasattr(self, "last_sent_index"):
                self.last_sent_index = {}

            last_index = self.last_sent_index.get(channel_id, -1)
            next_index = (last_index + 1) % len(messages)
            msg_to_send = messages[next_index]

            # Send the message as embed
            await message.channel.send(embed=Embed(description=msg_to_send))

            # Update last sent index for next rotation
            self.last_sent_index[channel_id] = next_index



def setup(bot: APBot):
    bot.add_cog(Recurrent(bot))
