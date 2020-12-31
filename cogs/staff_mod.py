import asyncio
import datetime
import re
from textwrap import dedent as wrap

import asyncpg
import discord
import humanize
from discord.ext import commands, flags

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
            time = humanize.naturaldelta(
                mute_info - datetime.datetime.utcnow())
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
        embed.set_author(name=mod, icon_url=mod.avatar_url)
        embed.set_footer(text=f"Case #{number}")
        embed.timestamp = info["time"]

        message = await self.bot.main_guild.get_channel(716719009499971685).fetch_message(info['messageid'])
        await message.edit(embed=embed)

    @commands.has_permissions(manage_messages=True)
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

    @flags.add_flag("-t", "--title", type = str, default = 'Official Warning')
    @flags.add_flag("-f", "--footer", type = str, default = 'blist.xyz')
    @flags.add_flag("message", nargs = "+")
    @commands.has_permissions(manage_messages = True)
    @commands.command(cls = flags.FlagCommand)
    async def dm(self, ctx, member: discord.Member, **arguments):
        """
        Send a official DM on behalf of Blist.

        **Required Arguments:**
        message | The message you want to send, this must be first.

        Optional **Arguments:**
        **--title**/-t | Choose a different title. Defaults to 'Official Warning'.
        **--footer**/-f | Choose a different footer with the blist logo. Default to 'blist.xyz'.
        ----
        **[AUTHOR]** - This will get replaced with your name with discriminator.
        **[MEMBER]** - This will get replaced with the target's name with discriminator.
        **[AUTHOR_NAME]** - This will get replaced with your name without discriminator.
        **[MEMBER_NAME]** - This will get replaced with the target's name without discriminator.
        **[SERVER]** - This will get replaced with the server's current name.
        **[SITE]** - This will get replaced with https://blist.xyz
        **[API]** - This will get replaced with https://blist.xyz/api/v2/
        **[API_DOCS]** - This will get replaced with https://blist.xyz/docs
        **[BOT_SITE:bot_id_here]** - This will get replaced with the given bot's link to the site. Will ignore if id isn't a bot.
        **[BOT:bot_id_here]** - This will get replaced with the given bot's name with discriminator. Will ignore if id isn't a bot.
        **[BOT_NAME:bot_id_here]** - This will get replaced with the given bot's name without discriminator. Will ignore if id isn't a bot.
        """

        def parse_arguments(text: str):
            def get_bot(reg):
                reg_type = str(reg.group(1))
                m = self.bot.main_guild.get_member(int(reg.group(2)))
                if not m.bot or not m:
                    return str(reg.group())  # ignore it, kinda
                if reg_type == "BOT":
                    return str(m)
                if reg_type == "BOT_NAME":
                    return str(m.name)
                if reg_type == "BOT_SITE":
                    return f"https://blist.xyz/bot/{m.id}"

            dict_of_arguments = {
                "[AUTHOR]": str(ctx.author),
                "[MEMBER]": str(member),
                "[AUTHOR_NAME]": str(ctx.author.name),
                "[MEMBER_NAME]": str(member.name),
                "[SERVER]": str(ctx.guild.name),
                "[SITE]": "https://blist.xyz",
                "[API]": "https://blist.xyz/api/v2/",
                "[API_DOCS]": "https://blist.xyz/docs",
            }
            has_bot_arg = [x for x in re.finditer("\[(BOT|BOT_NAME|BOT_SITE):([0-9]{18})]", text)]
            if has_bot_arg:
                for match in has_bot_arg:
                    try:
                        dict_of_arguments[match.group()] = get_bot(match)
                    except (ValueError, KeyError):
                        pass

            search_keys = map(lambda x: re.escape(x), dict_of_arguments.keys())
            regex = re.compile('|'.join(search_keys))
            res = regex.sub(lambda m: dict_of_arguments[m.group()], text)

            return res

        if member.bot:
            return await ctx.send(f"I can't dm a bot.")

        message = parse_arguments(str(' '.join(arguments['message'])))
        embed = discord.Embed(
            title = arguments['title'],
            description = message,
            color = discord.Color.blurple()
        )
        embed.set_author(name = ctx.author, icon_url = ctx.author.avatar_url)
        embed.set_footer(text = arguments['footer'], icon_url = self.bot.user.avatar_url)
        try:
            await ctx.send(f'Sent a message to **{member}**.', embed = embed)
            await member.send(embed = embed)
        except discord.Forbidden:
            await ctx.send(f'{member.mention} has DMs disabled or has blocked me.')


def setup(bot):
    bot.add_cog(Mod(bot))