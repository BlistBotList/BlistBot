from io import BytesIO
from textwrap import dedent as wrap
import re

from utils.pages import MainMenu, LeaderboardPage, AnnouncementPage
from utils import announcements as announce_file, rank_card

import asyncio
import discord
from discord.ext import commands, flags

class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.announcements = announce_file.Announcement

    @commands.command()
    async def rank(self, ctx, *, member: discord.Member = None):
        member = member or ctx.author
        unique_id = await announce_file._get_unique_id(ctx, "USER", member.id)
        level_user = await self.bot.pool.fetchrow("SELECT * FROM main_site_leveling WHERE user_id = $1", unique_id)
        if member.bot:
            return await ctx.send("That is a bot...")
        member_name = "You are" if member.id == ctx.author.id else f"{member.name} is"
        if not level_user:
            return await ctx.send(f"{member_name.replace('is', 'has', 1).replace('are', 'have', 1)} "
                                  f"not gained any XP, or it has not been saved yet. ")
        if level_user['blacklisted']:
            return await ctx.send(f"{member_name} blacklisted from the leveling system. aka won't receive anymore XP.")

        full_leaderboard = await self.bot.pool.fetch("SELECT * FROM main_site_leveling ORDER BY level DESC, xp DESC")
        place = full_leaderboard.index(level_user) + 1
        bug_hunter_role = self.bot.main_guild.get_role(716722789234638860)
        donator_role = self.bot.main_guild.get_role(716724716299091980)
        developer_role = self.bot.main_guild.get_role(716684805286133840)
        custom = {}
        if level_user['xp_bar_color'] != "":
            custom['xp_color'] = str(level_user['xp_bar_color'])
        if level_user['border_color'] != "":
            custom['border_color'] = str(level_user['border_color'])
        if level_user['background_color'] != "":
            background = str(level_user['background_color'])
            if background.startswith("#"):
                custom['background'] = background
            else:
                try:
                    custom['background'] = BytesIO(await (await self.bot.session.get(background)).read())
                except Exception:
                    custom['background'] = (44, 44, 44, 255)

        avatar_bytes = BytesIO(await member.avatar_url_as(format="png", size=128).read())
        dev_badge = BytesIO(await (await self.bot.session.get("https://i.adiscorduser.com/nxPRRls.png")).read())
        bug_hunter_badge = BytesIO(await (await self.bot.session.get("https://i.adiscorduser.com/9pi4RtH.png")).read())
        donator_badge = BytesIO(await (await self.bot.session.get("https://i.adiscorduser.com/wpd4mRq.png")).read())

        rank_instance = rank_card.Rank(
            bug_hunter = bool(bug_hunter_role in member.roles),
            donator = bool(donator_role in member.roles),
            developer = bool(developer_role in member.roles),
            ctx = ctx,
            member = member,
        )
        card = await rank_instance.get_card(
            xp=level_user['xp'], position=place, level=level_user['level'], avatar_bytes=avatar_bytes, custom=custom,
            badges={'developer': dev_badge, 'bug_hunter': bug_hunter_badge, 'donator': donator_badge},
        )
        img = discord.File(card, 'rank_card.png')
        await ctx.send(file=img)

    @commands.has_role(716724716299091980)
    @flags.add_flag("-bg", "--background", type=str, default=None)
    @flags.add_flag("-xp", "--xp_bar", type=str, default=None)
    @flags.add_flag("-border", "--border_colour", "--border_color", dest="border_color", type=str, default=None)
    @commands.command(name="customrank", aliases=['crank', 'customizecard'], cls=flags.FlagCommand)
    async def custom_rank(self, ctx, **arguments):
        """
        Customize your rank card using the arguments!

        **Arguments**:

        **--background**/-bg | Provide a HEX value or image URL to be set as your card background.
        **--xp_bar**/-xp | Provide a HEX value to be set as your xp bar's color.
        **--border_color**/-border | Provide a HEX value to be set as your xp border color.
        You can also pass `"remove"` as value to reset them to default. Example: `b!crank -bg "remove"`

        **Example**: `b!crank --background "https://i.adiscorduser.com/4ZZdxmR.png" (or "#ffffff") -xp "#666666" --border_color "#123456"`
        """
        if not arguments['border_color'] and not arguments['background'] and not arguments['xp_bar']:
            await ctx.send_help(ctx.command)
            return
        unique_id = await announce_file._get_unique_id(ctx, "USER", ctx.author.id)
        level_user = await self.bot.pool.fetchrow("SELECT * FROM main_site_leveling WHERE user_id = $1", unique_id)
        if not level_user or level_user['blacklisted'] or ctx.author.bot:
            return await ctx.send(f"{ctx.author.name} you haven't received any XP yet or are blacklisted from doing so.")

        success_text = []
        failed_text = []
        if arguments['background']:
            background = arguments['background']
            removing = False
            if background.lower() == "remove":
                removing = True
                set_background = await rank_card.Rank(ctx, ctx.author).customize_rank_card("BACKGROUND")
            else:
                if not "https://" or "http://" in background:
                    if not re.search("^#(?:[0-9a-fA-F]{3}){1,2}$", str(background)):
                        return await ctx.send(f"(background) {ctx.author.name}, "
                                              f"that does not look like a valid image URL or HEX value (#123456)")
                set_background = await rank_card.Rank(ctx, ctx.author).customize_rank_card("BACKGROUND", str(background))
            if set_background[0] is True:
                if removing:
                    success_text.append(f"- Removed your custom background")
                else:
                    bg = set_background[1]
                    bg = f"<{bg}>" if bg.startswith("https://") or bg.startswith("http://") else bg
                    success_text.append(f"- Set your Background to: {bg}")
            else:
                failed_text.append(f"Something went wrong while {'saving' if not removing else 'removing'} "
                                   f"your background: {set_background[1]}")

        if arguments['xp_bar']:
            xp_bar = arguments['xp_bar']
            removing = False
            if xp_bar.lower() == "remove":
                removing = True
                set_xp_colour = await rank_card.Rank(ctx, ctx.author).customize_rank_card("XP_BAR_COLOUR")
            else:
                if not re.search("^#(?:[0-9a-fA-F]{3}){1,2}$", str(xp_bar)):
                    return await ctx.send(f"(xp_bar) {ctx.author.name}, that does not look like a valid HEX value (#123456)")
                set_xp_colour = await rank_card.Rank(ctx, ctx.author).customize_rank_card("XP_BAR_COLOUR", str(xp_bar))
            if set_xp_colour[0] is True:
                if removing:
                    success_text.append(f"- Removed your custom XP color")
                else:
                    success_text.append(f"- Set your XP bar colour to: {set_xp_colour[1]}")
            else:
                failed_text.append(f"Something went wrong while {'saving' if not removing else 'removing'} "
                                   f"your XP bar color: {set_xp_colour[1]}")

        if arguments['border_color']:
            border_color = arguments['border_color']
            removing = False
            if border_color.lower() == "remove":
                removing = True
                set_border_colour = await rank_card.Rank(ctx, ctx.author).customize_rank_card("BORDER_COLOUR")
            else:
                if not re.search("^#(?:[0-9a-fA-F]{3}){1,2}$", str(border_color)):
                    return await ctx.send(f"(border_color) {ctx.author.name}, that does not look like a valid HEX value (#123456)")
                set_border_colour = await rank_card.Rank(ctx, ctx.author).customize_rank_card("BORDER_COLOUR", str(border_color))
            if set_border_colour[0] is True:
                if removing:
                    success_text.append(f"- Removed your custom border color")
                else:
                    success_text.append(f"- Set your border color to: {set_border_colour[1]}")
            else:
                failed_text.append(f"Something went wrong while {'saving' if not removing else 'removing'} "
                                   f"your border color: {set_border_colour[1]}")

        if failed_text:
            join_errors = "\n".join(failed_text)
            await ctx.send(f"**{ctx.author.name}**, I got the following errors:\n{join_errors}")
            return

        join_success = "\n".join(success_text)
        await ctx.send(f"**{ctx.author.name}**, Successfully done the following:\n{join_success}")
        return

    @commands.group(aliases=['boa', 'botannounce'], invoke_without_command=True)
    async def botannouncement(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(str(ctx.command))

    @flags.add_flag("-pin", "--pinned", action='store_true', default=False)
    @flags.add_flag("announcement", nargs="+", type=str)
    @botannouncement.command(cls=flags.FlagCommand, name='create', aliases=['make'], brief="See [p]help botannouncement create")
    async def botannouncement_create(self, ctx, bot: discord.Member, **arguments):
        """
        Announce something for your bot! you have to be the owner or co-owners.

        Announcements may not be greater than 2,000 characters, or less than 50.

        **Example:** `b!botannouncement create your_bot your_announcement (or file) --pinned (optional)`.

        Announcement can also be `file` to read from a .txt file.
        You can also pin the announcement using the optional `--pinned` argument, defaults to False.
        """
        check_listed = await announce_file.is_bot_on_site(ctx, bot.id)
        if not check_listed or not bot.bot:
            return await ctx.send("That is not a bot or it's not listed on the site!")

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

        inserted = await self.announcements.insert(
            ctx, announcement, bot.id, arguments['pinned'])

        if isinstance(inserted, str):
            return await ctx.send(f"{ctx.author.name}, something went wrong... {inserted}")

        # Sending the announcement in chat because we can...
        announcement_object: announce_file.Announcement = inserted
        announcement_content: str = inserted.content
        creator: announce_file.Author = await inserted.get_author_object(ctx)
        bot: announce_file.Bot = await inserted.get_bot_object(ctx)

        if len(announcement_content) >= 1700:
            announcement = announcement[:1700]
            more_characters = f"{2000 - 1700} [more characters](https://blist.xyz/bot/{bot.id}/announcements)"
            announcement += f"... **{more_characters}...**"

        menu = MainMenu(AnnouncementPage(entries=list([(announcement_object, announcement_content, creator, bot)]),
                                         per_page=1), clear_reactions_after=True)
        bot_site = f"https://blist.xyz/bot/{bot.id}/announcements"
        await ctx.send(f"Successfully announced that for {bot}, see it here: <{bot_site}>")
        await menu.start(ctx)
        return

    @flags.add_flag("-i", "--id", type=int, default=None)
    @flags.add_flag("-b", "--bot", type=discord.Member, default=None)
    @flags.add_flag("-old", "--oldest", action='store_true', default=False)
    @flags.add_flag("-a", "--all", action='store_true', default=False)
    @botannouncement.command(cls=flags.FlagCommand, name='view', aliases=['show'], brief="See [p]help botannouncement view")
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
        if arguments['bot']:
            bot_arg = arguments['bot']
            check_listed = await announce_file.is_bot_on_site(ctx, bot_arg.id)
            if not check_listed or not bot_arg.bot:
                return await ctx.send("That is not a bot or it's not listed on the site!")
            limit = 1 if not arguments['all'] else None
            fetched_announcements = await self.announcements.fetch_bot_announcements(
                ctx, bot_id=bot_arg.id, limit=limit, oldest=arguments['oldest'])
        elif arguments['id']:
            fetched_announcements = await self.announcements.from_unique_id(ctx, arguments['id'])
            if fetched_announcements:
                fetched_announcements = [fetched_announcements]
        else:
            return await ctx.send(f"{ctx.author.name}, please provide either `--bot` or `--id` not nothing. See {ctx.prefix}help {ctx.command.qualified_name}")

        if isinstance(fetched_announcements, str):
            return await ctx.send(
                f"{ctx.author.name}, i couldn't find any announcements.\n{fetched_announcements}")

        if not fetched_announcements:
            return await ctx.send(
                f"{ctx.author.name}, i couldn't find any announcements.")

        all_bot_announcements = []

        for x in fetched_announcements:
            announcement: announce_file.Announcement = x
            announcement_content: str = x.content
            creator: announce_file.Author = await x.get_author_object(ctx)
            bot: announce_file.Bot = await x.get_bot_object(ctx)

            if len(announcement_content) >= 1700:
                announcement = announcement[:1700]
                more_characters = f"{2000 - 1700} [more characters](https://blist.xyz/bot/{bot.id}/announcements)"
                announcement += f"... **{more_characters}...**"

            all_bot_announcements.append((announcement, announcement_content, creator, bot))

        menu = MainMenu(AnnouncementPage(entries=list(all_bot_announcements), per_page=1), clear_reactions_after=True)
        await menu.start(ctx)
        return

    @botannouncement.command(cls=flags.FlagCommand, name='delete', aliases=['remove'], brief="See [p]help botannouncement delete")
    async def botannouncement_delete(self, ctx, bot: discord.Member, announcement_id: int):
        """
        Delete an announcement from your bot page via the unique id, this can be found on the bottom of the announcement card.
        With confirmation.

        **Example:** `b!botannouncement delete your_bot announcement_id`.
        """
        check_listed = await announce_file.is_bot_on_site(ctx, bot.id)
        if not check_listed or not bot.bot:
            return await ctx.send("That is not a bot or it's not listed on the site!")

        owners_query = await self.bot.pool.fetchrow(
            "SELECT main_owner, owners FROM main_site_bot WHERE id = $1 AND approved = True", bot.id)
        bot_owners = [owners_query['main_owner']]
        if owners_query['owners']:
            for x in owners_query['owners'].split(" "):
                bot_owners.append(int(x))

        if ctx.author.id not in bot_owners:
            return await ctx.send(f"{ctx.author.name}, you are not the owner of {bot}!")

        the_announcement = await self.announcements.from_unique_id(ctx, announcement_id)
        if not the_announcement:
            return await ctx.send(f"{ctx.author.name}, i couldn't find any announcement matching the announcement id.")
        else:
            pass

        msg = await ctx.send(f"**{ctx.author.name}**, do you really want delete that announcement "
                             f"with ID: {announcement_id} for {bot} ? React with ✅ or ❌ in 30 seconds.")
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

        delete_announcement = await the_announcement.delete(ctx, bot.id)
        if not delete_announcement:
            return await ctx.send(f"{ctx.author.name}, that announcement id didn't match that bot.")
        await ctx.send(f"Successfully deleted announcement with ID: {announcement_id} for {bot}.")

        if isinstance(delete_announcement, self.announcements):
            announcement_object: announce_file.Announcement = delete_announcement
            announcement_content: str = announcement_object.content
            creator: announce_file.Author = await announcement_object.get_author_object(ctx)
            _bot: announce_file.Bot = await announcement_object.get_bot_object(ctx)
            menu = MainMenu(
                AnnouncementPage(
                    entries=list([(announcement_object, announcement_content, creator, _bot)]), per_page=1),
                clear_reactions_after=True)
            await menu.start(ctx)
            return
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
            menu = MainMenu(LeaderboardPage(entries=list(for_menu), per_page=5), clear_reactions_after=True)
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
    async def userinfo(self, ctx, *, member: discord.Member=None):
        """Shows information on a user"""
        member = member or ctx.author
        em = discord.Embed(
            title=f"{member.name} - #{member.discriminator}",
            url=f"https://blist.xyz/user/{member.id}/",
            color=discord.Colour.blurple(),
            description=wrap(
                f"""
                >>> `ID:` {member.id}
                `Bot:` {member.bot}
                `Status:` {str(member.status).title()}
                `Highest Role:` {member.top_role.mention}
                `Created Account:` {member.created_at.strftime("%c")}
                `Joined This Server:` {member.joined_at.strftime("%c")}
                """
            )
        )
        unique_id = await announce_file._get_unique_id(ctx, "USER", member.id)
        level_user = await self.bot.pool.fetchrow("SELECT * FROM main_site_leveling WHERE user_id = $1", unique_id)
        if level_user:
            full_leaderboard = await self.bot.pool.fetch("SELECT * FROM main_site_leveling ORDER BY level DESC, xp DESC")
            place = full_leaderboard.index(level_user) + 1
            em.add_field(name="Leveling:",
                         value=wrap(
                             f""">>> `Place:` {place}
                             `Level:` {level_user['level']:,d}
                             `XP:` {level_user['xp']:,d}
                             `Blacklisted:` {'Yes' if level_user['blacklisted'] else 'No'}
                             """)
                         )
        em.set_thumbnail(url=member.avatar_url)
        await ctx.send(embed=em)


def setup(bot):
    bot.add_cog(General(bot))
