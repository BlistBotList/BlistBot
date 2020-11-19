import asyncio
import datetime
from textwrap import dedent as wrap

import asyncpg
import discord
import humanize
from discord.ext import commands

from . import checks
from .time import FutureTime


class Mod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._task = bot.loop.create_task(self.dispatch_mutes())

    async def dispatch_mutes(self):
        try:
            while not self.bot.is_closed():
                seven_days = datetime.datetime.utcnow() + datetime.timedelta(days=7)
                mutes = await self.bot.mod_pool.fetch("SELECT * FROM mutes WHERE expire < $1 ORDER BY expire", seven_days)
                for mute in mutes:
                    if mute['expire'] <= datetime.datetime.utcnow():
                        await self.call_mute(mute)
        except asyncio.CancelledError:
            raise
        except (OSError, discord.ConnectionClosed, asyncpg.PostgresConnectionError):
            self._task.cancel()
            self._task = self.bot.loop.create_task(self.dispatch_mutes())

    async def call_mute(self, mute):
        member = self.bot.main_guild.get_member(mute["userid"])
        mute_role = self.bot.main_guild.get_role(725899725152190525)
        await member.remove_roles(mute_role, reason="Unmuted")
        await self.bot.mod_pool.execute("DELETE FROM mutes WHERE id = $1", mute["id"])
        await self.do_case(self.bot.main_guild.get_member(mute["modid"]), member, "Automatic Un-mute", "Un-Mute")

    async def do_case(self, mod: discord.Member, member: discord.Member, reason, type, time=None):
        last_case_number = await self.bot.mod_pool.fetchval("SELECT COUNT(*) FROM action")
        if time:
            string = f"**__Length:__** ``{humanize.naturaldelta(time.dt - datetime.datetime.utcnow())}``"
        else:
            string = ""
        embed = discord.Embed(
            title=type.title(), color=discord.Color.blurple(),
            description=wrap(
            f"""
            **__Victim:__** {member} ({member.id})
            **__Reason:__** ``{reason or f'No reason was set. Do b!reason {last_case_number + 1} <reason> to do so.'}``
            {string}
            """
            )
        )
        embed.set_author(name=str(mod), icon_url=mod.avatar_url)
        embed.set_footer(text=f"Case #{last_case_number + 1}")
        embed.timestamp = datetime.datetime.utcnow()
        message = await self.bot.main_guild.get_channel(716719009499971685).send(embed=embed)
        await self.bot.mod_pool.execute("INSERT INTO action VALUES($1, $2, $3, $4, $5, $6)", member.id, mod.id, reason or 'None', message.id, type, datetime.datetime.utcnow())
        return last_case_number + 1

    @commands.has_permissions(ban_members=True)
    @commands.command()
    async def ban(self, ctx, member: discord.Member, *, reason=None):
        if member.bot:
            return await ctx.send(f"You cannot ban bots! Use `b!delete @{member} <reason>` to do so.")

        if not ctx.author.top_role > member.top_role:
            return await ctx.send("You cannot ban someone higher than you!")

        await self.do_case(ctx.author, member, reason, "Ban")
        await member.ban(reason=reason)

    @commands.has_permissions(kick_members=True)
    @commands.command()
    async def mute(self, ctx, member: discord.Member, length: FutureTime, *, reason):
        if not ctx.author.top_role > member.top_role:
            return await ctx.send(f"You cannot kick someone higher than you!")

        is_muted = await self.bot.mod_pool.fetch("SELECT * FROM mutes WHERE userid = $1", member.id)
        mute_role = self.bot.main_guild.get_role(725899725152190525)
        if mute_role in member.roles or is_muted != []:
            return await ctx.send(f"This user is already muted!")        

        await member.add_roles(mute_role, reason=reason)
        case_number = await self.do_case(ctx.author, member, reason, "Mute", time=length)
        await self.bot.mod_pool.execute("INSERT INTO mutes VALUES($1, $2, $3, $4, $5)", ctx.author.id, member.id, datetime.datetime.utcnow(), length.dt, case_number)

    @commands.has_permissions(kick_members=True)
    @commands.command()
    async def unmute(self, ctx, member: discord.Member, reason=None):
        if not ctx.author.top_role > member.top_role:
            return await ctx.send(f"You cannot un-mute someone higher than you!")

        is_muted = await self.bot.mod_pool.fetch("SELECT * FROM mutes WHERE userid = $1", member.id)
        mute_role = self.bot.main_guild.get_role(725899725152190525)
        if mute_role not in member.roles or is_muted == []:
            return await ctx.send(f"This user is not muted!")

        await self.bot.mod_pool.execute("DELETE FROM mutes WHERE userid = $1", member.id)
        await member.remove_roles(mute_role, reason=reason)
        await self.do_case(ctx.author, member, reason, "Un-Mute")

    @commands.has_permissions(kick_members=True)
    @commands.command()
    async def kick(self, ctx, member: discord.Member, *, reason=None):
        if member.bot:
            return await ctx.send("You cannot kick bots! Use `b!delete @{member} <reason>` to do so.")

        if not ctx.author.top_role > member.top_role:
            return await ctx.send(f"You cannot kick someone higher than you!")

        await self.do_case(ctx.author, member, reason, "Kick")
        await member.kick(reason=reason)

    @commands.has_permissions(manage_messages=True)
    @commands.command()
    async def warn(self, ctx, member: discord.Member, *, reason=None):
        if member.bot:
            return await ctx.send("You cannot warn bots!")

        if not ctx.author.top_role > member.top_role:
            return await ctx.send(f"You cannot warn someone higher than you!")

        await self.do_case(ctx.author, member, reason, "Warn")

    @commands.has_permissions(manage_messages=True)
    @commands.command()
    async def purge(self, ctx, amount: int):
        if amount < 1:
            return await ctx.send("Cannot purge that amount of messages!")
        await ctx.channel.purge(limit=amount + 1)

    @commands.has_permissions(manage_messages=True)
    @commands.command()
    async def case(self, ctx, number: int):
        info = await self.bot.mod_pool.fetch("SELECT * FROM action WHERE id = $1", number)
        if not info:
            return await ctx.send(f"Case {number} does not exist!")
        else:
            info = info[0]

        target = ctx.guild.get_member(info['userid'])
        mod = ctx.guild.get_member(info['modid'])

        embed = discord.Embed(
            title=info['type'].title(),
            color=discord.Color.blurple(),
            description=wrap(
                f"""
                **__Mod:__** {mod} ({mod.id})
                **__Victim:__** {target} ({target.id})
                **__Reason:__** ``{info['reason']}``
                **__Time:__** ``{info['time'].strftime('%c')}``
                """
            )
        )
        await ctx.send(embed=embed)

    @commands.has_permissions(manage_messages=True)
    @commands.command()
    async def reason(self, ctx, number: int, *, reason):
        info = await self.bot.mod_pool.fetch("SELECT * FROM action WHERE id = $1", number)
        if not info:
            return await ctx.send(f"Case {number} does not exist!")
        else:
            info = info[0]

        await ctx.send(f"Set the reason to: `{reason}`")
        await self.bot.mod_pool.execute("UPDATE action SET reason = $1 WHERE id = $2", reason, number)
        
        target = ctx.guild.get_member(info['userid'])
        mod = ctx.guild.get_member(info['modid'])
        if info['type'] == "Mute":
            mute_info = await self.bot.mod_pool.fetchval("SELECT expire FROM mutes WHERE id = $1", info['id'])
            time = humanize.naturaldelta(mute_info - datetime.datetime.utcnow())
            string = f"**__Length:__** ``{time}``"
        else:
            string = ""
        embed = discord.Embed(
            title=info['type'].title(),
            color=discord.Color.blurple(),
            description=wrap(
                f"""
                **__Victim:__** {target} ({target.id})
                **__Reason:__** ``{reason}``
                {string}
                """
            )
        )
        embed.set_author(name=mod, icon_url= mod.avatar_url)
        embed.set_footer(text=f"Case #{number}")
        embed.timestamp = info["time"]

        message = await self.bot.main_guild.get_channel(716719009499971685).fetch_message(info['messageid'])
        await message.edit(embed=embed)

    @commands.command()
    @checks.main_guild_only()
    async def common_prefix(self, ctx, member: discord.Member):
        if not member.bot:
            return await ctx.send("This command can only be used on bots!")

        role = ctx.guild.get_role(764686546179325972)
        if role in member.roles:
            await member.remove_roles(role)
            return await ctx.send(f"Removed the common prefix role from {member}")
        else:
            await member.add_roles(role)
            return await ctx.send(f"Added the common prefix role to {member}")

def setup(bot):
    bot.add_cog(Mod(bot))
