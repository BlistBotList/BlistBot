from textwrap import dedent as wrap
from typing import Union

import discord
import googletrans
from discord.ext import commands, flags
from utils import checks


class Staff(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.translator = googletrans.Translator()

    @commands.has_permissions(kick_members=True)
    @commands.group(invoke_without_command=True, aliases=["q"])
    async def queue(self, ctx):
        bots = await self.bot.pool.fetch("SELECT * FROM main_site_bot WHERE approved = False AND denied = False")
        if not bots:
            await ctx.send("There are no bots in the queue")
            return

        listed_bots = []
        for x in bots:
            invite = str(
                discord.utils.oauth_url(x['id'], guild=self.bot.verification_guild)) + "&disable_guild_select=true"
            listed_bots.append(f"{x['username']} [Invite]({invite})")

        embed = discord.Embed(
            title="Queue",
            url="https://blist.xyz/staff#verification",
            description='\n'.join(listed_bots) if listed_bots else "All Clear",
            color=discord.Color.blurple()
        )
        await ctx.send(embed=embed)

    @checks.main_guild_only()
    @queue.command(aliases=["c"])
    async def certification(self, ctx):
        bots = await self.bot.pool.fetch("SELECT * FROM main_site_bot WHERE awaiting_certification = True")
        if bots is None:
            await ctx.send("There are no bots in the certification queue")
            return

        listed_bots = []
        for x in bots:
            listed_bots.append(f"{x['username']} | Added: {x['added']}")

        embed = discord.Embed(
            title="Certification Queue",
            description='\n'.join(listed_bots) if listed_bots else "All Clear",
            color=discord.Color.blurple()
        )
        await ctx.send(embed=embed)

    @checks.verification_guild_only()
    @commands.has_permissions(kick_members=True)
    @commands.command()
    async def approve(self, ctx, *, bot: discord.Member):
        if not bot.bot:
            await ctx.send("This is not a bot.")
            return

        bots = await self.bot.pool.fetchrow(
            "SELECT main_owner, referred_by FROM main_site_bot WHERE approved = False AND denied = False AND id = $1", bot.id)
        if not bots:
            await ctx.send("This bot is not awaiting approval")
            return

        owner = self.bot.main_guild.get_member(bots["main_owner"])
        if not owner:
            await ctx.send(f"{ctx.author.mention}, The owner of this bot has left the main server, deny it!")
            return

        if bots["referred_by"] != "":
            user_id = await self.bot.pool.fetchval("SELECT id FROM main_site_user WHERE referrer_code  = $1", bots["referred_by"])
            if user_id:
                await self.bot.pool.execute("UPDATE main_site_user SET referrals = referrals + 1 WHERE id = $1", user_id)

        await self.bot.pool.execute("UPDATE main_site_user SET developer = True WHERE id = $1", bots["main_owner"])
        await self.bot.pool.execute("UPDATE main_site_bot SET approved = True WHERE id = $1", bot.id)
        await self.bot.mod_pool.execute("UPDATE staff SET approved = approved + 1 WHERE userid = $1", ctx.author.id)

        queued_bots = await self.bot.pool.fetchval(
            "SELECT COUNT(*) FROM main_site_bot WHERE approved = False AND denied = False")
        invite = str(discord.utils.oauth_url(
            bot.id, guild=self.bot.main_guild)) + "&disable_guild_select=true"
        embed = discord.Embed(
            title=f"Approved {bot.name}",
            description=f"[Invite!]({invite})\n\nThere are {queued_bots} bot(s) in the queue.",
            color=discord.Color.blurple()
        )
        await self.bot.verification_guild.get_channel(763183376311517215).send(content=ctx.author.mention, embed=embed)
        em = discord.Embed(
            description=f"``{bot}`` by ``{self.bot.main_guild.get_member(bots['main_owner'])}`` was approved by ``{ctx.author}``",
            color=discord.Color.blurple())
        await self.bot.get_channel(716446098859884625).send(embed=em)

        dev_role = self.bot.main_guild.get_role(716684805286133840)

        try:
            await owner.send(f"Your bot `{bot}` was approved!")
        except (discord.Forbidden, AttributeError):
            pass

        try:
            await owner.add_roles(dev_role)
        except AttributeError:
            pass

        await bot.kick()
        self.bot.dispatch("bot_conclusion", bot, ctx.author)
        bots = await self.bot.pool.fetchval("SELECT COUNT(*) FROM main_site_bot")
        await self.bot.change_presence(activity=discord.Game(name=f"Watching {bots} bots"))

    @commands.has_permissions(kick_members=True)
    @commands.command()
    async def deny(self, ctx, bot: Union[discord.Member, discord.User], *, reason):
        if not bot.bot:
            await ctx.send("This user is not a bot")
            return

        bots = await self.bot.pool.fetchval(
            "SELECT main_owner FROM main_site_bot WHERE approved = False AND denied = False AND id = $1", bot.id)
        if not bots:
            await ctx.send("This bot is not awaiting approval")
            return

        await self.bot.mod_pool.execute("UPDATE staff SET denied = denied + 1 WHERE userid = $1", ctx.author.id)

        try:
            owner = self.bot.main_guild.get_member(bots)
            await owner.send(f"Your bot `{bot}` was denied!")
        except (discord.Forbidden, AttributeError):
            pass

        await self.bot.pool.execute("UPDATE main_site_bot SET denied = True WHERE id = $1", bot.id)
        embed = discord.Embed(
            description=f"Denied {bot.name}", color=discord.Color.red())
        await ctx.send(embed=embed)
        em = discord.Embed(
            description=f"``{bot}`` by ``{self.bot.main_guild.get_member(bots)}`` was denied by ``{ctx.author}`` for: \n```{reason}```",
            color=discord.Color.red())
        await self.bot.get_channel(716446098859884625).send(embed=em)
        await bot.kick(reason="Bot Denied")
        self.bot.dispatch("bot_conclusion", bot, ctx.author)

    @checks.main_guild_only()
    @commands.has_permissions(kick_members=True)
    @commands.command()
    async def delete(self, ctx, bot: Union[discord.Member, int], *, reason):
        bot_user = None
        if isinstance(bot, discord.Member):
            bot_user = bot
        if isinstance(bot, int):
            bot_user = self.bot.main_guild.get_member(bot)

        if bot_user and not bot_user.bot:
            await ctx.send("That is not a bot.")
            return

        bots = await self.bot.pool.fetchrow(
            "SELECT main_owner, username, certified, discriminator FROM main_site_bot WHERE approved = True AND id = $1", bot_user.id if bot_user else bot)
        if not bots:
            await ctx.send("This bot is not on the list")
            return

        bot_db = await self.bot.pool.fetchval("SELECT unique_id FROM main_site_bot WHERE id = $1", bot_user.id if bot_user else bot)
        await self.bot.pool.execute("DELETE FROM main_site_vote WHERE bot_id = $1", bot_db)
        await self.bot.pool.execute("DELETE FROM main_site_review WHERE bot_id = $1", bot_db)
        await self.bot.pool.execute("DELETE FROM main_site_auditlogaction WHERE bot_id = $1", bot_db)
        await self.bot.pool.execute("DELETE FROM main_site_bot WHERE id = $1", bot_user.id if bot_user else bot)

        embed = discord.Embed(
            description=f"Deleted {bots['username']}", color=discord.Color.red())
        await ctx.send(embed=embed)

        em = discord.Embed(
            description=f"``{bots['username']}#{bots['discriminator']}`` by ``{ctx.guild.get_member(bots['main_owner']) or bots['main_owner']}`` was deleted by ``{ctx.author}`` for: \n```{reason}```",
            color=discord.Color.red())
        await self.bot.get_channel(716446098859884625).send(embed=em)

        member = ctx.guild.get_member(bots['main_owner'])
        if member and bots['certified'] is True:
            certified_dev_role = ctx.guild.get_role(716724317207003206)
            await member.remove_roles(certified_dev_role)

        has_other_bots = await self.bot.pool.fetch("SELECT * FROM main_site_bot WHERE main_owner = $1",
                                                   bots['main_owner'])
        if not has_other_bots and member:
            dev_role = ctx.guild.get_role(716684805286133840)
            await member.remove_roles(dev_role)
            await self.bot.pool.execute("UPDATE main_site_user SET developer = False WHERE id = $1",
                                        bots['main_owner'])

        if bot_user is not None:
            await bot_user.kick(reason="Bot Deleted")

    @commands.has_permissions(kick_members=True)
    @commands.command()
    async def say(self, ctx, *, msg: commands.clean_content):
        """Make blist repeat what you said"""
        await ctx.send(msg)

    @flags.add_flag("--to", type=str, default="en")
    @flags.add_flag("--from", type=str, default="auto")
    @flags.add_flag("message", nargs="+")
    @commands.has_permissions(kick_members=True)
    @commands.command(hidden=True, aliases=["t"], cls=flags.FlagCommand)
    async def translate(self, ctx, **arguments):
        """
        Translates a message to English (default) using Google translate.

        **Optional Arguments**:
        --to | translate text to x language. Example: `b!translate cool --to en`
        --from | translate text from x language. Example: `b!translate cool --from nl`
        """
        message = ' '.join(arguments['message'])
        try:
            translated = self.translator.translate(
                message, dest=arguments['to'], src=arguments['from'])
        except ValueError:
            return await ctx.send(
                embed=discord.Embed(description="That is not a valid language!", color=discord.Color.red()))

        src = googletrans.LANGUAGES.get(
            translated.src, '(auto-detected)').title()
        dest = googletrans.LANGUAGES.get(translated.dest, 'Unknown').title()
        embed = discord.Embed(color=discord.Color.blurple())
        embed.add_field(name=f"{src} ({translated.src})",
                        value=translated.origin, inline=False)
        embed.add_field(name=f"{dest} ({translated.dest})",
                        value=translated.text, inline=False)
        await ctx.send(embed=embed)

    @commands.command()
    async def staff(self, ctx, member: discord.Member = None):
        if not member:
            member = ctx.author

        query = await self.bot.mod_pool.fetch("SELECT * FROM staff WHERE userid = $1", member.id)
        if not query:
            return await ctx.send("This user is not staff!")
        query = query[0]
        embed = discord.Embed(
            color=discord.Color.blurple(),
            description=wrap(
                f"""
                >>> Staff Since: ``{query['joinedat'].strftime("%F")}``
                Bots Approved: ``{query['approved']}``
                Bots Denied: ``{query['denied']}``
                Country: ``{query['country_code'] or 'Not Specified'}``
                Rank: ``{query['rank'] or 'Not Specified'}``
                """
            )
        )
        embed.set_author(name=member, icon_url=str(member.avatar_url))
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Staff(bot))