import datetime
from textwrap import dedent as wrap
from typing import Union, Tuple, Dict

import discord
import googletrans
import asyncio
import typing
from discord.ext import commands, flags
from utils import checks
from utils.time import time_took


def bot_log_embed(ctx, bot_and_owner: Tuple[Union[discord.Member, int], Union[discord.Member, int]], *,
                  reason: str=None):
    def escape_markdown(txt: str):
        return discord.utils.escape_markdown(str(txt))
    bot, bot_owner=bot_and_owner
    bot_text=f"{escape_markdown(str(bot))} ({bot.id})" \
        if isinstance(bot, discord.Member) else escape_markdown(str(bot))
    bot_owner_text=f"{escape_markdown(str(bot_owner))} ({bot_owner.id})" \
        if isinstance(bot_owner, discord.Member) else escape_markdown(str(bot_owner))

    command_author=f"{escape_markdown(ctx.author)} | ({ctx.author.id})"
    embed_stuff_dict={
        "deny": ("Bot denied", discord.Color.red(), f"**Bot:** {bot_text}\n**Owner:** {bot_owner_text}",
                 f"**Reviewer:** {command_author}", str(reason)),
        "delete": ("Bot deleted", discord.Color.red(), f"**Bot:** {bot_text}\n**Owner:** {bot_owner_text}",
                   f"**Author:** {command_author}", str(reason)),
        "approve": ("Bot approved", discord.Color.green(), f"**Bot:** {bot_text}\n**Owner:** {bot_owner_text}",
                    f"**Reviewer:** {command_author}", None)
    }
    title, color, description, command_invoker, reason=embed_stuff_dict.get(str(ctx.command.name))
    reason=f"**Reason:** {reason}" if reason is not None else ''
    emb=discord.Embed(
        title=title,
        description=f"{description}\n\n{command_invoker}\n{reason}",
        colour=color
    )
    return emb


class Staff(commands.Cog):
    def __init__(self, bot):
        self.bot=bot
        self.translator=googletrans.Translator()

    @commands.has_permissions(kick_members=True)
    @commands.group(invoke_without_command=True, aliases=["q"])
    async def queue(self, ctx):
        bots=await self.bot.pool.fetch("SELECT * FROM main_site_bot WHERE approved=False AND denied=False")
        if not bots:
            await ctx.send("There are no bots in the queue")
            return

        test_categories=(self.bot.get_cog("Events")).test_categories
        listed_bots=[]
        for x in bots:
            if x['id'] in test_categories.keys():
                testing_category=self.bot.verification_guild.get_channel(test_categories[x['id']])
                if not testing_category:
                    pass
                testing_channel=discord.utils.get(testing_category.text_channels, name="testing")
                category_created_at=testing_category.created_at.replace(tzinfo=datetime.timezone.utc)
                too_long=time_took(dt=category_created_at, only_hours=True,
                                     now_dt=datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc))
                if int(too_long) >= 6:
                    too_long=f"- {int(too_long)}+ hours in testing ⚠️"
                else:
                    too_long=""

                being_tested=f"(being tested in {testing_category.name} | {testing_channel.mention})"
                listed_bots.append(f"~~{x['username']}~~ {being_tested} {too_long}")
            else:
                too_long=time_took(dt=x['added'], only_hours=True,
                                     now_dt=datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc))
                if int(too_long) >= 2:
                    too_long=f"- {int(too_long)}+ hours in queue ⚠️"
                else:
                    too_long=""
                invite=str(
                    discord.utils.oauth_url(x['id'],
                                            guild=self.bot.verification_guild)) + "&disable_guild_select=true"
                listed_bots.append(f"{x['username']} [Invite]({invite}) {too_long}")

        embed=discord.Embed(
            title="Queue",
            url="https://blist.xyz/staff#verification",
            description='\n'.join(listed_bots) if listed_bots else "All Clear",
            color=discord.Color.blurple()
        )
        await ctx.send(embed=embed)

    @checks.main_guild_only()
    @queue.command(aliases=["c"])
    async def certification(self, ctx):
        bots=await self.bot.pool.fetch("SELECT * FROM main_site_bot WHERE awaiting_certification=True")
        if bots is None:
            await ctx.send("There are no bots in the certification queue")
            return

        listed_bots=[]
        for x in bots:
            listed_bots.append(f"{x['username']} | Added: {x['added']}")

        embed=discord.Embed(
            title="Certification Queue",
            description='\n'.join(listed_bots) if listed_bots else "All Clear",
            color=discord.Color.blurple()
        )
        await ctx.send(embed=embed)

    @checks.verification_guild_only()
    @commands.has_permissions(kick_members=True)
    @commands.command(aliases=['accept'])
    async def approve(self, ctx, *, bot: discord.Member):
        if not bot.bot:
            await ctx.send("This is not a bot.")
            return

        bots=await self.bot.pool.fetchrow(
            "SELECT main_owner, referred_by FROM main_site_bot WHERE approved=False AND denied=False AND id=$1",
            bot.id)
        if not bots:
            await ctx.send("This bot is not awaiting approval")
            return

        owner=self.bot.main_guild.get_member(bots["main_owner"])
        if not owner:
            await ctx.send(f"{ctx.author.mention}, The owner of this bot has left the main server, deny it!")
            return

        if bots["referred_by"] != "":
            user_id=await self.bot.pool.fetchval("SELECT id FROM main_site_user WHERE referrer_code =$1",
                                                   bots["referred_by"])
            if user_id:
                await self.bot.pool.execute("UPDATE main_site_user SET referrals=referrals + 1 WHERE id=$1",
                                            user_id)

        await self.bot.pool.execute("UPDATE main_site_user SET developer=True WHERE id=$1", bots["main_owner"])
        await self.bot.pool.execute("UPDATE main_site_bot SET approved=True WHERE id=$1", bot.id)
        await self.bot.mod_pool.execute("UPDATE staff SET approved=approved + 1 WHERE userid=$1", ctx.author.id)

        queued_bots=await self.bot.pool.fetchval(
            "SELECT COUNT(*) FROM main_site_bot WHERE approved=False AND denied=False")
        invite=str(discord.utils.oauth_url(
            bot.id, guild=self.bot.main_guild)) + "&disable_guild_select=true"
        embed=discord.Embed(
            title=f"Approved {bot.name}",
            description=f"[Invite!]({invite})\n\nThere are {queued_bots} bot(s) in the queue.",
            color=discord.Color.blurple()
        )
        await self.bot.verification_guild.get_channel(763183376311517215).send(
            content=ctx.author.mention, embed=embed)

        em=bot_log_embed(ctx, (bot, owner))
        await self.bot.get_channel(716446098859884625).send(embed=em)

        dev_role=self.bot.main_guild.get_role(716684805286133840)

        try:
            await owner.send(f"Your bot `{bot}` was approved!")
        except (discord.Forbidden, AttributeError):
            pass

        try:
            await owner.add_roles(dev_role)
        except AttributeError:
            pass

        await bot.kick()
        bots=await self.bot.pool.fetchval("SELECT COUNT(*) FROM main_site_bot")
        await self.bot.change_presence(activity=discord.Game(name=f"Watching {bots} bots"))

    @commands.has_permissions(kick_members=True)
    @commands.command()
    async def deny(self, ctx, bot: Union[discord.Member, discord.User]):
        if not bot.bot:
            await ctx.send("This user is not a bot")
            return

        bots=await self.bot.pool.fetchval(
            "SELECT main_owner FROM main_site_bot WHERE approved=False AND denied=False AND id=$1", bot.id)
        if not bots:
            await ctx.send("This bot is not awaiting approval")
            return

        def wait_for_check(m):
            return m.channel.id == ctx.channel.id and m.author.id == ctx.author.id

        preset_reasons=[
            "Bot was offline when we tried to test it.",
            "The bot's description is poor quality. The description must be improved before resubmission.",
            "The avatar of the bot is considered NSFW.",
            "NSFW commands that the bot has work in non-NSFW channels.",
            "The bot is an unmodified clone of another bot.",
            "The bot's page contains scripts which causes issues with the integrity of the page.",
            "The bot violates Discord ToS.",
            "The bot does not have 5 or more commands, excluding any type of help command.",
            "Bot sends level up messages which cannot be toggled by a staff member.",
            "Bot responds to other bots.",
            "The bot violates a rule listed in the main server rules.",
            "The bot responds to commands without a prefix being used.",
            "The bot's description is full of spam and junk to achieve the required character minimum.",
            "Bot owner left the main server whilst we were testing the bot.",
            "The bot does not have proper or complete error handling.",
            "The bot owner did not respond or complete fixes within the time frame given."
        ]

        join_preset_reasons="\n".join([f"**{num}.** {rule}" for num, rule in enumerate(preset_reasons, start=1)])
        embed=discord.Embed(
            title=f"Denying {bot.name}",
            description=join_preset_reasons,
            color=discord.Color.red()
        )
        embed.set_footer(text="You have 20 seconds to provide a valid reason number or type your own reason.")
        await ctx.send(embed=embed)

        try:
            msg=await self.bot.wait_for("message", timeout=20.0, check=wait_for_check)
        except asyncio.TimeoutError:
            return await ctx.send(
                "You did not provide a reason number or custom reason in time. The command was cancelled.")
        else:
            if msg.content.isdigit():
                try:
                    reason=preset_reasons[int(msg.content) - 1]
                except KeyError:
                    return await ctx.send(f"{msg.content} is not valid reason number. The command was cancelled.")
            else:
                reason=msg.content  # custom reason

        await self.bot.mod_pool.execute("UPDATE staff SET denied=denied + 1 WHERE userid=$1", ctx.author.id)

        try:
            owner=self.bot.main_guild.get_member(bots)
            await owner.send(f"Your bot `{bot}` was denied!")
        except (discord.Forbidden, AttributeError):
            pass

        await self.bot.pool.execute("UPDATE main_site_bot SET denied=True WHERE id=$1", bot.id)
        embed=discord.Embed(
            description=f"Denied {bot.name}", color=discord.Color.red())
        await ctx.send(embed=embed)

        bot_owner=self.bot.main_guild.get_member(bots)
        bot_owner=bot_owner if bot_owner else int(bots)
        em=bot_log_embed(ctx, (bot, bot_owner), reason=str(reason))
        await self.bot.get_channel(716446098859884625).send(embed=em)

        try:
            await bot.kick(reason="Bot Denied")
        except Exception:
            await ctx.send("Couldn't kick bot")

    @checks.main_guild_only()
    @commands.has_permissions(kick_members=True)
    @commands.command()
    async def delete(self, ctx, bot: Union[discord.Member, int]):
        if isinstance(bot, discord.Member):
            bot_id = bot.id
            if not bot.bot:
                return await ctx.send("That is not a bot.")
        elif isinstance(bot, int):
            bot_id = int(bot)
        else:
            return await ctx.send("invalid argument.")

        bot_from_db=await self.bot.pool.fetchrow(
            "SELECT main_owner, username, id, certified, discriminator, unique_id FROM main_site_bot "
            "WHERE approved=True AND id=$1", bot_id)

        if not bot_from_db:
            await ctx.send("This bot is not on the list")
            return

        # Preset reason --------------------

        def wait_for_check(m):
            return m.channel.id == ctx.channel.id and m.author.id == ctx.author.id

        preset_reasons=[
            "Bot left the main server",
            "Owner left the main server",
            "Owner was banned from the main server",
            "The bot had issues that were not fixed within the timeframe given",
            "Mass DM advertised",
            "Bot DM advertised",
            "Bot was editied and now violates our rules",
            "Bot sent unwanted spam",
        ]

        join_preset_reasons="\n".join([f"**{num}.** {rule}" for num,rule in enumerate(preset_reasons, start=1)])
        embed=discord.Embed(
            title=f"Deleting {bot_from_db['username']}",
            description=join_preset_reasons,
            color=discord.Color.red()
        )
        embed.set_footer(text="You have 20 seconds to provide a valid reason number or type your own reason.")
        await ctx.send(embed=embed)

        try:
            message=await self.bot.wait_for("message", timeout=20.0, check=wait_for_check)
        except asyncio.TimeoutError:
            return await ctx.send(
                "You did not provide a reason number or custom reason in time. The command was cancelled.")
        else:
            if message.content.isdigit():
                try:
                    reason=preset_reasons[int(message.content) - 1]
                except KeyError:
                    return await ctx.send(f"{message.content} is not valid reason number. The command was cancelled.")
            else:
                reason=message.content  # custom reason
        # --------------------
        await self.bot.pool.execute("DELETE FROM main_site_vote WHERE bot_id=$1", bot_from_db['unique_id'])
        await self.bot.pool.execute("DELETE FROM main_site_review WHERE bot_id=$1", bot_from_db['unique_id'])
        await self.bot.pool.execute("DELETE FROM main_site_auditlogaction WHERE bot_id=$1", bot_from_db['unique_id'])
        await self.bot.pool.execute("DELETE FROM main_site_announcement WHERE bot_id=$1", bot_from_db['unique_id'])
        await self.bot.pool.execute("DELETE FROM main_site_bot WHERE id=$1", bot_id)

        await ctx.send(embed=discord.Embed(
            description=f"Deleted {bot_from_db['username']}", color=discord.Color.red()))

        bot_owner=self.bot.main_guild.get_member(bot_from_db['main_owner'])
        bot_owner=bot_owner if bot_owner else int(bot_from_db['main_owner'])
        # -----------------------
        bot_member=self.bot.main_guild.get_member(bot_from_db['id'])
        bot_member=bot_member if bot_member else \
            f"{bot_from_db['username']}#{bot_from_db['discriminator']} ({bot_from_db['id']})"
        # -----------------------
        em=bot_log_embed(ctx, (bot_member, bot_owner), reason=str(reason))
        await self.bot.get_channel(716446098859884625).send(embed=em)

        has_other_bots = await self.bot.pool.fetch(
            "SELECT * FROM main_site_bot WHERE main_owner=$1", bot_from_db['main_owner'])

        if isinstance(bot_owner, discord.Member):
            if bot_from_db['certified'] is True:
                certified_dev_role=ctx.guild.get_role(716724317207003206)
                await bot_owner.remove_roles(certified_dev_role)
            if not has_other_bots:
                dev_role = ctx.guild.get_role(716684805286133840)
                await bot_owner.remove_roles(dev_role)

        if not has_other_bots:
            await self.bot.pool.execute(
                "UPDATE main_site_user SET developer=False WHERE id=$1", bot_from_db['main_owner'])

        if isinstance(bot_member, discord.Member):
            await bot_member.kick(reason="Bot Deleted")

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
        message=' '.join(arguments['message'])
        try:
            translated=self.translator.translate(
                message, dest=arguments['to'], src=arguments['from'])
        except ValueError:
            return await ctx.send(
                embed=discord.Embed(description="That is not a valid language!", color=discord.Color.red()))

        src=googletrans.LANGUAGES.get(
            translated.src, '(auto-detected)').title()
        dest=googletrans.LANGUAGES.get(translated.dest, 'Unknown').title()
        embed=discord.Embed(color=discord.Color.blurple())
        embed.add_field(name=f"{src} ({translated.src})",
                        value=translated.origin, inline=False)
        embed.add_field(name=f"{dest} ({translated.dest})",
                        value=translated.text, inline=False)
        await ctx.send(embed=embed)

    @commands.command()
    async def staff(self, ctx, member: discord.Member=None):
        if not member:
            member=ctx.author

        query=await self.bot.mod_pool.fetch("SELECT * FROM staff WHERE userid=$1", member.id)
        if not query:
            return await ctx.send("This user is not staff!")
        query=query[0]
        embed=discord.Embed(
            color=discord.Color.blurple(),
            description=wrap(
                f"""
                >>> Staff Since: ``{query['joinedat'].strftime("%F")}``
                Bots Approved: ``{query['approved']}``
                Bots Denied: ``{query['denied']}``
                Country: ``{query['country_code'] or 'Not Specified'}``
                Rank: ``{query['rank'] or 'Not Specified'}``
                Strikes: ``{query['strikes']}`` {'⚠' if query['strikes'] >= 5 else ""}
                """
            )
        )
        embed.set_author(name=member, icon_url=str(member.avatar_url))
        await ctx.send(embed=embed)

    @commands.has_permissions(kick_members=True)
    @checks.verification_guild_only()
    @commands.command(aliases=['lock'])
    async def hold(self, ctx, message: typing.Optional[discord.Message]=None, *, reason: str):
        """ Waiting on a bot owner to fix their bot? Use this!
        You can also include the message url of the message to the owner like so, `b!hold URLHERE reason here`
        Or use the command with only a reason, `b!hold reason here`
        """
        em=discord.Embed(
            title=str(reason),
            colour=discord.Color.blurple(),
            timestamp=ctx.message.created_at
        )
        em.set_author(name=ctx.author.name, icon_url=ctx.author.avatar_url)
        em.set_footer(text = "don't forget to use b!unlock, only you can send messages now.")
        if message:
            em.description=f"[message link]({message.jump_url})"

        staff_role=ctx.channel.category.overwrites_for(ctx.guild.get_role(763177553636098082))
        staff_role.send_messages=False
        everyone=ctx.channel.category.overwrites_for(ctx.guild.default_role)
        everyone.send_messages=False
        await ctx.channel.category.set_permissions(ctx.guild.get_role(763177553636098082), overwrite=staff_role,
                                                   reason=f"hold review for {reason}")
        await ctx.channel.category.set_permissions(ctx.guild.default_role, overwrite=everyone,
                                                   reason=f"hold review for {reason}")
        await ctx.channel.category.set_permissions(ctx.author, reason=f"hold review for {reason}",
                                                   send_messages=True)

        msg=await ctx.send(embed=em)
        await ctx.message.delete()
        await msg.pin()

    @commands.has_permissions(kick_members=True)
    @checks.verification_guild_only()
    @commands.command(aliases=['unlock'])
    async def unhold(self, ctx):
        """Unhold the channel to start reviewing a bot again."""
        em=discord.Embed(
            title="Unlocked the channel, you can continue.",
            colour=discord.Color.blurple()
        )
        em.set_author(name=ctx.author.name, icon_url=ctx.author.avatar_url)

        staff_role=ctx.channel.category.overwrites_for(ctx.guild.get_role(763177553636098082))
        staff_role.send_messages=None
        everyone=ctx.channel.category.overwrites_for(ctx.guild.default_role)
        everyone.send_messages=None
        await ctx.channel.category.set_permissions(ctx.guild.get_role(763177553636098082), overwrite=staff_role,
                                                   reason="unlocked")
        await ctx.channel.category.set_permissions(ctx.guild.default_role, overwrite=everyone, reason="unlocked")
        await ctx.channel.category.set_permissions(ctx.author, overwrite=None, reason="unlocked")

        await ctx.send(embed=em)
        await ctx.message.delete()
        channel_pins_hold_embeds=[x for x in await ctx.channel.pins() if x.embeds and x.embeds[0].author]
        if not channel_pins_hold_embeds:
            return

        try:
            await channel_pins_hold_embeds[0].unpin()
        except:
            return


def setup(bot):
    bot.add_cog(Staff(bot))
