import asyncio
import datetime
import os
import re

import aiohttp
from . import config # pylint: disable=relative-beyond-top-level
import discord
from discord.ext import commands

from . import checks  # pylint: disable=relative-beyond-top-level


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.has_permissions(administrator=True)
    @commands.command()
    async def add(self, ctx, member: discord.Member, level):
        level = level.lower()
        levels = ["bug_hunter", "developer", "administrator", "staff"]
        if level not in levels:
            await ctx.send(f"Thats not a valid option, the options are {', '.join([x for x in levels])}")
        await self.bot.pool.execute(f"UPDATE main_site_user SET {level} = True WHERE userid = $1", member.id)
        await ctx.send("Done")

    @commands.has_permissions(administrator=True)
    @commands.command()
    async def remove(self, ctx, member: discord.Member, level):
        level = level.lower()
        levels = ["bug_hunter", "developer", "administrator", "staff"]
        if level not in levels:
            await ctx.send(f"Thats not a valid option, the options are {', '.join([x for x in levels])}")
        await self.bot.pool.execute(f"UPDATE main_site_user SET {level} = False WHERE userid = $1", member.id)
        await ctx.send("Done")

    @checks.main_guild_only()
    @commands.has_permissions(administrator=True)
    @commands.group(invoke_without_command=True)
    async def certify(self, ctx, *, bot: discord.Member):
        if not bot.bot:
            await ctx.send("This user is not a bot")
            return

        bots = await self.bot.pool.fetchval("SELECT main_owner FROM main_site_bot WHERE certified = False AND awaiting_certification = True AND id = $1", bot.id)
        if bots == None:
            await ctx.send("This bot is not awaiting certification")
            return

        await self.bot.pool.execute("UPDATE main_site_bot SET certified = True, awaiting_certification = False WHERE id = $1", bot.id)

        embed = discord.Embed(description=f"Certified {bot.name}", color=discord.Color.blurple())
        await ctx.send(embed=embed)

        owner = ctx.guild.get_member(bots)
        em = discord.Embed(description=f"``{bot.name}`` by ``{owner}`` was certified", color=discord.Color.blurple())

        await self.bot.get_channel(716446098859884625).send(embed=em)
        certified_role = ctx.guild.get_role(716684142766456832)
        certified_dev_role = ctx.guild.get_role(716724317207003206)
        await owner.add_roles(certified_dev_role)
        await bot.add_roles(certified_role)

    @checks.main_guild_only()
    @commands.has_permissions(administrator=True)
    @certify.command()
    async def decline(self, ctx, bot: discord.Member, *, reason):
        if not bot.bot:
            await ctx.send("This user is not a bot")
            return

        bots = await self.bot.pool.fetchval("SELECT main_owner FROM main_site_bot WHERE awaiting_certification = True AND id = $1", bot.id)
        if bots == None:
            await ctx.send("This bot is not awaiting certification")
            return

        await self.bot.pool.execute("UPDATE main_site_bot SET awaiting_certification = False WHERE id = $1", bot.id)
        embed = discord.Embed(description=f"Denied certification for {bot.name}", color=discord.Color.blurple())
        await ctx.send(embed=embed)
        em = discord.Embed(description=f"``{bot.name}`` by ``{ctx.guild.get_member(bots)}`` was denied for certification for: \n```{reason}```", color=discord.Color.blurple())
        await self.bot.get_channel(716446098859884625).send(embed=em)

    @commands.is_owner()
    @commands.command()
    async def purge_cache(self, ctx):
        json = {"purge_everything": True}
        headers = {"X-Auth-Key": config.github_token,
                   "X-Auth-Email": config.github_email, "Content-Type": "application/json"}
        async with aiohttp.ClientSession().post(url="https://api.cloudflare.com/client/v4/zones/47697d23bd0d042fd63573cc9030177d/purge_cache/", headers=headers, json=json) as x:
            await ctx.send(f'{await x.json()}')

    @commands.is_owner()
    @commands.command()
    async def restart(self, ctx):
        await ctx.send("Restarting")
        os.system("systemctl restart blist")

    @commands.is_owner()
    @commands.command()
    async def update(self, ctx):
        """Pulls from a git remote and reloads modified cogs"""
        await ctx.channel.trigger_typing()
        process = await asyncio.create_subprocess_exec(
            "git", "pull",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        try:
            com = await asyncio.wait_for(process.communicate(), timeout=5)
            com = com[0].decode() + "\n" + com[1].decode()
        except asyncio.TimeoutError:
            await ctx.send("The process timed out.")

        reg = r"\S+(\.py)"
        reg = re.compile(reg)
        found = [match.group()[:-3].replace("/", ".")
                 for match in reg.finditer(com)]

        if found:
            updated = []
            for file in found:
                try:
                    self.bot.reload_extension(file)
                    updated.append(file)
                except (commands.ExtensionNotLoaded, commands.ExtensionNotFound):
                    continue
                except Exception as e:
                    embed = discord.Embed(title=f"There was an issue pulling from GitHub",
                                          description=f"\n```{e}```\n", color=discord.Color.red())
                    await ctx.send(embed=embed)
                    return

            if not updated:
                embed = discord.Embed(
                    title=f"No cogs were updated.", color=discord.Color.red())
                await ctx.send(embed=embed)
            else:
                embed = discord.Embed(
                    title=f"Updated cogs: " + ", ".join([f"`{text}`" for text in updated]), color=discord.Color.blurple())
                await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title=f"No cogs were updated.", color=discord.Color.red())
            await ctx.send(embed=embed)

    @commands.has_permissions(administrator=True)
    @commands.command()
    async def blacklist(self, ctx, userid: int, *, reason):
        check = await self.bot.pool.fetch(f"SELECT * FROM blacklisted WHERE userid = {userid}")
        if check is None or check == []:
            await self.bot.pool.execute("INSERT INTO blacklisted VALUES ($1, $2)", userid, reason)
            await ctx.send(f"Blacklisted ``{userid}`` for: \n```{reason}```")
        else:
            await self.bot.pool.execute("DELETE FROM blacklisted WHERE userid = $1", userid)
            await ctx.send(f"Unblacklisted ``{userid}`` for reason: \n```{reason}```")

    @checks.main_guild_only()
    @commands.has_permissions(administrator=True)
    @commands.command()
    async def staff(self, ctx):
        embed = discord.Embed(title="Staff", color=discord.Color.blurple(), description="""
---------------------
``Senior Administrators``
<@679118121943957504> :flag_us:
---------------------
``Administrators``
<@712737377524777001> :flag_us:
---------------------
``Senior Moderators``
<@482536364714491926> :flag_in:
<@670684162113667092> :flag_se:
---------------------
``Moderators``
<@150665783268212746> :flag_nl:
<@602656646979911738> :flag_eg:
<@296044953576931328> :flag_au:
---------------------
""")
        channel = ctx.guild.get_channel(716823743644696586)
        message = await channel.fetch_message(723641541486182410)
        await message.edit(embed=embed)
        await ctx.send("Updated")

    @checks.main_guild_only()
    @commands.has_permissions(administrator=True)
    @commands.command()
    async def rulesninfo(self, ctx):
        embed = discord.Embed(title="Blist Bot Rules/Requirements", color=discord.Color.blurple(), description="""
1. NSFW Commands must be restricted to NSFW only channels
2. Bots cannot be duplicates of other bots
3. Cannot contain scripts that affects the page
4. Bots must be online for testing.
5. Can not violate Discord ToS
6. Bots must have features and atleast 5 commands (Excluding any type of help commands, i.e. info, commands, etc.).
7. Cannot send level up messages
8. Cannot reply to other bots
9. Bots must not break server rules.
10. May not randomly respond to messages or commands not invoked without the specified prefix
11. Bots cannot have NSFW avatars
12. Must have a clean description, not junk filled
""")

        em = discord.Embed(title="Blist Server Rules", color=discord.Color.blurple(), description="""
1. Don't MINI MOD
2. Don't tag mod roles for no reason
3. Be respectful
4. Don't spam
5. Use common sense
6. No Evading punishments.
7. No NSFW.
8. Please use the channels accordingly.
9. Posting invites when it is relevant to the conversation (such as asking for a bot support server, minecraft server) is completely fine. However, advertising your server (or any advertising in general) is not okay.
10. Don't break Discord ToS
""")

        emb = discord.Embed(title="Links" , color=discord.Color.blurple(), description="""
[Site](https://blist.xyz)
[API](https://blist.xyz/api/)
[API Docs](https://docs.blist.xyz/)
[Certification Info](https://blist.xyz/certification/)
""")

        embe = discord.Embed(title="FAQ's", color=discord.Color.blurple(), description="""
**How did I get here?**
When logging in on the website, your grant us the ability to join guilds for you. Whenever you go to add a bot, you get added to the server.
\n**How do I add a bot?**
To add a bot, head over the https://blist.xyz/bot/add/.
\n**How long does the queue take?**
We try to get every bot done as fast as we can. Please take into consideration we have irl things to do sometimes.
""")

        channel = ctx.guild.get_channel(716717317320605736)
        rules = await channel.fetch_message(723643619315023873)
        bot_rules = await channel.fetch_message(723643619700899983)
        links = await channel.fetch_message(723643620313268291)
        faqs = await channel.fetch_message(723643620946870272)

        await rules.edit(embed=em)
        await bot_rules.edit(embed=embed)
        await links.edit(embed=emb)
        await faqs.edit(embed=embe)
        await ctx.send("Updated")

    @checks.main_guild_only()
    @commands.has_permissions(administrator=True)
    @commands.command()
    async def votesreset(self, ctx, *, message=None):
        top_bots = await self.bot.pool.fetch("SELECT * FROM main_site_bot ORDER BY monthly_votes DESC LIMIT 5")
        embed = discord.Embed(title=f"{datetime.datetime.utcnow().strftime('%B')} top 5 voted bots!", color=discord.Color.blurple())
        for bot in top_bots:
            embed.add_field(name=bot['name'], value=f"Votes: {bot['monthly_votes']}", inline=False)
        await ctx.send(content=message or "", embed=embed)
        bots = await self.bot.pool.fetch("SELECT * FROM main_site_bot")
        for bot in bots:
            await self.bot.pool.execute("UPDATE main_site_bot SET monthly_votes = 0 WHERE id = $1", bot["id"])
        await ctx.send("Monthly votes reset!")


def setup(bot):
    bot.add_cog(Admin(bot))