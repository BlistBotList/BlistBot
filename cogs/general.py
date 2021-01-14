from textwrap import dedent as wrap
from datetime import datetime

import asyncio
import discord
from discord.ext import commands, menus, flags

# subclass menu to add numbers button.
class MenuMain(menus.MenuPages):
    def __init__(self, source, **kwargs):
        super().__init__(source=source, check_embeds=True, **kwargs)

    @menus.button('\N{INPUT SYMBOL FOR NUMBERS}', position=menus.Last(1.5))
    async def numbered_page(self, payload):
        """lets you type a page number to go to"""
        channel = self.message.channel
        author_id = payload.user_id
        to_delete = [await channel.send('What page do you want to go to?')]

        def message_check(m):
            return m.author.id == author_id and channel == m.channel and m.content.isdigit()

        try:
            msg = await self.bot.wait_for('message', check=message_check, timeout=30.0)
        except asyncio.TimeoutError:
            to_delete.append(await channel.send('Took too long.'))
            await asyncio.sleep(5)
        else:
            page = int(msg.content)
            to_delete.append(msg)
            await self.show_checked_page(page - 1)

        try:
            await channel.delete_messages(to_delete)
        except Exception:
            pass


class LeaderboardPage(menus.ListPageSource):
    def __init__(self, entries, **kwargs):
        super().__init__(entries, **kwargs)

    async def format_page(self, menu, entry):
        em = discord.Embed(title="User Leaderboard | Pagination", color=discord.Color.blurple(),
                           url="https://blist.xyz/leaderboard/")
        em.set_thumbnail(url=str(menu.ctx.guild.icon_url))
        em.set_footer(text=f"Page: {menu.current_page + 1} / {self.get_max_pages()}")
        for name,value in entry:
            em.add_field(name=name, value=value, inline=False)

        return em


class AnnouncementPage(menus.ListPageSource):
    def __init__(self, entries, **kwargs):
        super().__init__(entries, **kwargs)

    async def format_page(self, menu, entry):
        announcement, announcement_id, time, pinned, creator, creator_avatar, bot_user, bot_user_avatar = entry
        em = discord.Embed(
            title=f"{len(self.entries)} Announcements for {bot_user['name']}#{bot_user['discriminator']}",
            color=discord.Color.blurple(),
            url=f"https://blist.xyz/bot/{bot_user['id']}/announcements",
            description=f"{time.strftime('%b. %d, %Y, %I:%M %p')}\n\n{announcement}\n\n"
                        f"**Pinned?**: {pinned}\n**ID**: {announcement_id}"
        )
        em.set_thumbnail(url=str(bot_user_avatar))
        em.set_footer(text=f"Page: {menu.current_page + 1} / {self.get_max_pages()}")
        em.set_author(name =f"{creator['name']}#{creator['discriminator']}", icon_url=str(creator_avatar))
        return em


class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(aliases=['boa', 'botannounce'], invoke_without_command=True)
    async def botannouncement(self, ctx):
        if not ctx.invoked_subcommand:
            return await ctx.send_help(ctx.invoked_subcommand)

    @flags.add_flag("-pin", "--pinned", action='store_true', default=False)
    @flags.add_flag("announcement", nargs="+", type=str)
    @botannouncement.command(cls=flags.FlagCommand, name='create', aliases=['make'])
    async def botannouncement_create(self, ctx, bot: discord.Member, **arguments):
        """
        Announce something for you bot! you have to be the owner or co-owners.

        Announcements may not be greater than 2,000 characters, or less than 50.

        **Example:** `b!botannouncement create your_bot your_announcement (or file) --pinned (optional)`.

        Announcement can also be `file` to read from a .txt file.
        You can also pin the announcement using the optional `--pinned` argument, defaults to False.
        """
        if not bot.bot:
            return await ctx.send("That is not a bot!")

        owners_query = await self.bot.pool.fetchrow(
            "SELECT main_owner, owners FROM main_site_bot WHERE id = $1 AND approved = True", bot.id)
        bot_owners = [owners_query['main_owner']]
        if owners_query['owners']:
            for x in owners_query['owners'].split(" "):
                bot_owners.append(int(x))

        if ctx.author.id not in bot_owners:
            return await ctx.send(f"{ctx.author.name}, you are not the owner of {bot}!")

        announcement = ' '.join(arguments['announcement'])
        if announcement.startswith("file"):
            if not ctx.message.attachments:
                return await ctx.send(f"{ctx.author.name}, you didn't attach a .txt file...")

            text_file = await ctx.message.attachments[0].to_file()
            if not text_file.filename.endswith(".txt"):
                return await ctx.send(f"{ctx.author.name}, you didn't attach a valid .txt file...")

            read_text_file = text_file.fp.read()
            if not bool(read_text_file.decode('utf-8')):
                return await ctx.send(f"{ctx.author.name}, that .txt file is empty...")

            announcement = str(read_text_file.decode('utf-8'))

        if len(announcement) >= 2000 or len(announcement) < 50:
            return await ctx.send(
                f"{ctx.author.name}, announcements may not be greater than 2,000 characters, or less than 50."
                f" **{len(announcement)} currently**")

        announcement_query = "INSERT INTO main_site_announcement (bot_id, creator_id, announcement, time, pinned) VALUES ($1, $2, $3, $4, $4, $5)"
        await self.bot.pool.execute(announcement_query, bot.id, ctx.author.id, announcement, datetime.utcnow(), arguments['pinned'])
        bot_site = f"https://blist.xyz/bot/{bot.id}/announcements"
        await ctx.send(f"Successfully announced that for {bot}, see it here: <{bot_site}>.")
        return

    @flags.add_flag("-i", "--id", type=int, default=None)
    @flags.add_flag("-b", "--bot", type=discord.Member, default=None)
    @flags.add_flag("-old", "--oldest", action='store_true', default=False)
    @flags.add_flag("-a", "--all", action='store_true', default=False)
    @botannouncement.command(cls=flags.FlagCommand, name='view', aliases=['show'])
    async def botannouncement_view(self, ctx, **arguments):
        """
        Get announcements for a bot or a specific announcement via the unique id, this can be found on the bottom of the announcement card.

        **Example**: `b!botannouncement view --bot bot_here` or `b!botannouncement view --id id_here`

        **Arguments**:

        **--bot**/-b - Get the most recent announcement of bot.
        **--id**/-i - Get the announcement that matches the id.

        **Can only be used in combination with `--bot`**:

        **--all**/-a - Get all announcements for bot.
        **--oldest**/-old - Sort bot announcements on oldest, works with `-all`. Defaults to newest.
        """

        def get_avatar(user_id: int, av_hash: str):
            av_format = "png"
            if av_hash.startswith("a_"):
                av_format = "gif"
            return f"https://cdn.discordapp.com/avatars/{user_id}/{av_hash}.{av_format}?size=1024"

        async def _from_unique_id(table_type: str, unique_id: int):
            if table_type == "USER":
                return await self.bot.pool.fetchrow(
                    "SELECT name, discriminator, userid, avatar_hash FROM main_site_user WHERE unique_id = $1",
                    int(unique_id))

            if table_type == "BOT":
                return await self.bot.pool.fetchrow(
                    "SELECT name, id, avatar_hash, discriminator FROM main_site_bot WHERE unique_id = $1",
                    int(unique_id))

        async def fetch_announcements():
            fetched_all_announcements = None
            bot_unique_id = None
            if arguments['bot']:
                bot_unique_id = await self.bot.pool.fetchrow(
                    "SELECT unique_id FROM main_site_bot WHERE id = $1", int(arguments['bot'].id))
            # ------------------------

            if arguments['id']:
                fetched_all_announcements = await self.bot.pool.fetchrow(
                    "SELECT * FROM main_site_announcement WHERE unique_id = $1", int(arguments['id']))

            if arguments['bot']:
                query = "SELECT * FROM main_site_announcement WHERE bot_id = $1 ORDER BY time DESC"
                if arguments['oldest']:
                    query = "SELECT * FROM main_site_announcement WHERE bot_id = $1 ORDER BY time ASC"

                if arguments['all']:
                    fetched_all_announcements = await self.bot.pool.fetch(query, bot_unique_id['unique_id'])
                else:
                    fetched_all_announcements = await self.bot.pool.fetchrow(query, bot_unique_id['unique_id'])

            return fetched_all_announcements

        if not await fetch_announcements():
            return await ctx.send(
                f"{ctx.author.name}, i couldn't find any announcements.")

        all_bot_announcements = []

        for x in await fetch_announcements():
            announcement: str = x['announcement']
            announcement_id: int = x['unique_id']
            time: datetime = x['time']
            pinned: bool = x['pinned']
            creator = await _from_unique_id("USER", x['creator_id'])
            creator_avatar: str = str(get_avatar(creator['id'], creator['avatar_hash']))
            bot_user = await _from_unique_id("BOT", x['bot_id'])
            bot_user_avatar: str = str(get_avatar(bot_user['id'], bot_user['avatar_hash']))

            if len(announcement) >= 1700:
                announcement = announcement[:1700]
                more_characters = f"{2000 - 1700} [more characters](https://blist.xyz/bot/{bot_user['id']}/announcements)"
                announcement += f"... **{more_characters}...**"

            all_bot_announcements.append((announcement, announcement_id, time, pinned, creator,
                                          creator_avatar, bot_user, bot_user_avatar))

        if not all_bot_announcements:
            return await ctx.send(
                f"{ctx.author.name}, i couldn't find any announcements.")

        if len(all_bot_announcements) >= 2:
            menu = MenuMain(AnnouncementPage(entries=list(all_bot_announcements), per_page=1), clear_reactions_after=True)
            await menu.start(ctx)
            return

        announcement, announcement_id, time, pinned, creator, creator_avatar, bot_user, bot_user_avatar = all_bot_announcements[0]
        em = discord.Embed(
            title=f"Announcement for {bot_user['name']}#{bot_user['discriminator']}",
            color=discord.Color.blurple(),
            url=f"https://blist.xyz/bot/{bot_user['id']}/announcements",
            description=f"{time.strftime('%b. %d, %Y, %I:%M %p')}\n\n{announcement}\n\n"
                        f"**Pinned?**: {pinned}\n**ID**: {announcement_id}"
        )
        em.set_thumbnail(url=str(bot_user_avatar))
        em.set_author(name =f"{creator['name']}#{creator['discriminator']}", icon_url=str(creator_avatar))
        return await ctx.send(embed=em)

    @botannouncement.command(cls=flags.FlagCommand, name='delete', aliases=['remove'])
    async def botannouncement_delete(self, ctx, bot: discord.Member, announcement_id: int):
        """
        Delete an announcement from your bot page via the unique id, this can be found on the bottom of the announcement card.
        With confirmation.

        **Example:** `b!botannouncement delete your_bot announcement_id`.
        """
        if not bot.bot:
            return await ctx.send("That is not a bot!")

        owners_query = await self.bot.pool.fetchrow(
            "SELECT main_owner, owners FROM main_site_bot WHERE id = $1 AND approved = True", bot.id)
        bot_owners = [owners_query['main_owner']]
        if owners_query['owners']:
            for x in owners_query['owners'].split(" "):
                bot_owners.append(int(x))

        if ctx.author.id not in bot_owners:
            return await ctx.send(f"{ctx.author.name}, you are not the owner of {bot}!")


        bot_id = await self.bot.pool.fetchrow("SELECT unique_id FROM main_site_bot WHERE id = $1", bot.id)
        the_announcement = await self.bot.pool.fetchrow(
            "SELECT * FROM main_site_announcement WHERE unique_id = $1 AND bot_id = $2", int(announcement_id), int(bot_id))

        if not the_announcement:
            return await ctx.send(f"{ctx.author.name}, "
                                  f"i can't find any announcement that matches the announcement id and bot id.")

        msg = await ctx.send(f"**{ctx.author.name}**, do you really want delete that announcement "
                             f"with ID: {announcement_id}for {bot} ? React with ✅ or ❌ in 30 seconds.")
        await msg.add_reaction("\U00002705")
        await msg.add_reaction("\U0000274c")

        def check(r, u):
            return u.id == ctx.author.id and r.message.channel.id == ctx.channel.id and str(r.emoji) in ["\U00002705",
                                                                                                         "\U0000274c"]

        try:
            reaction, user = await self.bot.wait_for('reaction_add', check = check, timeout = 30)
        except asyncio.TimeoutError:
            await msg.remove_reaction("\U00002705", ctx.guild.me)
            await msg.remove_reaction("\U0000274c", ctx.guild.me)
            await msg.edit(content = f"~~{msg.content}~~ i guess not, cancelled.")
            return
        else:
            if str(reaction.emoji) == "\U00002705":
                await msg.remove_reaction("\U00002705", ctx.guild.me)
                await msg.remove_reaction("\U0000274c", ctx.guild.me)
                await msg.edit(content = f"~~{msg.content}~~ You reacted with ✅:")
                pass
            if str(reaction.emoji) == "\U0000274c":
                await msg.remove_reaction("\U00002705", ctx.guild.me)
                await msg.remove_reaction("\U0000274c", ctx.guild.me)
                await msg.edit(content = f"~~{msg.content}~~ okay, cancelled.")
                return


        await self.bot.pool.execute(
            "DELETE FROM main_site_announcement WHERE unique_id = $1 AND bot_id = $2", int(announcement_id), int(bot_id))
        await ctx.send(f"Successfully delete announcement with ID: {announcement_id} for {bot}.")
        return

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

    @flags.add_flag("-a", "--all", action='store_true')
    @commands.command(aliases=["lb"], cls=flags.FlagCommand)
    async def leaderboard(self, ctx, **args):
        """
        Sends the top 5 users on the user leaderboard
        **Args:**
            **--all**/-a - Flag to output everyone on the leaderboard as a menu.
        """
        leaderboard = await self.bot.pool.fetch("SELECT * FROM main_site_leveling ORDER BY level DESC, xp DESC")
        embed = discord.Embed(title="User Leaderboard", color=discord.Color.blurple(),
                              url="https://blist.xyz/leaderboard/")
        embed.set_thumbnail(url=str(ctx.guild.icon_url))
        place = 0
        for_menu = []
        leaderboard = leaderboard[:5] if not args['all'] else leaderboard
        for leader in leaderboard:
            place += 1
            user = await self.bot.pool.fetch("SELECT * FROM main_site_user WHERE unique_id = $1", leader["user_id"])
            user = user[0]

            if place == 1:
                trophy = ":first_place:"
            elif place == 2:
                trophy = ":second_place:"
            elif place == 3:
                trophy = ":third_place:"
            else:
                trophy = ":medal:"

            if args['all']:
                for_menu.append((f"{trophy} #{place} - {user['name']}#{user['discriminator']}",
                                 f"Level: {leader['level']} | XP: {leader['xp']}"))

            embed.add_field(name=f"{trophy} #{place} - {user['name']}#{user['discriminator']}",
                            value=f"Level: {leader['level']} | XP: {leader['xp']}", inline=False)

        if args['all']:
            menu = MenuMain(LeaderboardPage(entries=list(for_menu), per_page=5), clear_reactions_after=True)
            await menu.start(ctx)
            return

        return await ctx.send(embed=embed)

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
