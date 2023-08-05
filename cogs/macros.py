import discord
from discord.ext import commands

ROLE_CAN_MAKE_MACROS = ["Chat Moderator", "Admin"]


def can_make_macros(ctx: commands.Context) -> bool:

    check = any([role.name in ROLE_CAN_MAKE_MACROS for role in ctx.message.author.roles])
    if not check:
        raise commands.CommandError(message=f"No permission to create macros! Needs to have one of these roles: {ROLE_CAN_MAKE_MACROS}")
    return check



class Macros(commands.Cog):
    """
    A system to let users respond with automated replies.
    Because getting asked for study resources all the time is annoying :(
    """

    def __init__(self, bot: commands.Bot) -> None:
    
        self.bot = bot

        self.allowed_mentions = discord.AllowedMentions.none()
        self.allowed_mentions.replied_user = True

        self.success_embed = discord.Embed(colour=discord.Colour.green())
        self.failure_embed = discord.Embed(colour=discord.Colour.red())

    async def get_macro(self, name: str) -> str | None:
        maybe_found = await self.bot.macros.find_one({"name": name})
        if not maybe_found:
            return None

        return maybe_found["value"]

    async def insert_macro(self, name: str, value: str) -> None:

        if await self.get_macro(name):
            raise KeyError("Macro already exists - try removing it first?")
        
        # Security: no idc about sanitization because mods are nice right guys?
        # Okay maybe I do care but I'll just remember to remove mentions from the bot when using macros
        await self.bot.macros.insert_one({"name": name, "value": value})

    async def delete_macro(self, name: str) -> None:

        if not await self.get_macro(name):
            raise KeyError("Macro doesn't exist - can't be deleted")
        
        macro = await self.bot.macros.delete_one({"name": name})

    @commands.command(name='m')
    async def use_macro(self, ctx: commands.Context, macro_name: str):
        """
        Uses a macro, replying to the user with the macro contents.
        """

        maybe_macro = await self.get_macro(macro_name)
        if maybe_macro:
            await ctx.message.reply(maybe_macro, allowed_mentions=self.allowed_mentions)
        
    
    @commands.check(can_make_macros)
    @commands.command(name='newmacro')
    async def new_macro(self, ctx: commands.Context, macro_name: str):
        """
        Creates a new macro that any user can use.
        """

        reply = ctx.message.reference
        if not reply:
            embed = self.failure_embed
            embed.title = "Cannot make macro"
            embed.description = "Reply to a message to make a macro with this command"
            await ctx.message.reply(embed=embed)
            return 
            
        reply = await ctx.channel.fetch_message(reply.message_id)
        if not reply:
            embed = self.failure_embed
            embed.title = "Cannot fetch replied message"
            embed.description = "Cannot fetch replied message - has it been deleted?"
            await ctx.message.reply(embed=embed)
            return

        await self.insert_macro(macro_name, reply.content)

        embed = self.success_embed
        embed.title = "Success"
        embed.description = f"Macro {self.bot.command_prefix}{self.use_macro.name} {macro_name} is available!"
        await ctx.message.reply(embed=embed, allowed_mentions=self.allowed_mentions)

    @commands.check(can_make_macros)
    @commands.command(name='removemacro')
    async def remove_macro(self, ctx: commands.Context, macro_name: str):
        """
        Removes a macro, preventing it from being used.
        """

        await self.delete_macro(macro_name)

        embed = self.failure_embed
        embed.title = "Success"
        embed.description = f"Macro {self.bot.command_prefix}{self.use_macro.name} {macro_name} has been deleted."
        await ctx.message.reply(embed=embed, allowed_mentions=self.allowed_mentions)

    @commands.command(name='listmacros')
    async def list_macros(self, ctx: commands.Context):
        """
        Lists all active macros
        """

        macros = await self.bot.macros.find({"name": {"$exists": True}}).to_list(length=None)
        macros = list(map(lambda macro: macro["name"], macros))
        macros = str(macros)[1:-1] # Remove square brackets

        await ctx.message.reply(embed=discord.Embed(title="Available macros", description=macros))

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Macros(bot), guilds=[discord.Object(id=bot.guild_id)])
