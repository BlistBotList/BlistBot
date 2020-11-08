import discord
import googletrans
from discord.ext import commands
from . import checks  # pylint: disable=relative-beyond-top-level
from typing import Union



class Staff(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.verification_guild = self.bot.get_guild(734527161289015337)
        self.main_guild = self.bot.get_guild(716445624517656727)

    @commands.has_permissions(kick_members = True)
    @commands.group(invoke_without_command = True)
    async def queue(self, ctx):
        bots = await self.bot.pool.fetch("SELECT * FROM main_site_bot WHERE approved = False AND denied = False")
        if not bots:
            await ctx.send("There are no bots in the queue")
            return

        listed_bots = []
        for x in bots:
            invite = str(
                discord.utils.oauth_url(x['id'], guild = self.verification_guild)) + "&disable_guild_select=true"
            listed_bots.append(f"{x['name']} [Invite]({invite})")

        embed = discord.Embed(
            title = "Queue",
            description = '\n'.join(listed_bots) if listed_bots else "All Clear",
            color = discord.Color.blurple()
        )
        await ctx.send(embed = embed)

    @checks.main_guild_only()
    @queue.command(aliases = ["c"])
    async def certification(self, ctx):
        bots = await self.bot.pool.fetch("SELECT * FROM main_site_bot WHERE awaiting_certification = True")
        if bots is None:
            await ctx.send("There are no bots in the certification queue")
            return

        listed_bots = []
        for x in bots:
            listed_bots.append(f"{x['name']} | Added: {x['joined']}")

        embed = discord.Embed(
            title = "Certification Queue",
            description = '\n'.join(listed_bots) if listed_bots else "All Clear",
            color = discord.Color.blurple()
        )
        await ctx.send(embed = embed)

    @checks.verification_guild_only()
    @commands.has_permissions(kick_members = True)
    @commands.command()
    async def approve(self, ctx, *, bot: discord.Member):
        if not bot.bot:
            await ctx.send("This is not a bot.")
            return

        bots = await self.bot.pool.fetchval(
            "SELECT main_owner FROM main_site_bot WHERE approved = False AND denied = False AND id = $1", bot.id)
        if not bots:
            await ctx.send("This bot is not awaiting approval")
            return

        owner = self.main_guild.get_member(bots)
        if not owner:
            await ctx.send(f"{ctx.author.mention}, The owner of this bot has left the main server, deny it!")
            return

        await self.bot.pool.execute("UPDATE main_site_user SET developer = True WHERE userid = $1", bots)
        await self.bot.pool.execute("UPDATE main_site_bot SET approved = True WHERE id = $1", bot.id)

        queued_bots = await self.bot.pool.fetchval(
            "SELECT COUNT(*) FROM main_site_bot WHERE approved = False AND denied = False")
        invite = str(discord.utils.oauth_url(bot.id, guild = self.main_guild)) + "&disable_guild_select=true"
        embed = discord.Embed(
            title = f"Approved {bot.name}",
            description = f"[Invite!]({invite})\n\nThere are still {queued_bots} in the queue.",
            color = discord.Color.blurple()
        )
        await self.verification_guild.get_channel(763183376311517215).send(content = ctx.author.mention, embed = embed)

        em = discord.Embed(
            description = f"``{bot.name}`` by ``{self.main_guild.get_member(bots)}`` was approved by ``{ctx.author.name}``",
            color = discord.Color.blurple())
        await self.bot.get_channel(716446098859884625).send(embed = em)

        dev_role = self.main_guild.get_role(716684805286133840)

        try:
            await owner.send(f"Your bot `{bot}` was approved!")
        except (discord.Forbidden, AttributeError):
            pass

        try:
            await owner.add_roles(dev_role)
        except AttributeError:
            pass

        await bot.kick()
        bots = await self.bot.pool.fetchval("SELECT COUNT(*) FROM main_site_bot")
        await self.bot.change_presence(activity = discord.Game(name = f"Watching {bots} bots"))

    @checks.verification_guild_only()
    @commands.has_permissions(kick_members = True)
    @commands.command()
    async def deny(self, ctx, bot: discord.Member, *, reason):
        if not bot.bot:
            await ctx.send("This user is not a bot")
            return

        bots = await self.bot.pool.fetchval(
            "SELECT main_owner FROM main_site_bot WHERE approved = False AND denied = False AND id = $1", bot.id)
        if not bots:
            await ctx.send("This bot is not awaiting approval")
            return

        try:
            owner = self.main_guild.get_member(bots)
            await owner.send(f"Your bot `{bot}` was denied!")
        except (discord.Forbidden, AttributeError):
            pass

        await self.bot.pool.execute("UPDATE main_site_bot SET denied = True WHERE id = $1", bot.id)
        embed = discord.Embed(description = f"Denied {bot.name}", color = discord.Color.red())
        await ctx.send(embed = embed)
        em = discord.Embed(
            description = f"``{bot.name}`` by ``{self.main_guild.get_member(bots)}`` was denied by ``{ctx.author.name}`` for: \n```{reason}```",
            color = discord.Color.red())
        await self.bot.get_channel(716446098859884625).send(embed = em)
        await bot.kick(reason = "Bot Denied")

    @checks.main_guild_only()
    @commands.has_permissions(kick_members = True)
    @commands.command()
    async def delete(self, ctx, bot: Union[discord.Member, int], *, reason):
        bot_user = None
        if isinstance(bot, discord.Member):
            bot_user = bot
        if isinstance(bot, int):
            bot_user = self.main_guild.get_member(bot)

        if bot_user and not bot_user.bot:
            await ctx.send("That is not a bot.")
            return

        bots = await self.bot.pool.fetchrow(
            "SELECT main_owner, name, certified FROM main_site_bot WHERE approved = True AND id = $1", bot_user.id)
        if not bots:
            await ctx.send("This bot is not on the list")
            return

        await self.bot.pool.execute("DELETE FROM main_site_bot WHERE id = $1", bot_user.id)

        embed = discord.Embed(description = f"Deleted {bots['name']}", color = discord.Color.red())
        await ctx.send(embed = embed)

        em = discord.Embed(
            description = f"``{bots['name']}`` by ``{ctx.guild.get_member(bots['main_owner']) or bots['main_owner']}`` was deleted by ``{ctx.author.name}`` for: \n```{reason}```",
            color = discord.Color.red())
        await self.bot.get_channel(716446098859884625).send(embed = em)

        member = ctx.guild.get_member(bots['main_owner'])
        if bots['certified'] is True:
            certified_dev_role = ctx.guild.get_role(716724317207003206)
            await member.remove_roles(certified_dev_role)

        has_other_bots = await self.bot.pool.fetch("SELECT * FROM main_site_bot WHERE main_owner = $1",
                                                   bots['main_owner'])
        if not has_other_bots and member:
            dev_role = ctx.guild.get_role(716684805286133840)
            await member.remove_roles(dev_role)
            await self.bot.pool.execute("UPDATE main_site_user SET developer = False WHERE userid = $1",
                                        bots['main_owner'])

        if bot_user is not None:
            await bot_user.kick(reason = "Bot Deleted")

    @commands.has_permissions(kick_members = True)
    @commands.command()
    async def say(self, ctx, *, msg: commands.clean_content):
        """Make blist repeat what you said"""
        await ctx.send(msg)

    @commands.has_permissions(kick_members = True)
    @commands.command(hidden = True)
    async def translate(self, ctx, to, *, message: commands.clean_content):
        """Translates a message to English using Google translate."""
        translator = googletrans.Translator()
        try:
            translated = translator.translate(message, dest = to)
        except ValueError:
            return await ctx.send("That is not a valid language")
        src = googletrans.LANGUAGES.get(translated.src, '(auto-detected)').title()
        dest = googletrans.LANGUAGES.get(translated.dest, 'Unknown').title()
        embed = discord.Embed()
        embed.add_field(name = f"{src} ({translated.src})", value = translated.origin.title(), inline = False)
        embed.add_field(name = f"{dest} ({translated.dest})", value = translated.text.title(), inline = False)
        await ctx.send(embed = embed)


def setup(bot):
    bot.add_cog(Staff(bot))
