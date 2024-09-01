"""
    @_recurrent.subcommand(name="group", description="Group channels by a name")
    async def group(self, inter: Interaction, name: str = SlashOption(description="Name of the group", required=True), channel_ids: str = SlashOption(description="Comma-separated list of channel IDs", required=True)):
        try:
            await inter.response.defer()
            channel_ids_list = [int(cid.strip()) for cid in channel_ids.split(',')]
            await self.bot.db.recurrent.add_group(name, channel_ids_list)
            await inter.followup.send(f"Channels grouped under '{name}'.")
        except ValueError:
            await inter.followup.send("Invalid channel IDs provided. Ensure they are comma-separated integers.")
        except Exception as e:
            await inter.followup.send(f"Error grouping channels: {e}")

    @_recurrent.subcommand(name="showgroups", description="Show all channel groups")
    async def showgroups(self, inter: Interaction):
        try:
            await inter.response.defer()
            groups = await self.bot.db.recurrent.get_groups()
            if not groups:
                await inter.followup.send("No groups found.")
                return
            group_list = "\n".join([f"{name}: {', '.join([f'<#{cid}>' for cid in channel_ids])}" for name, channel_ids in groups.items()])
            await inter.followup.send(f"Channel Groups:\n{group_list}")
        except Exception as e:
            await inter.followup.send(f"Error retrieving groups: {e}")



    @_recurrent.subcommand(name="groupmessage", description="Add a recurring message to all channels in a group")
    async def groupmessage(self, inter: Interaction, group_name: str = SlashOption(description="Name of the group", required=True), message: str = SlashOption(description="Message to send", required=True), limit: int = SlashOption(description="Message count limit before sending a recurring message", required=True)):
        try:
            await inter.response.defer()
            group = await self.bot.db.recurrent.get_group(group_name)
            if not group:
                await inter.followup.send(f"Group '{group_name}' not found.")
                return

            for channel_id in group:
                await self.bot.db.recurrent.add_message(channel_id, message, limit)

            await inter.followup.send(f"Added recurring message '{message}' to group '{group_name}' with limit {limit}.")
        except Exception as e:
            await inter.followup.send(f"Error adding recurring message to group: {e}")
    @_recurrent.subcommand(name="removegroup", description="Remove a group of channels and their recurring messages by name")
    async def removegroup(self, inter: Interaction, name: str = SlashOption(description="Name of the group to remove", required=True)):
        try:
            await inter.response.defer()
            group = await self.bot.db.recurrent.get_group(name)
            if not group:
                await inter.followup.send(f"Group '{name}' not found.")
                return

            for channel_id in group:
                await self.bot.db.recurrent.clear_channel_messages(channel_id)
            
            await self.bot.db.recurrent.delete_group(name)
            await inter.followup.send(f"Group '{name}' and its recurring messages have been removed.")
        except Exception as e:
            await inter.followup.send(f"Error removing group: {e}")
"""






import nextcord
from nextcord.ext import commands
from bot_base import APBot
from nextcord import Interaction, SelectOption, SlashOption, slash_command, TextInputStyle
from collections import defaultdict
from nextcord.ui import Select, View, Modal, TextInput
from nextcord import Embed 
import logging

class Recurrent(commands.Cog):
    def __init__(self, bot: APBot):
        self.bot = bot
        self.message_count_cache = defaultdict(int)
        self.category_message_count_cache = defaultdict(lambda: defaultdict(int))  
        self.activity_threshold = 10  
        self.category_threshold = 10  

    @slash_command(name="recurrent", description="Manage recurring messages")
    async def _recurrent(self, inter: Interaction):
        await inter.response.send_message("Subcommands: /recurrent add, /recurrent clear, /recurrent list, /recurrent remove, /recurrent status, /recurrent group, /recurrent showgroups, /recurrent groupmessage, /recurrent removegroup, /recurrent clear_category", ephemeral=True)

    @_recurrent.subcommand(name="add", description="Add a recurring message to a channel")
    async def add(self, inter: Interaction, channel_id: str = SlashOption(description="ID of the channel where the message will be sent", required=True), message: str = SlashOption(description="Message to send", required=True), limit: int = SlashOption(description="Message count limit before sending a recurring message", required=True)):
        try:
            await inter.response.defer()
            channel_id = int(channel_id)
            channel = self.bot.get_channel(channel_id)
            if not channel:
                await inter.followup.send(f"Channel ID {channel_id} not found.")
                return

            await self.bot.db.recurrent.add_message(channel_id, message, limit)
            await inter.followup.send(f"Recurring message added to channel <#{channel_id}> with limit {limit}.")
        except ValueError:
            await inter.followup.send("Invalid channel ID provided.")
        except Exception as e:
            await inter.followup.send(f"Error adding recurring message: {e}")


    @_recurrent.subcommand(name="list", description="List all recurring messages in a channel")
    async def list(self, inter: Interaction, channel_id: str = SlashOption(description="ID of the channel to list messages from", required=True)):
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
    async def remove(self, inter: Interaction, channel_id: str = SlashOption(description="ID of the channel to remove the message from", required=True), index: int = SlashOption(description="Index of the message to remove", required=True)):
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

    @_recurrent.subcommand(name="status", description="Show how many times each recurring message has been sent")
    async def status(self, inter: Interaction, channel_id: str = SlashOption(description="ID of the channel to show status for", required=True)):
        try:
            await inter.response.defer()
            channel_id = int(channel_id)
            channel_config = await self.bot.db.recurrent.get_channel_config(channel_id)
            if not channel_config["messages"]:
                await inter.followup.send(f"No recurring messages found for channel <#{channel_id}>.")
                return
            
            status_list = "\n".join([
                f"{idx + 1}: {msg} - Sent {channel_config['message_counts'][msg]} times"
                for idx, msg in enumerate(channel_config["messages"])
            ])
            await inter.followup.send(f"Recurring message status for channel <#{channel_id}>:\n{status_list}")
        except ValueError:
            await inter.followup.send("Invalid channel ID provided.")
        except Exception as e:
            await inter.followup.send(f"Error retrieving message status: {e}")

    @_recurrent.subcommand(
        name="add_category",
        description="Add a recurring message to a category of channels"
    )
    async def add_category(self, inter: Interaction):
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
                    await select_interaction.response.send_message("Category not found.", ephemeral=False)
                    return

                # Display a modal to enter the message and limit
                class MessageLimitModal(Modal):
                    def __init__(self, bot: APBot, selected_category):
                        super().__init__(title="Enter Message and Limit")
                        self.bot = bot
                        self.selected_category = selected_category

                        # Make the message box long
                        self.message_input = TextInput(
                            label="Message to Send",
                            placeholder="Enter the message here...",
                            required=True,
                            max_length=2000,
                            style=TextInputStyle.paragraph  # Set the style to paragraph for a longer input box
                        )
                        self.add_item(self.message_input)

                        self.limit_input = TextInput(
                            label="Message Count Limit",
                            placeholder="Enter the limit here (number)...",
                            required=True,
                            style=TextInputStyle.short
                        )
                        self.add_item(self.limit_input)

                    async def callback(self, modal_interaction: Interaction):
                        try:
                            limit = int(self.limit_input.value)
                        except ValueError:
                            await modal_interaction.response.send_message("Invalid limit. Please enter a number.", ephemeral=False)
                            return

                        # Step 3: Ask which channels to exclude
                        class ChannelExcludeSelect(Select):
                            def __init__(self, bot: APBot, channels, message, limit):
                                options = [
                                    SelectOption(label="None of them", value="none")  # Add "None of them" option
                                ] + [
                                    SelectOption(label=channel.name, value=str(channel.id))
                                    for channel in channels
                                ]
                                super().__init__(placeholder="Select channels to exclude", min_values=0, max_values=len(options), options=options)
                                self.bot = bot  # Make sure to store the bot instance
                                self.message = message
                                self.limit = limit

                            async def callback(self, exclude_interaction: Interaction):
                                # Defer interaction to prevent timeouts
                                await exclude_interaction.response.defer(ephemeral=False)

                                # Check if "None of them" is selected
                                if "none" in self.values:
                                    excluded_channels = []  # No channels are excluded
                                else:
                                    excluded_channels = [int(channel_id) for channel_id in self.values]

                                # Add the recurring message to all text channels except the excluded ones
                                for channel in selected_category.channels:
                                    if isinstance(channel, nextcord.TextChannel) and channel.id not in excluded_channels:
                                        await self.bot.db.recurrent.add_message(channel.id, self.message, self.limit)

                                await exclude_interaction.followup.send(
                                    f"Added recurring message to all channels in category '{selected_category.name}' with limit {self.limit}, excluding selected channels.",
                                    ephemeral=False  # Visible to everyone
                                )

                        # Create and send the exclusion select menu
                        channel_select = ChannelExcludeSelect(self.bot, [ch for ch in selected_category.channels if isinstance(ch, nextcord.TextChannel)], self.message_input.value, limit)
                        exclusion_view = View(timeout=60)
                        exclusion_view.add_item(channel_select)
                        await modal_interaction.response.send_message("Select channels to exclude:", view=exclusion_view, ephemeral=False)  # Visible to everyone

                # Show modal for message and limit input
                modal = MessageLimitModal(self.bot, selected_category)
                await select_interaction.response.send_modal(modal)  # Directly sending modal without any defer

        # Create and send the category select menu
        select = CategorySelect(self.bot)
        view = View(timeout=60)
        view.add_item(select)
        await inter.response.send_message("Please select a category:", view=view, ephemeral=False)  # Visible to everyone


    @_recurrent.subcommand(
        name="remove_category", 
        description="Remove all recurring messages from a category of channels"
    )
    async def remove_category(self, inter: Interaction):
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
                    await select_interaction.followup.send("Category not found.", ephemeral=False)  # Make message visible to everyone
                    return

                # Remove recurring messages for all text channels in the category
                for channel in selected_category.channels:
                    if isinstance(channel, nextcord.TextChannel):
                        await self.bot.db.recurrent.clear_channel_data(channel.id)

                await select_interaction.followup.send(
                    f"Removed all recurring messages for category '{selected_category.name}'.",
                    ephemeral=False  # Make message visible to everyone
                )

        # Create and send the category select menu
        select = CategorySelect(self.bot)
        view = View(timeout=60)
        view.add_item(select)
        await inter.response.send_message("Please select a category:", view=view, ephemeral=False)  # Make message visible to everyone



    @commands.Cog.listener("on_message")
    async def _recurrent_on_message(self, message):
        channel_id = message.channel.id
        channel_config = await self.bot.db.recurrent.get_channel_config(channel_id)
        
        if not channel_config["messages"]:
            return

        self.message_count_cache[channel_id] += 1

        if self.message_count_cache[channel_id] >= self.activity_threshold:
            self.message_count_cache[channel_id] = 0
            for msg in channel_config["messages"]:
                if channel_config["message_counts"][msg] < channel_config["limit"]:
                    await message.channel.send(embed=Embed(description=msg))
                    channel_config["message_counts"][msg] += 1

                    await self.bot.db.recurrent.update_message_count(channel_id, msg, channel_config["message_counts"][msg])
                    
                    if channel_config["message_counts"][msg] >= channel_config["limit"]:
                        await self.bot.db.recurrent.remove_message(channel_id, msg)
                    
                    break



def setup(bot: APBot):
    bot.add_cog(Recurrent(bot))

