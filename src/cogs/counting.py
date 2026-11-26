"""AP Students mathematical counting game. Only acts in the configured channel."""
import asyncio
import logging
import re
import time

import nextcord
from nextcord import Embed, Interaction, SlashOption, slash_command
from nextcord.ext import commands
from app_config import get_command_guild_ids, load_optional_config
from utils.math_evaluator import Evaluator, MAX_COUNT
from utils.counting_store import CountingStore, apply_count, apply_restore

log=logging.getLogger(__name__)
GUILD_IDS=get_command_guild_ids(load_optional_config())
MOD_ROLES={'Trial Chat Moderator','Chat Moderator','Lead Moderator','Moderator','Admin'}
NO_MENTIONS=nextcord.AllowedMentions.none()

HELP = '''**How to Play**
Start at **1** and take turns. Send a number or an expression equal to the next number.
✅ Correct count • ❌ Wrong integer or counting twice in a row resets the streak • ⚠️ Invalid expressions or non-integer results are not counted.
Use `/test` to privately check an expression without affecting the game.

**Basic Operations**
`a+b` addition, `a-b` subtraction, `a*b` multiplication, `a/b` division
`a^b` or `a**b` exponentiation; `n!` or `factorial(n)` factorial
`a=b` verifies that both sides are exactly equal.
Examples: `2^3` → 8; `5!` → 120; `1+1=2` → 2.

**Constants and Formatting**
`pi` or `π`: pi; `e` or `ℯ`: Euler's number; `i` or `ⅈ`: imaginary unit (i² = -1).
Explicit and implicit multiplication work: `2*3`, `2(3+4)`, `2π`, `3x`, `2sin(π/2)`.
Unicode ×, ÷, −, √(...) and superscript digits are supported. Spaces between tokens are optional. Wrap an expression in one pair of backticks to prevent Discord italic formatting. Use parentheses to avoid ambiguous fractions: `1/(2(4))` → 1/8.

**Common Functions**
`sqrt(x)` square root: `sqrt(81)` → 9
`abs(x)` absolute value: `abs(-5)` → 5
`floor(x)` round down: `floor(3.8)` → 3
`ceil(x)` round up: `ceil(3.2)` → 4
`log(x,b)` logarithm of x in base b: `log(8,2)` → 3
`ln(x)` or `log(x)` natural logarithm: `ln(e^4)` → 4
`exp(x)` e raised to x: `exp(0)` → 1
`binomial(n,k)` choose k items from n: `binomial(10,3)` → 120

**Trigonometry**
`sin(x)`, `cos(x)`, `tan(x)`: sine, cosine, tangent.
`asin(x)`, `acos(x)`, `atan(x)`: inverse trig functions.
All angles use radians. `sin(π/2)` → 1.

**Summations (Σ)**
`sum(expression, variable, start, end)`
• expression: formula evaluated at each step
• variable: which variable changes
• start/end: first and last integers, both included
`sum(k²,k,1,3)` → 1² + 2² + 3² = 14

**Products (Π)**
`prod(expression, variable, start, end)`
Same inputs as summation, but multiplies the terms.
`prod(k,k,1,4)` → 1 × 2 × 3 × 4 = 24

**Definite Integrals (∫)**
`integral(expression, variable, lower, upper)` or `int(...)`
• expression: function to integrate
• variable: variable of integration
• lower/upper: finite real bounds
`integral(2x,x,0,3)` → 9

**Derivatives**
`diff(expression, variable, point)`
• expression: function to differentiate
• variable: variable of differentiation
• point: value at which to evaluate the first derivative
`diff(3x²,x,2)` → 12

**Advanced Examples**
`e^(πi)+3` → 2
`sin(π/4)^2+cos(π/4)^2` → 1
`integral(2x,x,0,3)+sum(k,k,1,4)` → 19
`2³×√(144)÷4` → 24

**FAQ and Limits**
• Does APBot round? No. A correct count must be an exact positive integer equal to the next number (up to 1 trillion). `2π` is not a valid count, but `2π/π` → 2. Zero and negative integers are wrong counts and can reset the game.
• Can I use variables? Yes, if bound inside sum, prod, integral or diff. `3x` alone is invalid.
• Can I undo a count by editing or deleting? No.
• Up to 250 characters; sums/products up to 200 terms with integer bounds between -10000 and 10000; factorial up to 200; binomial arguments up to 500; numeric exponent magnitude up to 100. Complex expressions may time out.
• Need help checking an answer? Use `/test` privately.'''



def duration(seconds):
    days,seconds=divmod(seconds,86400); hours,seconds=divmod(seconds,3600); minutes,seconds=divmod(seconds,60)
    return f'{days}d {hours}h {minutes}m' if days else f'{hours}h {minutes}m {seconds}s' if hours else f'{minutes}m {seconds}s'


def looks_like_math(text):
    # Only delete obvious non-math conversation, not malformed math attempts.
    # Recognize math inside Discord inline code before sending it to the parser.
    text = text.lstrip().lstrip("`").lstrip()
    return bool(re.match(r'\s*(?:[0-9.(+\-−π√ℯⅈ]|(?:pi|e|i|sqrt|abs|sin|cos|tan|asin|acos|atan|log|ln|exp|floor|ceil|factorial|binomial|sum|prod|integral|int|diff)\b)',text,re.I))


class Counting(commands.Cog):
    def __init__(self,bot):
        self.bot=bot
        self.evaluator=Evaluator()
        # Share lock and store per bot instance; Mongo CAS protects against stale writes.
        if not hasattr(bot,'_counting_lock'): bot._counting_lock=asyncio.Lock()
        self.lock=bot._counting_lock
        self.store=CountingStore(bot.db.base_db.database)
        self.pending=0
        self.test_times={}

    def guild_allowed(self,guild):
        return guild is not None and str(guild.id)==str(self.bot.config.get('guild_id'))

    def channel_id(self):
        try: return int(self.bot.config.get('counting_channel_id',0) or 0)
        except (ValueError,TypeError): return 0

    def is_channel(self,message):
        return self.guild_allowed(message.guild) and self.channel_id()!=0 and message.channel.id==self.channel_id()

    def can_restore(self,member):
        configured=self.bot.config.get('counting_moderator_role_ids',[]) or []
        roles={str(x) for x in configured}
        if getattr(getattr(member,'guild_permissions',None),'administrator',False): return True
        return any(str(r.id) in roles or (not roles and r.name in MOD_ROLES) for r in getattr(member,'roles',[]))

    async def react(self,message,emoji):
        try: await message.add_reaction(emoji)
        except nextcord.HTTPException: log.warning('Counting reaction failed for %s',message.id)

    async def notice(self,message,text):
        try: await message.channel.send(text,allowed_mentions=NO_MENTIONS,delete_after=12)
        except nextcord.HTTPException: log.warning('Counting notice failed')

    @commands.Cog.listener()
    async def on_message(self,message):
        if not self.is_channel(message) or message.author.bot or getattr(message,'webhook_id',None): return
        if message.type not in (nextcord.MessageType.default,nextcord.MessageType.reply): return
        text=message.content.strip()
        if not looks_like_math(text):
            try: await message.delete()
            except nextcord.HTTPException: log.warning('Could not remove non-counting message %s',message.id)
            return
        if self.pending>=12:
            await self.react(message,'⚠️')
            return
        self.pending+=1
        try:
            async with self.lock:
                result=await self.evaluator.evaluate(text)
                if not result['ok'] or result.get('integer') is None:
                    await self.react(message,'⚠️')
                    await self.notice(message,'Not counted. '+result.get('error','Use an exact integer within the supported range.')+' Try `/test`.')
                    return
                number=result['integer']
                for _ in range(3):
                    old=await self.store.read(message.guild.id,message.channel.id)
                    action,new,stats=apply_count(old,number,message.author.id,message.id,time.time())
                    if action=='duplicate': return
                    if await self.store.commit(old,new): break
                else:
                    await self.notice(message,'Count not recorded because the game changed concurrently. Try again.'); return
                if action=='accepted':
                    await self.react(message,'✅')
                    if stats['record']:
                        await message.channel.send(f"New all-time counting record: **{new['count']:,}**!",allowed_mentions=NO_MENTIONS)
                else:
                    await self.react(message,'❌')
                    description=('The same member counted twice in a row.' if stats['reason']=='same_user' else f"Expected **{stats['expected']:,}**, but received **{stats['received']:,}**.")
                    embed=Embed(title='Count ruined!',description=description,color=0xED4245)
                    embed.add_field(name='Final count',value=f"{stats['count']:,}")
                    embed.add_field(name='All-time record',value=f"{stats['record']:,}")
                    embed.add_field(name='Participants',value=str(stats['participants']))
                    embed.add_field(name='Streak duration',value=duration(stats['duration']))
                    embed.set_footer(text='Restart from 1! Use /count help to explore supported math functions.')
                    await message.channel.send(embed=embed,allowed_mentions=NO_MENTIONS)
        except Exception:
            log.exception('Counting message processing failed')
            await self.notice(message,'Counting could not finish processing this message. Ask a moderator if the state looks wrong.')
        finally:
            self.pending-=1

    @slash_command(name='test',description='Privately evaluate a mathematical expression',guild_ids=GUILD_IDS)
    async def math_test(self,inter:Interaction,expression:str=SlashOption(description='Mathematical expression',required=True)):
        await inter.response.defer(ephemeral=True)
        if not self.guild_allowed(inter.guild):
            return await inter.followup.send('This command is available in AP Students only.',ephemeral=True)
        now=time.monotonic()
        # Prune expired entries and limit requests without storing expressions or user histories.
        self.test_times={k:v for k,v in self.test_times.items() if now-v<3}
        if inter.user.id in self.test_times:
            return await inter.followup.send('Please wait 3 seconds between tests.',ephemeral=True)
        self.test_times[inter.user.id]=now
        try:
            result=await self.evaluator.evaluate(expression)
            if not result['ok']:
                return await inter.followup.send('Unable to evaluate: '+result['error'],ephemeral=True,allowed_mentions=NO_MENTIONS)
            n=result.get('integer')
            embed=Embed(title='Expression Evaluator',color=0x57F287 if n is not None and n>0 else 0xF0B232)
            embed.add_field(name='Result',value=result['result'],inline=False)
            if result.get('approximation') and result['approximation']!=result['result']:
                embed.add_field(name='Approximation',value=result['approximation'],inline=False)
            embed.set_footer(text=('Valid counting expression' if n is not None and n>0 else 'Not a supported positive integer')+' • Count unchanged')
            await inter.followup.send(embed=embed,ephemeral=True,allowed_mentions=NO_MENTIONS)
        except Exception:
            # Do not log private expression content or send a public error.
            await inter.followup.send('Calculator unavailable. Try again later.',ephemeral=True)

    @slash_command(name='count',description='Mathematical counting game',guild_ids=GUILD_IDS)
    async def count(self,inter:Interaction):
        pass

    @count.subcommand(name='help',description='Counting rules and mathematical syntax')
    async def count_help(self,inter:Interaction):
        await inter.response.send_message(embed=Embed(title='Counting Help',description=HELP,color=0x5865F2),ephemeral=True)

    @count.subcommand(name='restore',description='Restore a count (moderators only)')
    async def restore(self,inter:Interaction,number:int=SlashOption(description='Last correct number to restore',required=True,min_value=0,max_value=MAX_COUNT),reason:str=SlashOption(description='Reason for restoring',required=True)):
        await inter.response.defer(ephemeral=True)
        if not self.guild_allowed(inter.guild) or not self.can_restore(inter.user):
            return await inter.followup.send('Only authorized moderators can restore a count.',ephemeral=True)
        if not self.channel_id() or inter.channel_id!=self.channel_id():
            return await inter.followup.send('Run this in the configured counting channel.',ephemeral=True)
        try:
            async with self.lock:
                old=await self.store.read(inter.guild.id,inter.channel_id)
                new=apply_restore(old,number,inter.user.id,reason,time.time())
                if not await self.store.commit(old,new):
                    return await inter.followup.send('Count changed concurrently. Retry the command.',ephemeral=True)
                embed=Embed(title='Count Restored',description=f"Previous count: **{old['count']:,}**\nRestored count: **{number:,}**\nNext number: **{number+1:,}**",color=0x57F287)
                embed.add_field(name='Reason',value=reason,inline=False)
                embed.add_field(name='Restored by',value=inter.user.mention)
                try: await inter.channel.send(embed=embed,allowed_mentions=NO_MENTIONS)
                except nextcord.HTTPException:
                    return await inter.followup.send('Count restored in MongoDB, but the public announcement failed.',ephemeral=True)
            await inter.followup.send('Count restored.',ephemeral=True)
        except ValueError as error:
            await inter.followup.send(str(error),ephemeral=True)
        except Exception:
            log.exception('Count restore failed')
            await inter.followup.send('Could not confirm restoration. Check the game state before retrying.',ephemeral=True)


def setup(bot):
    bot.add_cog(Counting(bot))
