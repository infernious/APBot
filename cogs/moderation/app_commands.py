import nextcord
import motor
from nextcord import app_commands

class ModerationAppCommands:
    """
    App commands to assist with moderation - because sometimes "/ban user" is just too many characters!
    """

    def __init__(self, db: motor.motor_asyncio.AsyncIOMotorCollection, log_channel: int):

        self.db = db
        self.log_channel = log_channel

    @app_commands.context_menu()
    async def get_warnings(self, interaction: nextcord.Interaction, member: nextcord.Member):
        # TODO: implement this because afaik the db stuff ain't working rn
        pass
