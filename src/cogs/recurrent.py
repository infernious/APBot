from nextcord.ext import commands
from bot_base import APBot
from nextcord import Embed, Interaction, SlashOption, slash_command
from collections import defaultdict

class Recurrent(commands.Cog):
    def __init__(self, bot: APBot):
        self.bot = bot
        self.message_count_cache = defaultdict(int)
        self.activity_threshold = 10  

    @slash_command(name="recurrent", description="Manage recurring messages")
    async def _recurrent(self, inter: Interaction):
        await inter.response.send_message("Subcommands: /recurrent add, /recurrent clear, /recurrent list, /recurrent remove, /recurrent status, /recurrent group, /recurrent showgroups", ephemeral=True)

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

