from __future__ import annotations

import datetime
import json
import os
import random
import re
import sys
import io
from textwrap import dedent as wrap
from typing import TYPE_CHECKING, Any, Dict, Optional, Union

import discord
import pytz
from discord.ext import commands, tasks

import config
from utils.checks import WrongGuild
from utils.time import time_took

utc = pytz.UTC

if TYPE_CHECKING:
    from bot import Blist


class Events(commands.Cog):
    def __init__(self, bot: Blist):
        self.bot: Blist = bot
        # bot_id: category_id
        self.test_categories: Dict[int, int] = {}

    async def update_staff_embed(self, guild: discord.Guild):
        web_mods_query = await self.bot.mod_pool.fetch(
            "SELECT userid, country_code FROM staff WHERE rank = $1",
            "Website Moderator",
        )
        senior_web_mod_query = await self.bot.mod_pool.fetch(
            "SELECT userid, country_code FROM staff WHERE rank = $1",
            "Senior Website Moderator",
        )
        admins_query = await self.bot.mod_pool.fetch(
            "SELECT userid, country_code FROM staff WHERE rank = $1", "Administrator"
        )
        senior_admins_query = await self.bot.mod_pool.fetch(
            "SELECT userid, country_code FROM staff WHERE rank = $1",
            "Senior Administrator",
        )
        senior_administrators = [
            f"{guild.get_member(user['userid']).mention} :flag_{str(user['country_code']).lower()}:"
            for user in senior_admins_query
        ]
        administrators = [
            f"{guild.get_member(user['userid']).mention} :flag_{str(user['country_code']).lower()}:"
            for user in admins_query
        ]
        senior_website_moderators = [
            f"{guild.get_member(user['userid']).mention} :flag_{str(user['country_code']).lower()}:"
            for user in senior_web_mod_query
        ]
        website_moderators = [
            f"{guild.get_member(user['userid']).mention} :flag_{str(user['country_code']).lower()}:"
            for user in web_mods_query
        ]

        embed = discord.Embed(color=discord.Color.blurple(), title="Staff")
        embed.add_field(
            name="> Senior Administrators",
            value="\n".join(senior_administrators) or "None",
            inline=False,
        )
        embed.add_field(
            name="> Administrators",
            value="\n".join(administrators) or "None",
            inline=False,
        )
        embed.add_field(
            name="> Senior Website Moderators",
            value="\n".join(senior_website_moderators) or "None",
            inline=False,
        )
        embed.add_field(
            name="> Website Moderators",
            value="\n".join(website_moderators) or "None",
            inline=False,
        )
        channel = guild.get_channel(716823743644696586)
        message = channel.get_partial_message(723641541486182410)
        await message.edit(embed=embed)

    @property
    def error_webhook(self):
        token = config.error_webhook_token
        web_id = config.error_webhook_id
        hook = discord.Webhook.partial(
            id=web_id,
            token=token,
            client=self.bot,
        )
        return hook

    async def new_on_error(self, event, *args, **kwargs):
        error = sys.exc_info()
        if not error[1]:
            return
        em = discord.Embed(
            title="Bot Error:",
            description=f"**Event**: {event}\n```py\n{error[1]}\n\n{error}```",
            color=discord.Color.blurple(),
        )
        await self.error_webhook.send(embed=em)

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        ignored = (
            commands.CommandNotFound,
            commands.DisabledCommand,
            commands.TooManyArguments,
        )
        send_embed = (
            commands.MissingPermissions,
            discord.HTTPException,
            commands.NotOwner,
            commands.CheckFailure,
            commands.MissingRequiredArgument,
            commands.BadArgument,
            commands.BadUnionArgument,
            commands.BadFlagArgument,
            commands.TooManyFlags,
            commands.MissingRequiredFlag,
            WrongGuild,
        )

        errors = {
            commands.MissingPermissions: "You do not have permissions to run this command.",
            discord.HTTPException: "There was an error connecting to Discord. Please try again.",
            commands.CommandInvokeError: "There was an issue running the command.",
            commands.NotOwner: "You are not the owner.",
            commands.CheckFailure: "This command cannot be used in this guild!",
            commands.MissingRole: "You're missing the **{}** role",
            commands.MissingRequiredArgument: "`{}` is a required argument!",
        }

        if isinstance(error, ignored):
            return

        if isinstance(error, send_embed):
            if isinstance(error, commands.MissingRequiredArgument):
                err = errors.get(error.__class__).format(str(error.param).partition(":")[0])
            elif isinstance(error, commands.MissingRole):
                role = ctx.guild.get_role(error.missing_role)
                err = errors.get(error.__class__).format(role.mention)
            else:
                efd = errors.get(error.__class__)
                err = str(efd)
                if not efd:
                    err = str(error)

            em = discord.Embed(description=str(err), color=discord.Color.red())
            try:
                await ctx.send(embed=em)
                return
            except discord.Forbidden:
                pass

        # when error is not handled above
        em = discord.Embed(
            title="Bot Error:",
            description=f"```py\n{error}\n```",
            color=discord.Color.blurple(),
        )
        await ctx.send(
            embed=discord.Embed(
                description=f"Something went wrong... {type(error).__name__}",
                color=discord.Color.red(),
            )
        )
        await self.error_webhook.send(embed=em)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.guild is None:
            if message.author == self.bot.user:
                return
            channel = self.bot.main_guild.get_channel(716727091818790952)
            embed = discord.Embed(
                color=discord.Color.blurple(),
                description=f"""
New Message

>>> **Author:** `{message.author} ({message.author.id})`
**Message:** ```{message.content}```
""",
            )
            await channel.send(embed=embed)
        if message.channel.id == 743127622053003364:
            if message.attachments or re.findall(
                r"<(?P<animated>a?):(?P<name>[a-zA-Z0-9_]{2,32}):(?P<id>[0-9]{18,22})>",
                message.content,
            ):
                await message.add_reaction("✔")
                await message.add_reaction("❌")

        if message.guild == self.bot.main_guild:
            ignored_cats = [716445624517656729]
            ignored_chans = [716717997510885477, 793522769999953970]
            if message.channel.category.id in ignored_cats:
                return
            if message.channel.id in ignored_chans:
                return
            user = await self.bot.pool.fetch("SELECT * FROM main_site_user WHERE id = $1", message.author.id)
            if user:
                user = user[0]
                leveling_user = await self.bot.pool.fetch(
                    "SELECT * FROM main_site_leveling WHERE user_id = $1",
                    user["unique_id"],
                )

                if leveling_user and leveling_user[0]["blacklisted"]:
                    return
                else:
                    pass

                now = datetime.datetime.utcnow().replace(tzinfo=utc)
                one_minute = now + datetime.timedelta(seconds=60)
                xp = random.randint(5, 10)

                if not leveling_user or leveling_user[0]["last_time"] is None:
                    return await self.bot.pool.execute(
                        "INSERT INTO main_site_leveling (xp, level, user_id, last_time, blacklisted, xp_bar_color, border_color, background_color) VALUES ($1, 1, $2, $3, False, $4, $5, $6)",
                        xp,
                        user["unique_id"],
                        one_minute.replace(tzinfo=utc),
                        "",
                        "",
                        "",
                    )

                leveling_user = leveling_user[0]
                if (
                    leveling_user["last_time"].replace(tzinfo=utc) is not None
                    and leveling_user["last_time"].replace(tzinfo=utc) > now
                ):
                    return
                else:
                    await self.bot.pool.execute(
                        "UPDATE main_site_leveling SET last_time = $1 WHERE user_id = $2",
                        one_minute.replace(tzinfo=utc),
                        user["unique_id"],
                    )
                    await self.bot.pool.execute(
                        "UPDATE main_site_leveling SET xp = xp + $1 WHERE user_id = $2",
                        xp,
                        user["unique_id"],
                    )
                    await self.lvl_up(user, message)

    async def lvl_up(self, db_user, message):
        user = await self.bot.pool.fetch("SELECT * FROM main_site_leveling WHERE user_id = $1", db_user["unique_id"])
        xp = user[0]["xp"]
        lvl = user[0]["level"]
        if xp >= lvl * 50:
            await self.bot.pool.execute(
                "UPDATE main_site_leveling SET level = level + 1, xp = $1 WHERE user_id = $2",
                0,
                db_user["unique_id"],
            )
            await message.channel.send(
                f"Congrats {message.author}, you are now **Level {user[0]['level'] + 1}** :tada:"
            )

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.message_id == 780106851961667614:
            # Updates
            if payload.emoji.id == 780103995879325696:
                role = self.bot.main_guild.get_role(716723291011678319)
                await payload.member.add_roles(role, reason="Assignable Roles")
            # NSFW Channel
            if payload.emoji.name == "🔞":
                role = self.bot.main_guild.get_role(716723357336338482)
                await payload.member.add_roles(role, reason="Assignable Roles")
            # Giveaways
            if payload.emoji.id == 780103641519358013:
                role = self.bot.main_guild.get_role(779891942464421928)
                await payload.member.add_roles(role, reason="Assignable Roles")
            # Polls
            if payload.emoji.id == 780103746432139274:
                role = self.bot.main_guild.get_role(750771398636601354)
                await payload.member.add_roles(role, reason="Assignable Roles")
            # Announcements
            if payload.emoji.id == 780103872668237835:
                role = self.bot.main_guild.get_role(716723257663029372)
                await payload.member.add_roles(role, reason="Assignable Roles")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        payload.member = self.bot.main_guild.get_member(payload.user_id)
        if payload.message_id == 780106851961667614:
            # Updates
            if payload.emoji.id == 780103995879325696:
                role = self.bot.main_guild.get_role(716723291011678319)
                await payload.member.remove_roles(role, reason="Assignable Roles")
            # NSFW Channel
            if payload.emoji.name == "🔞":
                role = self.bot.main_guild.get_role(716723357336338482)
                await payload.member.remove_roles(role, reason="Assignable Roles")
            # Giveaways
            if payload.emoji.id == 780103641519358013:
                role = self.bot.main_guild.get_role(779891942464421928)
                await payload.member.remove_roles(role, reason="Assignable Roles")
            # Polls
            if payload.emoji.id == 780103746432139274:
                role = self.bot.main_guild.get_role(750771398636601354)
                await payload.member.remove_roles(role, reason="Assignable Roles")
            # Announcements
            if payload.emoji.id == 780103872668237835:
                role = self.bot.main_guild.get_role(716723257663029372)
                await payload.member.remove_roles(role, reason="Assignable Roles")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        # Adding member role if they already passed member screening somehow..
        if member.guild.id == self.bot.main_guild.id and not member.bot:
            if member.pending is False:
                role = member.guild.get_role(716732766796120156)
                await member.add_roles(role)

            # wanted to do join logs but too lazy...
            # members = sorted(self.bot.main_guild.members, key = lambda m: m.joined_at)
            # joined_position = list(members).index(member) + 1
        if member.guild == self.bot.main_guild and member.bot:
            role = member.guild.get_role(716684129453735936)
            await member.add_roles(role)

        if member.guild == self.bot.verification_guild:
            if member.bot:
                bot_role = self.bot.verification_guild.get_role(763187834219003934)
                await member.add_roles(bot_role)
                overwrites = {
                    member.guild.get_role(763177553636098082): discord.PermissionOverwrite(manage_channels=True),
                    member.guild.get_role(763187834219003934): discord.PermissionOverwrite(read_messages=False),
                    member: discord.PermissionOverwrite(read_messages=True),
                }
                category = await member.guild.create_category(name=member.name, overwrites=overwrites)
                channel = await category.create_text_channel(name="Testing")
                await category.create_text_channel(name="Testing-NSFW", nsfw=True)
                await category.create_voice_channel(name="Voice Testing", bitrate=member.guild.bitrate_limit)
                self.test_categories[member.id] = category.id

                site_bot_data = await self.bot.pool.fetchrow("SELECT * FROM main_site_bot WHERE id = $1", member.id)
                if site_bot_data:
                    bot_owner_id = int(site_bot_data["main_owner"])
                    try:
                        bot_owner = self.bot.main_guild.get_member(
                            bot_owner_id
                        ) or await self.bot.main_guild.fetch_member(bot_owner_id)
                    except discord.NotFound:
                        bot_owner = None

                    owner_string = f"{bot_owner} ({bot_owner_id})" if bot_owner else bot_owner_id

                    embed = discord.Embed(
                        title=str(member),
                        color=discord.Color.blurple(),
                        description=(
                            f"**Owner:** {owner_string}\n"
                            f"**Prefix:** {site_bot_data['prefix']}\n"
                            f"**Tags:** {', '.join(list(site_bot_data['tags']))}\n"
                            f"**Added:** {site_bot_data['added'].strftime('%F')}\n\n"
                            f"**Short Description:** {site_bot_data['short_description']}\n"
                        ),
                    )
                    embed.add_field(
                        name="**Links**",
                        value=(
                            f"**Privacy Policy:** {site_bot_data['privacy_policy_url'] or 'None'}\n"
                            f"**Website:** {site_bot_data['website'] or 'None'}\n"
                            f"**Invite:** {site_bot_data['invite_url'] or 'Default'}\n"
                            f"**Blist Link:** https://blist.xyz/bot/{member.id}/"
                        ),
                    )

                    embed.add_field(name="Notes", value=site_bot_data["notes"] or "None", inline=False)
                    embed.set_thumbnail(url=member.display_avatar.url)
                    message = await channel.send(embed=embed)
                    await message.pin()
                    if not bot_owner:
                        await channel.send(f"⚠️ **The owner of this bot cannot be found in the main server. Deny it!**")

            if not member.bot:
                staff_db = await self.bot.mod_pool.fetch("SELECT * FROM staff WHERE userid=$1", member.id)
                if not staff_db:
                    return await member.kick(reason="User is not a staff member.")

                try:
                    rank_user = self.bot.main_guild.get_member(member.id) or await self.bot.main_guild.fetch_member(
                        member.id
                    )
                except discord.NotFound:
                    return await member.kick(reason="User is not in the main server.")

                rank = rank_user.top_role.name
                role = discord.utils.get(self.bot.verification_guild.roles, name=str(rank))
                if role:
                    await member.add_roles(role, role)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        # Adding member role after member screening.
        if before.guild.id == self.bot.main_guild.id and not before.bot:
            if before.pending is True and after.pending is False:
                role = self.bot.main_guild.get_role(716732766796120156)
                if role not in after.roles:
                    await after.add_roles(role)

        premium = self.bot.main_guild.get_role(716724716299091980)
        if premium not in before.roles and premium in after.roles:
            await self.bot.pool.execute("UPDATE main_site_user SET premium = True WHERE id = $1", before.id)
            bots = await self.bot.pool.fetch("SELECT * FROM main_site_bot WHERE main_owner = $1", before.id)
            servers = await self.bot.pool.fetch("SELECT * FROM main_site_server WHERE main_owner = $1", before.id)
            for bot in bots:
                await self.bot.pool.execute("UPDATE main_site_bot SET premium = True WHERE id = $1", bot["id"])
            for server in servers:
                await self.bot.pool.execute(
                    "UPDATE main_site_server SET premium = True WHERE id = $1",
                    server["id"],
                )
        if premium in before.roles and premium not in after.roles:
            await self.bot.pool.execute("UPDATE main_site_user SET premium = False WHERE id = $1", before.id)
            bots = await self.bot.pool.fetch("SELECT * FROM main_site_bot WHERE main_owner = $1", before.id)
            servers = await self.bot.pool.fetch("SELECT * FROM main_site_server WHERE main_owner = $1", before.id)
            for bot in bots:
                await self.bot.pool.execute("UPDATE main_site_bot SET premium = False WHERE id = $1", bot["id"])
            for server in servers:
                await self.bot.pool.execute(
                    "UPDATE main_site_server SET premium = False WHERE id = $1",
                    server["id"],
                )

        bug_hunter = self.bot.main_guild.get_role(716722789234638860)
        if bug_hunter not in before.roles and bug_hunter in after.roles:
            await self.bot.pool.execute("UPDATE main_site_user SET bug_hunter = True WHERE id = $1", before.id)
        if bug_hunter in before.roles and bug_hunter not in after.roles:
            await self.bot.pool.execute("UPDATE main_site_user SET bug_hunter = False WHERE id = $1", before.id)

        admin1 = self.bot.main_guild.get_role(716713266683969626)
        admin2 = self.bot.main_guild.get_role(716713238955556965)
        if admin1 not in before.roles and admin1 in after.roles:
            await self.bot.pool.execute(
                "UPDATE main_site_user SET administrator = True WHERE id = $1",
                before.id,
            )
        if admin1 in before.roles and admin1 not in after.roles:
            await self.bot.pool.execute(
                "UPDATE main_site_user SET administrator = False WHERE id = $1",
                before.id,
            )
        if admin2 not in before.roles and admin2 in after.roles:
            await self.bot.pool.execute(
                "UPDATE main_site_user SET administrator = True WHERE id = $1",
                before.id,
            )
        if admin2 in before.roles and admin2 not in after.roles:
            await self.bot.pool.execute(
                "UPDATE main_site_user SET administrator = False WHERE id = $1",
                before.id,
            )

        if before.bot:
            staff_bot = self.bot.main_guild.get_role(777575976124547072)
            if staff_bot not in before.roles and staff_bot in after.roles:
                await self.bot.pool.execute("UPDATE main_site_bot SET staff = True WHERE id = $1", before.id)
            if staff_bot in before.roles and staff_bot not in after.roles:
                await self.bot.pool.execute("UPDATE main_site_bot SET staff = False WHERE id = $1", before.id)

        # staff_roles = [716713266683969626, 716713238955556965,
        # 716713498360545352, 716713293330514041]
        set_difference1 = set(before.roles) - set(after.roles)
        set_difference2 = set(after.roles) - set(before.roles)
        if list(set_difference2) != []:
            new_roles = list(set_difference2)
            if new_roles[0].id not in self.bot.staff_roles:
                return
            await self.bot.mod_pool.execute(
                "UPDATE staff SET rank = $1 WHERE userid = $2",
                new_roles[0].name,
                before.id,
            )
            await self.update_staff_embed(self.bot.main_guild)
            if not before.bot:
                rank_user = self.bot.verification_guild.get_member(before.id)
                if not rank_user:
                    return

                before_rank = before.top_role.name
                before_role = discord.utils.get(self.bot.verification_guild.roles, name=str(before_rank))
                if before_role and before_role in rank_user.roles:
                    await rank_user.remove_roles(before_role)

                after_rank = after.top_role.name
                after_role = discord.utils.get(self.bot.verification_guild.roles, name=str(after_rank))
                if after_role and after_role not in rank_user.roles:
                    await rank_user.add_roles(after_role)

        # else:
        #    new_roles = list(set_difference1)
        #    await self.bot.mod_pool.execute("UPDATE staff SET rank = $1 WHERE userid = $2", new_roles[0].id, before.id)

    @staticmethod
    def __parse_message_contents(message: discord.Message) -> str:
        fields = {"content": message.content, "attachments": [], "embeds": [], "components": []}
        for attachment in message.attachments:
            fields["attachments"].append(attachment.url)
        for embed in message.embeds:
            fields["embeds"].append(json.dumps(embed.to_dict()))
        for component in message.components:
            fields["components"].append(json.dumps(component.to_dict()))

        return "\n".join(f"{key.upper()}: {str(value)}" for key, value in fields.items())

    @staticmethod
    async def __fetch_bot_inviter_from_auditlogs(
        bot: discord.Member, limit: int = 10, **kwargs: Any
    ) -> Optional[Union[discord.Member, discord.User, discord.Object]]:
        async for entry in bot.guild.audit_logs(limit=limit, action=discord.AuditLogAction.bot_add, **kwargs):
            print("audit entry", entry, entry.target, entry.user, entry.user_id, bot.id)
            if entry.target and str(entry.target.id) == str(bot.id):
                return entry.user or discord.Object(entry.user_id) if entry.user_id else None
        return None

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if member.guild == self.bot.verification_guild and member.bot:
            second_try = discord.utils.get(member.guild.categories, name=member.name)
            second_try = second_try.id if second_try else None
            get_category_id = self.test_categories.get(member.id, second_try)
            admin_logs = self.bot.main_guild.get_channel(797186257061937152)
            if get_category_id:
                all_messages = []
                category: discord.CategoryChannel = member.guild.get_channel(get_category_id)  # type: ignore
                reviewed_by = None
                for channel in list(category.text_channels) + list(category.voice_channels):
                    if channel.type != discord.ChannelType.voice:
                        messages = [msg async for msg in channel.history(limit=None, after=channel.created_at)]
                        reviewed_by = discord.utils.find(
                            lambda m: m.content.lower() in ["b!approve", "b!deny"],
                            messages,
                        )
                        for x in messages:
                            contents = self.__parse_message_contents(x)
                            all_messages.append(f"[#{x.channel.name} | {x.author.name}]:\n{contents}")

                    await channel.delete()

                file_name = f'{member.name.replace(" ", "_")}.txt'
                file = io.StringIO("\n---------\n".join(all_messages))
                reviewed_by = f"{str(reviewed_by.author)} ({reviewed_by.id})" if reviewed_by else "Not Found"
                invited_by = await self.__fetch_bot_inviter_from_auditlogs(member)
                invited_by = f"{str(invited_by)} ({invited_by.id})" if invited_by else "Not Found"
                review_embed = discord.Embed(
                    title="Bot reviewed",
                    color=discord.Color.blurple(),
                    description=wrap(
                        f"""
                    **Bot**: {str(member)} ({member.id})
                    **Reviewed by**: {reviewed_by}\n
                    **Invited by**: {invited_by}
                    **Total Messages**: {len(all_messages)}
                    **Time Taken**: {time_took(category.created_at)}
                    """
                    ),
                )
                await admin_logs.send(embed=review_embed, file=discord.File(file, file_name))  # type: ignore

                await category.delete()
                try:
                    del self.test_categories[member.id]
                except KeyError:
                    pass

        muted = await self.bot.mod_pool.fetchval("SELECT userid FROM mutes WHERE userid = $1", member.id)
        if muted:
            await member.guild.ban(discord.Object(id=member.id), reason="Left whilst muted")

        if member.guild == self.bot.main_guild:
            if member.bot:
                x = await self.bot.pool.fetch("SELECT * FROM main_site_bot WHERE id = $1", member.id)
                if x:
                    embed = discord.Embed(
                        description=f"{member} ({member.id}) has left the server and is listed on the site! Use `b!delete` to delete the bot",
                        color=discord.Color.red(),
                    )
                    await self.bot.get_channel(716727091818790952).send(embed=embed)
                    return
            if not member.bot:
                note_fmt = "⚠️ **The owner of the bot that is being tested here ({bot_name} ({bot_id})) has left the main server. Deny it!**"
                user_bots = (
                    await self.bot.pool.fetch("SELECT * FROM main_site_bot WHERE main_owner = $1", member.id) or []
                )
                if user_bots:
                    parsed_bots = []
                    for bot in user_bots:
                        bot_id = bot["id"]
                        bot_unique_id = bot["unique_id"]
                        if bot["denied"]:
                            await self.bot.pool.execute(
                                "DELETE FROM main_site_vote WHERE bot_id=$1",
                                bot_unique_id,
                            )
                            await self.bot.pool.execute(
                                "DELETE FROM main_site_review WHERE bot_id=$1",
                                bot_unique_id,
                            )
                            await self.bot.pool.execute(
                                "DELETE FROM main_site_auditlogaction WHERE bot_id=$1",
                                bot_unique_id,
                            )
                            await self.bot.pool.execute("DELETE FROM main_site_bot WHERE id=$1", bot_id)
                            return

                        parsed_bots.append(f"{bot['username']} (<@{bot['id']}>)")

                        if testing_category_id := self.test_categories.get(bot_id):
                            testing_category = self.bot.verification_guild.get_channel(testing_category_id)
                            if testing_category:
                                for chan in testing_category.text_channels:
                                    try:
                                        await chan.send(note_fmt.format(bot_name=bot["username"], bot_id=bot_id))
                                    except:
                                        pass

                    bots = " \n".join(f"- {x}" for x in parsed_bots)
                    listed_bots = f"{len(user_bots)} bot listed{'s' if len(user_bots) > 1 else ''}:"
                    embed = discord.Embed(
                        description=f"{member} ({member.id}) left the server and has {listed_bots}:\n\n{bots}\n\n",
                        color=discord.Color.red(),
                    )
                    embed.set_footer(
                        text=f"Use the `b!delete` command to delete the bot{'s' if len(user_bots) > 1 else ''}"
                    )
                    await self.bot.get_channel(716727091818790952).send(embed=embed)

    @commands.Cog.listener("on_ready")
    async def if_bot_restarted(self):
        test_categories = [
            x for x in self.bot.verification_guild.categories if x.id not in [763183878457262083, 734527161289015338]
        ]
        if test_categories:
            for cat in test_categories:
                if testing_bot := discord.utils.get(self.bot.verification_guild.members, name=cat.name):
                    self.test_categories[testing_bot.id] = cat.id

    @tasks.loop(minutes=30)
    async def check_join(self):
        bots = await self.bot.pool.fetch(
            "SELECT id, username, uses_slash_commands FROM main_site_bot WHERE approved = True"
        )
        channel = self.bot.main_guild.get_channel(716727091818790952)

        emb = discord.Embed(
            title="Bot(s) Not Found!",
            description="The following bot(s) have not joined the Support Server after getting approved...",
            color=discord.Color.red(),
        )
        emb.set_footer(text="Please add them to the server using the invite!")
        total = 0
        for bot in bots:
            bot_id = bot["id"]
            if bot_id == 765175524594548737:
                return
            try:
                bot_member = self.bot.main_guild.get_member(bot_id) or await self.bot.main_guild.fetch_member(bot_id)
            except discord.NotFound:
                bot_member = None

            if not bot_member:
                invite = str(discord.utils.oauth_url(bot_id, guild=self.bot.main_guild, disable_guild_select=True))
                emb.description += f"\n- [{bot['username']} ({bot_id})]({invite})"
                total += 1

        if total:
            emb.title = f"{total} {emb.title}"
            await channel.send(embed=emb)

    # Minutes = 60 is better than Hours = 1!! This is for you @A Discord User @Soheab_
    @tasks.loop(minutes=60)
    async def update_statuses(self):
        bots = await self.bot.pool.fetch("SELECT * FROM main_site_bot WHERE approved = True")
        for bot in bots:
            member_instance = self.bot.main_guild.get_member(bot["id"])
            if member_instance is None:
                break
            await self.bot.pool.execute(
                "UPDATE main_site_bot SET status = $1 WHERE id = $2",
                str(member_instance.status),
                bot["id"],
            )

    @tasks.loop(minutes=1)
    async def change_status(self):
        approved_bots = await self.bot.pool.fetchval(
            "SELECT COUNT(*) FROM main_site_bot WHERE approved = True AND denied = False"
        )
        users = await self.bot.pool.fetchval("SELECT COUNT(*) FROM main_site_user")
        queued_bots = await self.bot.pool.fetchval(
            "SELECT COUNT(*) FROM main_site_bot WHERE approved = False AND denied = False"
        )
        options = [
            f"with {queued_bots} bots in the queue",
            f"with {approved_bots} approved bots",
            f"with {users} total users",
        ]
        await self.bot.change_presence(activity=discord.Game(name=random.choice(options)))

    # i agree, @A Trash Coder .
    @tasks.loop(minutes=60)
    async def check_bot_testing(self):
        queued_bots = await self.bot.pool.fetch(
            "SELECT added, id FROM main_site_bot WHERE approved = False AND denied = False"
        )
        if not queued_bots:
            return

        for x in queued_bots:
            bot_id: int = x["id"]
            if testing_category_id := self.test_categories.get(bot_id):
                testing_category = self.bot.verification_guild.get_channel(testing_category_id)
                if not testing_category:
                    continue

                bot_member = self.bot.verification_guild.get_member(bot_id)
                category_created_at = testing_category.created_at.replace(tzinfo=datetime.timezone.utc)
                testing_hours = time_took(
                    dt=category_created_at,
                    only_hours=True,
                    now_dt=datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc),
                )

                if int(testing_hours) >= 2:
                    ovm = [x for x in testing_category.overwrites if isinstance(x, discord.Member) and not x.bot]
                    if ovm:  # user overwrites, hold command is used.
                        return
                    else:
                        invited_by = (await self.__fetch_bot_inviter_from_auditlogs(),)  # before=category_created_at
                        invited_by = f" (Invited by {invited_by[0].user.mention})" if invited_by else ""
                        for channel in testing_category.text_channels:
                            try:
                                await channel.send(
                                    f"Friendly reminder that {bot_member.mention}{invited_by} has been waiting for "
                                    f"more than {testing_hours} hours without the category being on hold "
                                    f"via the `b!hold` command. Please use that command if you are waiting for a "
                                    "response or mention someone who can take over the review from you."
                                )
                            except:
                                pass

    @tasks.loop(hours=72)
    async def check_bot_owner(self):
        site_bots = await self.bot.pool.fetch("SELECT * FROM main_site_bot WHERE approved = True")

        def parse_owners(bot) -> list:
            owner_ids = [int(bot["main_owner"])]
            for _id in bot["owners"].split(" "):
                if _id:
                    owner_ids.append(int(_id))

            return owner_ids

        not_in_server = []
        for bot in site_bots:
            owner_ids = parse_owners(bot)

            found = None
            for mid in owner_ids:
                try:
                    found = self.bot.main_guild.get_member(mid) or await self.bot.main_guild.fetch_member(mid)
                except discord.NotFound:
                    continue

                if found:
                    break

            if not found:
                not_in_server.append(bot)

        embeds = []
        if not_in_server:
            get_owners = lambda bot: ", ".join(f"<@{o}>" for o in parse_owners(bot))
            joined = "\n".join(
                f"- {bot['username']} ({bot['id']}) | Owners: {get_owners(bot)}" for bot in not_in_server
            )
            pag = commands.Paginator(prefix="", suffix="", max_size=6000)
            for line in joined.split("\n"):
                pag.add_line(line)

            for page in pag.pages:
                emb = discord.Embed(
                    title="Check bot owners task",
                    description=f"**All owner of the following bots have left the server:**\n{page}",
                )
                emb.set_footer(text="Use b!delete to delete them from the site!")
                embeds.append(emb)

            await self.bot.get_channel(793522769999953970).send(embeds=embeds)

    @check_bot_testing.before_loop
    @change_status.before_loop
    @update_statuses.before_loop
    @check_join.before_loop
    # @check_bot_owner.before_loop
    async def before_loops(self):
        await self.bot.wait_until_ready()

    def cog_load(self) -> None:
        self._old_on_error = self.bot.on_error
        self.bot.on_error = self.new_on_error
        self.check_join.start()
        self.change_status.start()
        self.update_statuses.start()
        self.check_bot_testing.start()
        # self.check_bot_owner.start()

    def cog_unload(self):
        self.bot.on_error = self._old_on_error
        self.check_join.stop()
        self.change_status.stop()
        self.update_statuses.stop()
        self.check_bot_testing.stop()
        # self.check_bot_owner.stop()


async def setup(bot: Blist):
    await bot.add_cog(Events(bot))
