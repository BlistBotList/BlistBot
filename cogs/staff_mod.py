from datetime import datetime
from discord import message
from discord.ext import commands
import discord

class Mod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.mod_log = self.bot.main_guild.get_channel(716719009499971685)

    async def do_case(self, ctx, member: discord.Member, reason, type):
        last_case_number = await self.bot.mod_pool.fetchval("SELECT COUNT(*) FROM action")
        embed = discord.Embed(title=type.title(), color=discord.Color.blurple(), description=f"""
**__Victim:__** {member} ({member.id})
**__Reason:__** ``{reason or f'No reason was set. Do b!reason {last_case_number + 1} <reason> to do so.'}``
""")
        embed.set_author(name=ctx.author, icon_url=(ctx.author.avatar_url))
        embed.set_footer(text=f"Case #{last_case_number + 1}")
        embed.timestamp = datetime.utcnow()
        message = await self.mod_log.send(embed=embed)
        await self.bot.mod_pool.execute("INSERT INTO action VALUES($1, $2, $3, $4, $5, $6)", member.id, ctx.author.id, reason or 'None', message.id, type, datetime.utcnow())
        #userid, modid, reason, messageid, type, time, id

    @commands.has_permissions(ban_members=True)
    @commands.command()
    async def ban(self, ctx, member: discord.Member, *, reason=None):
        if member.bot:
            return await ctx.send(f"You cannot ban bots! Use `b!delete @{member} <reason>` to do so.")

        if not ctx.author.top_role > member.top_role:
            return await ctx.send("You cannot ban someone higher than you!")

        await self.do_case(ctx, member, reason, "Ban")
        await member.ban(reason=reason)

    @commands.has_permissions(kick_members=True)
    @commands.command()
    async def kick(self, ctx, member: discord.Member, *, reason=None):
        if member.bot:
            return await ctx.send("You cannot kick bots! Use `b!delete @{member} <reason>` to do so.")

        if not ctx.author.top_role > member.top_role:
            return await ctx.send(f"You cannot kick someone higher than you!")

        await self.do_case(ctx, member, reason, "Kick")
        await member.kick(reason=reason)

    @commands.has_permissions(manage_messages=True)
    @commands.command()
    async def warn(self, ctx, member: discord.Member, *, reason=None):
        if member.bot:
            return await ctx.send("You cannot warn bots!")

        if not ctx.author.top_role > member.top_role:
            return await ctx.send(f"You cannot warn someone higher than you!")

        await self.do_case(ctx, member, reason, "Warn")

    @commands.command()
    async def purge(self, ctx, amount: int):
        if amount < 1:
            return await ctx.send("Cannot purge that amount of messages!")
        await ctx.channel.purge(limit=amount + 1)

    @commands.command()
    async def case(self, ctx, number: int):
        info = await self.bot.mod_pool.fetch("SELECT * FROM action WHERE id = $1", number)
        if info == []:
            return await ctx.send(f"Case {number} does not exist!")
        else:
            info = info[0]

        target = ctx.guild.get_member(info['userid'])
        mod = ctx.guild.get_member(info['modid'])

        embed = discord.Embed(title=info['type'].title(), color=discord.Color.blurple(), description=f"""
**__Mod:__** {mod} ({mod.id})
**__Victim:__** {target} ({target.id})
**__Reason:__** ``{info['reason']}``
**__Time:__** ``{info['time'].strftime('%c')}``
""")
        await ctx.send(embed=embed)

    @commands.command()
    async def reason(self, ctx, number: int, *, reason):
        info = await self.bot.mod_pool.fetch("SELECT * FROM action WHERE id = $1", number)
        if info == []:
            return await ctx.send(f"Case {number} does not exist!")
        else:
            info = info[0]

        await ctx.send(f"Set the reason to: `{reason}`")
        await self.bot.mod_pool.execute("UPDATE action SET reason = $1 WHERE id = $2", reason, number)
        
        target = ctx.guild.get_member(info['userid'])
        mod = ctx.guild.get_member(info['modid'])

        embed = discord.Embed(title=info['type'].title(), color=discord.Color.blurple(), description=f"""
**__Victim:__** {target} ({target.id})
**__Reason:__** ``{reason}``
""")
        embed.set_author(name=mod, icon_url=(mod.avatar_url))
        embed.set_footer(text=f"Case #{number}")
        embed.timestamp = info["time"]

        message = await self.mod_log.fetch_message(info['messageid'])
        await message.edit(embed=embed)

def setup(bot):
    bot.add_cog(Mod(bot))