import discord
from discord.ext import commands


class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.main_guild = self.bot.get_guild(716445624517656727)

    @commands.command()
    async def stats(self, ctx):
        """Shows info on Blist"""
        approved_bots = await self.bot.pool.fetchval(
            "SELECT COUNT(*) FROM main_site_bot WHERE approved = True AND denied = False")
        queued_bots = await self.bot.pool.fetchval(
            "SELECT COUNT(*) FROM main_site_bot WHERE approved = False AND denied = False")
        denied_bots = await self.bot.pool.fetchval(
            "SELECT COUNT(*) FROM main_site_bot WHERE approved = False AND denied = True")
        users = await self.bot.pool.fetchval("SELECT COUNT(*) FROM main_site_user")
        votes = await self.bot.pool.fetchval("SELECT COUNT(*) FROM main_site_vote")

        embed = discord.Embed(
            title = "Blist Stats",
            description =
            f"""
            >>> ``Total Bots:`` {approved_bots + queued_bots}
            ``Total Approved Bots:`` {approved_bots}
            ``Total Denied Bots:`` {denied_bots}
            ``Total Queued Bots:`` {queued_bots}
            ``Total Users:`` {users}
            ``Total Votes:`` {votes}
            ``Bot Ping:`` {self.bot.latency * 1000:.2f}ms
            """,
            color = discord.Color.blurple()
        )
        embed.set_thumbnail(url = str(ctx.guild.icon_url))
        await ctx.send(embed = embed)

    @commands.command()
    async def top(self, ctx):
        """Shows leaderboard information"""
        bots = await self.bot.pool.fetch(
            "SELECT * FROM main_site_bot WHERE approved = True ORDER BY total_votes DESC LIMIT 5")
        embed = discord.Embed(title = "Top 5 Voted Bots", color = discord.Color.blurple())
        place = 0
        for x in bots:
            place += 1
            embed.add_field(name = f"**{place}.** ``{x['name']}: {x['total_votes']}``", value = "** **", inline = False)
        await ctx.send(embed = embed)

    @commands.command(aliases = ["bot"])
    async def botinfo(self, ctx, *, bot: discord.Member):
        """Shows information on a listed bot"""
        if not bot.bot:
            await ctx.send("This is not a bot!")
            return

        bots = await self.bot.pool.fetch("SELECT * FROM main_site_bot WHERE id = $1", bot.id)
        if not bots:
            await ctx.send("This bot is not on our list")
            return

        tags = ', '.join([str(x) for x in bots[0]['tags']])
        b = bots[0]
        if b['github'] == '':
            github = None
        else:
            github = f"[Click Here]({b['github']})"

        if b['website'] == '':
            website = None
        else:
            website = f"[Click Here]({b['website']})"

        if b['support_server'] == '':
            support = None
        else:
            support = f"[Click Here](https://discord.gg/{b['support_server']})"

        if b['invite_url'] == '':
            invite = f"[Click Here]({discord.utils.oauth_url(bot.id)})"
        else:
            invite = f"[Click Here]({b['invite_url']})"

        embed = discord.Embed(
            title = f"{bot.name}#{bot.discriminator}",
            description =
            f"""
            >>> Owner: ``{self.main_guild.get_member(b['main_owner'])}``
            Library: ``{b['library']}``
            Prefix: ``{b['prefix']}``
            Tags: ``{tags}``
            Monthly Votes: ``{b['monthly_votes']}``
            All-Time Votes: ``{b['total_votes']}``
            Certified: ``{b['certified']}``
            Server Count: ``{b['server_count']}``
            Added: ``{b['joined'].strftime('%D')}``
            """,
            color = discord.Color.blurple()
        )
        embed.add_field(
            name = "**Links**",
            value =
            f"""
            >>> GitHub: {github}
            Privacy Policy: {b['privacy_policy_url'] or 'None'}
            Website: {website}
            Support: {support}
            Invite: {invite}
            Blist Link: [Click Here](https://blist.xyz/bot/{bot.id}/)
            """
        )
        embed.add_field(name = "Short Description", value = b['short_description'], inline = False)
        embed.set_image(url = f"https://blist.xyz/api/bot/{bot.id}/widget")

        embed.set_thumbnail(url = bot.avatar_url)
        await ctx.send(embed = embed)

    @commands.command()
    async def bots(self, ctx, *, member: discord.Member = None):
        """Shows user's listed bots"""
        member = member or ctx.author
        if member.bot:
            await ctx.send("This user is a bot!")
            return

        bots = await self.bot.pool.fetch("SELECT * FROM main_site_bot WHERE main_owner = $1 AND approved = True",
                                         member.id)
        if bots is None:
            await ctx.send("This user has no approved bots on our list")
            return

        listed_bots = []
        for x in bots:
            listed_bots.append(f"**{x['name']}** ({self.main_guild.get_member(x['id']).mention})")

        embed = discord.Embed(
            title = f"{member.name}'s bots",
            description = ">>>" + '\n '.join(
                listed_bots) if listed_bots else 'This user has not bots listed on out site',
            color = discord.Color.blurple()
        )
        await ctx.send(embed = embed)

    @commands.command()
    async def position(self, ctx):
        bots = await self.bot.pool.fetch(
            "SELECT * FROM main_site_bot WHERE main_owner = $1 AND approved = False AND denied = False", ctx.author.id)
        if not bots:
            await ctx.send(f"{ctx.author.mention}, you have no bots in the queue!")
            return

        queue = await self.bot.pool.fetch("SELECT * FROM main_site_bot WHERE approved = False AND denied = False")

        for b in bots:
            await ctx.send(f"{b['name']} is #{queue.index(b) + 1} in the queue")

    @commands.command(aliases = ["user", "member", "memberinfo", "ui"])
    async def userinfo(self, ctx, *, member: discord.Member = None):
        """Shows information on a user"""
        if member is None:
            member = ctx.author

        embed = discord.Embed(title = member.name, color = discord.Color.blurple())
        embed.set_thumbnail(url = member.avatar_url)
        embed.add_field(name = "Name:", value = member.name)
        embed.add_field(name = "Discriminator:", value = f"#{member.discriminator}")
        embed.add_field(name = "ID:", value = member.id)
        embed.add_field(name = "Bot:", value = member.bot)
        embed.add_field(name = "Status:", value = member.status)
        embed.add_field(name = "Highest Role:", value = member.top_role.mention)
        embed.add_field(name = "Created Account:", value = member.created_at.strftime("%c"), inline = False)
        embed.add_field(name = "Joined This Server:", value = member.joined_at.strftime("%c"), inline = False)
        await ctx.send(embed = embed)


def setup(bot):
    bot.add_cog(General(bot))
