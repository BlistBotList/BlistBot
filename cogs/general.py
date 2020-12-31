from textwrap import dedent as wrap

import discord
from discord.ext import commands


class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def stats(self, ctx):
        """Shows info on Blist"""
        approved_bots = await self.bot.pool.fetchval(
            "SELECT COUNT(*) FROM main_site_bot WHERE approved = True AND denied = False")
        certified_bots = await self.bot.pool.fetchval(
            "SELECT COUNT(*) FROM main_site_bot WHERE certified = True")
        queued_bots = await self.bot.pool.fetchval(
            "SELECT COUNT(*) FROM main_site_bot WHERE approved = False AND denied = False")
        denied_bots = await self.bot.pool.fetchval(
            "SELECT COUNT(*) FROM main_site_bot WHERE approved = False AND denied = True")
        users = await self.bot.pool.fetchval("SELECT COUNT(*) FROM main_site_user")
        votes = await self.bot.pool.fetchval("SELECT COUNT(*) FROM main_site_vote")

        embed = discord.Embed(
            title="Blist Stats",
            description=wrap(
                f"""
                >>> ``Total Bots:`` {approved_bots + queued_bots + denied_bots}
                ``Total Approved Bots:`` {approved_bots}
                ``Total Certified Bots:`` {certified_bots}
                ``Total Denied Bots:`` {denied_bots}
                ``Total Queued Bots:`` {queued_bots}
                ``Total Users:`` {users}
                ``Total Votes:`` {votes}
                ``Bot Ping:`` {self.bot.latency * 1000:.2f}ms
                """
            ),
            color=discord.Color.blurple()
        )
        embed.set_thumbnail(url=str(ctx.guild.icon_url))
        await ctx.send(embed=embed)

    @commands.command(aliases=["lb"])
    async def leaderboard(self, ctx):
        """Sends the top 10 users on the user leaderboard"""
        leaderboard = await self.bot.pool.fetch("SELECT * FROM main_site_leveling ORDER BY level DESC, xp DESC LIMIT 10")
        embed = discord.Embed(title="User Leaderboard",
                              url="https://blist.xyz/leaderboard/")
        embed.set_thumbnail(url=str(ctx.guild.icon_url))
        place = 0
        for leader in leaderboard:
            place += 1
            user = await self.bot.pool.fetch("SELECT * FROM main_site_user WHERE unique_id = $1", leader["user_id"])
            user = user[0]
            embed.add_field(name=f"#{place} - {user['name']}#{user['discriminator']}",
                            value=f"Level: {leader['level']} | XP: {leader['xp']}", inline=False)

        await ctx.send(embed=embed)

    @commands.command()
    async def top(self, ctx):
        """Shows leaderboard information"""
        bots = await self.bot.pool.fetch("SELECT * FROM main_site_bot WHERE approved = True ORDER BY total_votes DESC LIMIT 5")
        embed = discord.Embed(title="Top 5 Voted Bots",
                              color=discord.Color.blurple())
        place = 0
        for x in bots:
            place += 1
            embed.add_field(
                name=f"**{place}.** ``{x['name']}: {x['total_votes']}``", value="** **", inline=False)
        await ctx.send(embed=embed)

    @commands.command(aliases=["bot"])
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
        github = f"[Click Here]({b['github']})" if b['github'] else None
        website = f"[Click Here]({b['website']})" if b['website'] else None
        support = f"[Click Here](https://discord.gg/{b['support_server']})" if b['support_server'] else None
        invite = f"[Click Here]({b['invite_url']})" if b['invite_url'] else f"[Click Here]({discord.utils.oauth_url(bot.id)})"
        privacy_url = b['privacy_policy_url'] if b['privacy_policy_url'] else None

        embed = discord.Embed(
            title=str(bot),
            description=wrap(
                f"""
                >>> Owner: ``{self.bot.main_guild.get_member(b['main_owner'])}``
                Library: ``{b['library']}``
                Prefix: ``{b['prefix']}``
                Tags: ``{tags}``
                Monthly Votes: ``{b['monthly_votes']}``
                All-Time Votes: ``{b['total_votes']}``
                Certified: ``{b['certified']}``
                Server Count: ``{b['server_count']}``
                Added: ``{b['joined'].strftime('%D')}``
                """
            ),
            color=discord.Color.blurple()
        )
        embed.add_field(
            name="**Links**",
            value=wrap(
                f"""
                >>> GitHub: {github}
                Privacy Policy: {privacy_url}
                Website: {website}
                Support: {support}
                Invite: {invite}
                Blist Link: [Click Here](https://blist.xyz/bot/{bot.id}/)
                """
            )
        )
        embed.add_field(name="Short Description",
                        value=b['short_description'], inline=False)
        embed.set_image(url=f"https://blist.xyz/api/bot/{bot.id}/widget")

        embed.set_thumbnail(url=bot.avatar_url)
        await ctx.send(embed=embed)

    @commands.command()
    async def bots(self, ctx, *, member: discord.Member = None):
        """Shows user's listed bots"""
        member = member or ctx.author
        if member.bot:
            await ctx.send("This user is a bot!")
            return

        bots = await self.bot.pool.fetch("SELECT * FROM main_site_bot WHERE main_owner = $1 AND approved = True", member.id)
        if not bots:
            await ctx.send("This user has no approved bots on our list")
            return

        listed_bots = []
        for x in bots:
            bot = self.bot.main_guild.get_member(x['id'])
            listed_bots.append(
                f"""
                [**{x['name']}**](https://blist.xyz/bot/{bot.id}/) ({bot.mention})
                > `Added:` {x['joined'].strftime('%A, %b %d, %X')}
                > `Certified:` {x['certified']}
                > `Prefix:` {x['prefix']}
                """
            )

        embed = discord.Embed(
            title=f"{member.name}'s bots",
            description=wrap(''.join(
                listed_bots)) if listed_bots else 'This user has not bots listed on out site',
            color=discord.Color.blurple()
        )
        await ctx.send(embed=embed)

    @commands.command()
    async def position(self, ctx):
        bots = await self.bot.pool.fetch("SELECT * FROM main_site_bot WHERE main_owner = $1 AND approved = False AND denied = False", ctx.author.id)
        if not bots:
            await ctx.send(f"{ctx.author.mention}, you have no bots in the queue!")
            return

        queue = await self.bot.pool.fetch("SELECT * FROM main_site_bot WHERE approved = False AND denied = False")

        for b in bots:
            await ctx.send(f"{b['name']} is #{queue.index(b) + 1} in the queue")

    @commands.command(aliases=["user", "member", "memberinfo", "ui", "whois"])
    async def userinfo(self, ctx, *, member: discord.Member = None):
        """Shows information on a user"""
        member = member or ctx.author
        user = await self.bot.pool.fetchval("SELECT unique_id FROM main_site_user WHERE userid = $1", member.id)
        leveling = await self.bot.pool.fetch("SELECT * FROM main_site_leveling WHERE user_id = $1", user)
        if leveling:
            em = discord.Embed(
                title=str(member),
                url=f"https://blist.xyz/user/{member.id}/",
                color=discord.Colour.blurple(),
                description=wrap(
                    f"""
                    >>> `Name:` {member.name} - #{member.discriminator}
                    `ID:` {member.id}
                    `Bot:` {member.bot}
                    `Status:` {str(member.status).title()}
                    `Highest Role:` {member.top_role.mention}
                    `Created Account:` {member.created_at.strftime("%c")}
                    `Joined This Server:` {member.joined_at.strftime("%c")}
                    `XP:` {leveling[0]["xp"]:,d}
                    `Level:` {leveling[0]["level"]:,d}
                    """
                )
            )
            em.set_thumbnail(url=member.avatar_url)
            await ctx.send(embed=em)
        else:
            em = discord.Embed(
                title=str(member),
                url=f"https://blist.xyz/user/{member.id}/",
                color=discord.Colour.blurple(),
                description=wrap(
                    f"""
                    >>> `Name:` {member.name} - #{member.discriminator}
                    `ID:` {member.id}
                    `Bot:` {member.bot}
                    `Status:` {str(member.status).title()}
                    `Highest Role:` {member.top_role.mention}
                    `Created Account:` {member.created_at.strftime("%c")}
                    `Joined This Server:` {member.joined_at.strftime("%c")}
                    """
                )
            )
            em.set_thumbnail(url=member.avatar_url)
            await ctx.send(embed=em)


def setup(bot):
    bot.add_cog(General(bot))