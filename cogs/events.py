import datetime
import random
import re
import os
import sys
from operator import ne
from textwrap import dedent as wrap

import config
import discord
from discord.ext import commands, tasks, flags
from utils.time import time_took
import pytz

utc = pytz.UTC


class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.old_on_error = bot.on_error
        bot.on_error = self.new_on_error
        self.test_categories = {}
        self.check_join.start()  # pylint: disable=no-member
        self.change_status.start()
        self.update_statuses.start()
        self.check_bot_testing.start()

    def cog_unload(self):
        self.bot.on_error = self.old_on_error

    async def update_staff_embed(self, guild: discord.Guild):
        web_mods_query = await self.bot.mod_pool.fetch("SELECT userid, country_code FROM staff WHERE rank = $1",
                                                       'Website Moderator')
        senior_web_mod_query = await self.bot.mod_pool.fetch("SELECT userid, country_code FROM staff WHERE rank = $1",
                                                             'Senior Website Moderator')
        admins_query = await self.bot.mod_pool.fetch("SELECT userid, country_code FROM staff WHERE rank = $1",
                                                     'Administrator')
        senior_admins_query = await self.bot.mod_pool.fetch("SELECT userid, country_code FROM staff WHERE rank = $1",
                                                            'Senior Administrator')
        senior_administrators = [
            f"{guild.get_member(user['userid']).mention} :flag_{str(user['country_code']).lower()}:" for user in
            senior_admins_query]
        administrators = [
            f"{guild.get_member(user['userid']).mention} :flag_{str(user['country_code']).lower()}:" for user in
            admins_query]
        senior_website_moderators = [
            f"{guild.get_member(user['userid']).mention} :flag_{str(user['country_code']).lower()}:" for user in
            senior_web_mod_query]
        website_moderators = [
            f"{guild.get_member(user['userid']).mention} :flag_{str(user['country_code']).lower()}:" for user in
            web_mods_query]

        embed = discord.Embed(color = discord.Color.blurple(), title = "Staff")
        embed.add_field(name = "> Senior Administrators",
                        value = "\n".join(senior_administrators) or "None", inline = False)
        embed.add_field(name = "> Administrators",
                        value = "\n".join(administrators) or "None", inline = False)
        embed.add_field(name = "> Senior Website Moderators", value = "\n".join(
            senior_website_moderators) or "None", inline = False)
        embed.add_field(name = "> Website Moderators",
                        value = "\n".join(website_moderators) or "None", inline = False)
        channel = guild.get_channel(716823743644696586)
        message = await channel.fetch_message(723641541486182410)
        await message.edit(embed = embed)

    @property
    def error_webhook(self):
        token = config.error_webhook_token
        web_id = config.error_webhook_id
        hook = discord.Webhook.partial(
            id = web_id, token = token, adapter = discord.AsyncWebhookAdapter(self.bot.session))
        return hook

    async def new_on_error(self, event, *args, **kwargs):
        error = sys.exc_info()
        if not error[1]:
            return
        em = discord.Embed(
            title = 'Bot Error:',
            description = f'**Event**: {event}\n```py\n{error[1]}\n\n{error}```',
            color = discord.Color.blurple()
        )
        await self.error_webhook.send(embed = em)

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        ignored = (commands.CommandNotFound, commands.DisabledCommand, commands.TooManyArguments)
        send_embed = (commands.MissingPermissions, discord.HTTPException, commands.NotOwner,
                      commands.CheckFailure, commands.MissingRequiredArgument, commands.BadArgument,
                      commands.BadUnionArgument, flags.ArgumentParsingError)

        errors = {
            commands.MissingPermissions: "You do not have permissions to run this command.",
            discord.HTTPException: "There was an error connecting to Discord. Please try again.",
            commands.CommandInvokeError: "There was an issue running the command.",
            commands.NotOwner: "You are not the owner.",
            commands.CheckFailure: "This command cannot be used in this guild!",
            commands.MissingRole: "You're missing the **{}** role",
            commands.MissingRequiredArgument: "`{}` is a required argument!"
        }

        if isinstance(error, ignored):
            return

        if isinstance(error, send_embed):
            if isinstance(error, commands.MissingRequiredArgument):
                err = errors.get(error.__class__).format(str(error.param).partition(':')[0])
            elif isinstance(error, commands.MissingRole):
                role = ctx.guild.get_role(error.missing_role)
                err = errors.get(error.__class__).format(role.mention)
            else:
                efd = errors.get(error.__class__)
                err = str(efd)
                if not efd:
                    err = str(error)

            em = discord.Embed(description = str(err), color = discord.Color.red())
            try:
                await ctx.send(embed = em)
                return
            except discord.Forbidden:
                pass

        # when error is not handled above
        em = discord.Embed(
            title = 'Bot Error:',
            description = f'```py\n{error}\n```',
            color = discord.Color.blurple()
        )
        await ctx.send(embed = discord.Embed(description = f"Something went wrong... {type(error).__name__}",
                                             color = discord.Color.red()))
        await self.error_webhook.send(embed = em)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.guild is None:
            if message.author == self.bot.user:
                return
            channel = self.bot.main_guild.get_channel(716727091818790952)
            embed = discord.Embed(color = discord.Color.blurple(), description = f"""
New Message

>>> **Author:** `{message.author} ({message.author.id})`
**Message:** ```{message.content}```
""")
            await channel.send(embed = embed)
        if message.channel.id == 743127622053003364:
            if message.attachments or re.findall(
                    r"<(?P<animated>a?):(?P<name>[a-zA-Z0-9_]{2,32}):(?P<id>[0-9]{18,22})>", message.content):
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
                leveling_user = await self.bot.pool.fetch("SELECT * FROM main_site_leveling WHERE user_id = $1",
                                                          user["unique_id"])

                if leveling_user and leveling_user[0]["blacklisted"]:
                    return
                else:
                    pass

                now = datetime.datetime.utcnow().replace(tzinfo = utc)
                one_minute = now + datetime.timedelta(seconds = 60)
                xp = random.randint(5, 10)

                if not leveling_user or leveling_user[0]["last_time"] is None:
                    return await self.bot.pool.execute(
                        "INSERT INTO main_site_leveling (xp, level, user_id, last_time, blacklisted, xp_bar_color, border_color, background_color) VALUES ($1, 1, $2, $3, False, $4, $5, $6)",
                        xp, user["unique_id"], one_minute.replace(tzinfo = utc), "", "", "")

                leveling_user = leveling_user[0]
                if leveling_user["last_time"].replace(tzinfo = utc) is not None and leveling_user["last_time"].replace(
                        tzinfo = utc) > now:
                    return
                else:
                    await self.bot.pool.execute("UPDATE main_site_leveling SET last_time = $1 WHERE user_id = $2",
                                                one_minute.replace(tzinfo = utc), user["unique_id"])
                    await self.bot.pool.execute("UPDATE main_site_leveling SET xp = xp + $1 WHERE user_id = $2", xp,
                                                user["unique_id"])
                    await self.lvl_up(user, message)

    async def lvl_up(self, db_user, message):
        user = await self.bot.pool.fetch("SELECT * FROM main_site_leveling WHERE user_id = $1", db_user["unique_id"])
        xp = user[0]["xp"]
        lvl = user[0]["level"]
        if xp >= lvl * 50:
            await self.bot.pool.execute("UPDATE main_site_leveling SET level = level + 1, xp = $1 WHERE user_id = $2",
                                        0, db_user["unique_id"])
            await message.channel.send(
                f"Congrats {message.author}, you are now **Level {user[0]['level'] + 1}** :tada:")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.message_id == 780106851961667614:
            # Updates
            if payload.emoji.id == 780103995879325696:
                role = self.bot.main_guild.get_role(716723291011678319)
                await payload.member.add_roles(role, reason = "Assignable Roles")
            # NSFW Channel
            if payload.emoji.name == "🔞":
                role = self.bot.main_guild.get_role(716723357336338482)
                await payload.member.add_roles(role, reason = "Assignable Roles")
            # Giveaways
            if payload.emoji.id == 780103641519358013:
                role = self.bot.main_guild.get_role(779891942464421928)
                await payload.member.add_roles(role, reason = "Assignable Roles")
            # Polls
            if payload.emoji.id == 780103746432139274:
                role = self.bot.main_guild.get_role(750771398636601354)
                await payload.member.add_roles(role, reason = "Assignable Roles")
            # Announcements
            if payload.emoji.id == 780103872668237835:
                role = self.bot.main_guild.get_role(716723257663029372)
                await payload.member.add_roles(role, reason = "Assignable Roles")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        payload.member = self.bot.main_guild.get_member(payload.user_id)
        if payload.message_id == 780106851961667614:
            # Updates
            if payload.emoji.id == 780103995879325696:
                role = self.bot.main_guild.get_role(716723291011678319)
                await payload.member.remove_roles(role, reason = "Assignable Roles")
            # NSFW Channel
            if payload.emoji.name == "🔞":
                role = self.bot.main_guild.get_role(716723357336338482)
                await payload.member.remove_roles(role, reason = "Assignable Roles")
            # Giveaways
            if payload.emoji.id == 780103641519358013:
                role = self.bot.main_guild.get_role(779891942464421928)
                await payload.member.remove_roles(role, reason = "Assignable Roles")
            # Polls
            if payload.emoji.id == 780103746432139274:
                role = self.bot.main_guild.get_role(750771398636601354)
                await payload.member.remove_roles(role, reason = "Assignable Roles")
            # Announcements
            if payload.emoji.id == 780103872668237835:
                role = self.bot.main_guild.get_role(716723257663029372)
                await payload.member.remove_roles(role, reason = "Assignable Roles")

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
                    member.guild.get_role(763177553636098082): discord.PermissionOverwrite(manage_channels = True),
                    member.guild.get_role(763187834219003934): discord.PermissionOverwrite(read_messages = False),
                    member: discord.PermissionOverwrite(read_messages = True),
                }
                category = await member.guild.create_category(name = member.name, overwrites = overwrites)
                channel = await category.create_text_channel(name = "Testing")
                await category.create_text_channel(name = "Testing-NSFW", nsfw = True)
                await category.create_voice_channel(name = "Voice Testing", bitrate = member.guild.bitrate_limit)
                try:
                    self.test_categories[member.id] = category.id
                except Exception:
                    pass

                bot = await self.bot.pool.fetch("SELECT * FROM main_site_bot WHERE id = $1", member.id)
                if not bot:
                    pass
                else:
                    embed = discord.Embed(
                        title = str(member),
                        color = discord.Color.blurple(),
                        description = wrap(
                            f"""
                            >>> Owner: ``{str(self.bot.main_guild.get_member(bot[0]['main_owner']))}``
                            Prefix: ``{bot[0]['prefix']}``
                            Tags: ``{', '.join(list(bot[0]['tags']))}``
                            Added: ``{bot[0]['added'].strftime('%F')}``
                            """
                        )
                    )
                    embed.add_field(
                        name = "**Links**",
                        value = wrap(
                            f"""
                            >>> Privacy Policy: {bot[0]['privacy_policy_url'] or 'None'}
                            Website: {bot[0]['website'] or 'None'}
                            Invite: {bot[0]['invite_url'] or 'Default'}
                            Blist Link: https://blist.xyz/bot/{member.id}/
                            """
                        )
                    )
                    embed.add_field(name = "Short Description",
                                    value = bot[0]['short_description'], inline = False)
                    embed.add_field(name = "Notes", value = bot[0]['notes'] or 'None', inline = False)
                    embed.set_thumbnail(url = member.avatar_url)
                    message = await channel.send(embed = embed)
                    await message.pin()

            if not member.bot:
                rank_user = self.bot.main_guild.get_member(member.id)
                if not rank_user:
                    return
                rank = rank_user.top_role.name
                role = discord.utils.get(self.bot.verification_guild.roles, name = str(rank))
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
                await self.bot.pool.execute("UPDATE main_site_server SET premium = True WHERE id = $1", server["id"])
        if premium in before.roles and premium not in after.roles:
            await self.bot.pool.execute("UPDATE main_site_user SET premium = False WHERE id = $1", before.id)
            bots = await self.bot.pool.fetch("SELECT * FROM main_site_bot WHERE main_owner = $1", before.id)
            servers = await self.bot.pool.fetch("SELECT * FROM main_site_server WHERE main_owner = $1", before.id)
            for bot in bots:
                await self.bot.pool.execute("UPDATE main_site_bot SET premium = False WHERE id = $1", bot["id"])
            for server in servers:
                await self.bot.pool.execute("UPDATE main_site_server SET premium = False WHERE id = $1", server["id"])

        bug_hunter = self.bot.main_guild.get_role(716722789234638860)
        if bug_hunter not in before.roles and bug_hunter in after.roles:
            await self.bot.pool.execute("UPDATE main_site_user SET bug_hunter = True WHERE id = $1", before.id)
        if bug_hunter in before.roles and bug_hunter not in after.roles:
            await self.bot.pool.execute("UPDATE main_site_user SET bug_hunter = False WHERE id = $1", before.id)

        admin1 = self.bot.main_guild.get_role(716713266683969626)
        admin2 = self.bot.main_guild.get_role(716713238955556965)
        if admin1 not in before.roles and admin1 in after.roles:
            await self.bot.pool.execute("UPDATE main_site_user SET administrator = True WHERE id = $1", before.id)
        if admin1 in before.roles and admin1 not in after.roles:
            await self.bot.pool.execute("UPDATE main_site_user SET administrator = False WHERE id = $1", before.id)
        if admin2 not in before.roles and admin2 in after.roles:
            await self.bot.pool.execute("UPDATE main_site_user SET administrator = True WHERE id = $1", before.id)
        if admin2 in before.roles and admin2 not in after.roles:
            await self.bot.pool.execute("UPDATE main_site_user SET administrator = False WHERE id = $1", before.id)

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
            await self.bot.mod_pool.execute("UPDATE staff SET rank = $1 WHERE userid = $2", new_roles[0].name,
                                            before.id)
            await self.update_staff_embed(self.bot.main_guild)
            if not before.bot:
                rank_user = self.bot.verification_guild.get_member(before.id)
                if not rank_user:
                    return

                before_rank = before.top_role.name
                before_role = discord.utils.get(self.bot.verification_guild.roles, name = str(before_rank))
                if before_role and before_role in rank_user.roles:
                    await rank_user.remove_roles(before_role)

                after_rank = after.top_role.name
                after_role = discord.utils.get(self.bot.verification_guild.roles, name = str(after_rank))
                if after_role and after_role not in rank_user.roles:
                    await rank_user.add_roles(after_role)

        # else:
        #    new_roles = list(set_difference1)
        #    await self.bot.mod_pool.execute("UPDATE staff SET rank = $1 WHERE userid = $2", new_roles[0].id, before.id)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        if member.guild == self.bot.verification_guild and member.bot:
            second_try = discord.utils.get(member.guild.categories, name = member.name)
            second_try = second_try.id if second_try else None
            get_category_id = self.test_categories.get(member.id, second_try)
            admin_logs = self.bot.main_guild.get_channel(797186257061937152)
            if get_category_id:
                file_name = f'{member.name.replace(" ", "_")}.txt'
                file = open(file_name, "w")
                all_messages = []
                category = member.guild.get_channel(get_category_id)
                reviewed_by = None
                for channel in category.channels:
                    if channel.type != discord.ChannelType.voice:
                        messages = await channel.history(limit = None, after = channel.created_at).flatten()
                        reviewed_by = discord.utils.find(lambda m: m.content.lower() in ["b!approve", "b!deny"],
                                                         messages)
                        for x in messages:
                            content = str(
                                x.content) if not x.embeds else f"EMBED: {str(x.embeds[0].to_dict())}" if not x.content else f"CONTENT: {str(x.content)}\nEMBED: {str(x.embeds[0].to_dict())}" if x.content and x.embeds else "None"
                            all_messages.append(f"[#{x.channel.name} | {x.author.name}]: {content}" + "\n-------\n")

                    await channel.delete()

                file.writelines(all_messages)
                file.close()
                reviewed_by = f"{str(reviewed_by.author)} ({reviewed_by.id})" if reviewed_by else "Not Found"
                # this might not be that accurate.
                invited_by = await member.guild.audit_logs(limit = 2, action = discord.AuditLogAction.bot_add,
                                                           before = category.created_at).flatten()
                invited_by = f"{str(invited_by[0].user)} ({invited_by[0].user.id})" if invited_by else "Not Found"
                await admin_logs.send(
                    content = f"**Bot**: {str(member)} ({member.id})\n"
                              f"**Invited by**: {invited_by}\n\n"
                              f"**Reviewed by**: {reviewed_by}\n\n"
                              f"**Total Messages**: {len(all_messages)}\n"
                              f"**Time Took**: {time_took(category.created_at)}",
                    file = discord.File(file_name, file.name))

                await category.delete()
                try:
                    del self.test_categories[member.id]
                except KeyError:
                    pass
                if os.path.exists(file_name):
                    try:
                        os.remove(file_name)
                    except Exception:
                        pass

        muted = await self.bot.mod_pool.fetchval("SELECT userid FROM mutes WHERE userid = $1", member.id)
        if muted:
            await member.guild.ban(discord.Object(id = member.id), reason = "Left whilst muted")

        if member.guild == self.bot.main_guild:
            if member.bot:
                x = await self.bot.pool.fetch("SELECT * FROM main_site_bot WHERE id = $1", member.id)
                if x:
                    embed = discord.Embed(
                        description = f"{member} ({member.id}) has left the server and is listed on the site! Use `b!delete` to delete the bot",
                        color = discord.Color.red())
                    await self.bot.get_channel(716727091818790952).send(embed = embed)
                    return
            if not member.bot:
                x = await self.bot.pool.fetch("SELECT * FROM main_site_bot WHERE main_owner = $1", member.id)
                if x:
                    for user in x:
                        bot_id = user['id']
                        bot_unique_id = user['unique_id']
                        if user["denied"]:
                            await self.bot.pool.execute("DELETE FROM main_site_vote WHERE bot_id=$1", bot_unique_id)
                            await self.bot.pool.execute("DELETE FROM main_site_review WHERE bot_id=$1", bot_unique_id)
                            await self.bot.pool.execute("DELETE FROM main_site_auditlogaction WHERE bot_id=$1", bot_unique_id)
                            await self.bot.pool.execute("DELETE FROM main_site_bot WHERE id=$1", bot_id)
                            return
                        bots = " \n".join(
                            [f"{user['username']} (<@{user['id']}>)"])
                        listed_bots = f"{len(x)} bot listed:" if len(
                            x) == 1 else f"{len(x)} bots listed:"
                        embed = discord.Embed(
                            description = f"{member} ({member.id}) left the server and has {listed_bots}\n\n{bots} \n\nUse the `b!delete` command to delete the bot",
                            color = discord.Color.red())
                        await self.bot.get_channel(716727091818790952).send(embed = embed)

                        if user['id'] in self.test_categories.keys():
                            testing_category = self.bot.verification_guild.get_channel(self.test_categories[user['id']])
                            if not testing_category:
                                return
                            for x in testing_category.text_channels:
                                try:
                                    await x.send(f"The owner of the bot ({user['username']} (<@{user['id']}>)) "
                                                 "being tested here has left the main server, deny it!")
                                except:
                                    pass

    @commands.Cog.listener("on_ready")
    async def if_bot_restarted(self):
        await self.bot.wait_until_ready()
        test_categories = [x for x in self.bot.verification_guild.categories
                           if x.id not in [763183878457262083, 734527161289015338]]
        if test_categories:
            for cat in test_categories:
                testing_bot = discord.utils.get(self.bot.verification_guild.members, name = cat.name)
                if testing_bot:
                    self.test_categories[testing_bot.id] = cat.id

    @tasks.loop(minutes = 30)
    async def check_join(self):
        bots = await self.bot.pool.fetch("SELECT * FROM main_site_bot WHERE approved = True")
        channel = self.bot.main_guild.get_channel(716727091818790952)
        for bot in bots:
            if bot['id'] == 765175524594548737:
                return
            b = self.bot.main_guild.get_member(bot['id'])
            if not b:
                embed = discord.Embed(
                    title = "Bot Has Not Joined!!",
                    description = "The following bot has not joined the Support Server after getting approved...",
                    color = discord.Color.red()
                )
                embed.add_field(
                    name = bot['username'],
                    value = str(
                        discord.utils.oauth_url(bot['id'], guild = self.bot.main_guild)) + "&disable_guild_select=true"
                )
                await channel.send(embed = embed)

    # Minutes = 60 is better than Hours = 1!! This is for you @A Discord User @Soheab_
    @tasks.loop(minutes = 60)
    async def update_statuses(self):
        bots = await self.bot.pool.fetch("SELECT * FROM main_site_bot WHERE approved = True")
        for bot in bots:
            member_instance = self.bot.main_guild.get_member(bot["id"])
            if member_instance is None:
                break
            await self.bot.pool.execute("UPDATE main_site_bot SET status = $1 WHERE id = $2",
                                        str(member_instance.status), bot["id"])

    @tasks.loop(minutes = 1)
    async def change_status(self):
        approved_bots = await self.bot.pool.fetchval(
            "SELECT COUNT(*) FROM main_site_bot WHERE approved = True AND denied = False")
        users = await self.bot.pool.fetchval("SELECT COUNT(*) FROM main_site_user")
        queued_bots = await self.bot.pool.fetchval(
            "SELECT COUNT(*) FROM main_site_bot WHERE approved = False AND denied = False")
        options = [
            f"with {queued_bots} bots in the queue",
            f"with {approved_bots} approved bots",
            f"with {users} total users"
        ]
        await self.bot.change_presence(activity = discord.Game(name = random.choice(options)))

    # i agree, @A Trash Coder .
    @tasks.loop(minutes = 60)
    async def check_bot_testing(self):
        queued_bots = await self.bot.pool.fetch("SELECT added, id FROM main_site_bot WHERE approved = False AND denied = False")
        if not queued_bots:
            return

        for x in queued_bots:
            bot_id = x['id']
            if bot_id in self.test_categories.keys():
                testing_category = self.bot.verification_guild.get_channel(self.test_categories[bot_id])
                if not testing_category:
                    return

                bot_member = self.bot.verification_guild.get_member(bot_id)
                category_created_at = testing_category.created_at.replace(tzinfo = datetime.timezone.utc)
                testing_hours = time_took(dt = category_created_at, only_hours = True,
                                          now_dt = datetime.datetime.utcnow().replace(tzinfo = datetime.timezone.utc))

                if int(testing_hours) >= 2:
                    ovm = [x for x in testing_category.overwrites if isinstance(x, discord.Member) and not x.bot]
                    if ovm:  # user overwrites, hold command is used.
                        return
                    else:
                        for channel in testing_category.text_channels:
                            try:
                                await channel.send(
                                    f"Friendly reminder that {bot_member.mention} has been waiting for more than "
                                    f"{testing_hours} hours without the category being on hold via the `b!hold` "
                                    "command. Please use that command if you are waiting for a response or any other "
                                    "reason"
                                )
                            except:
                                pass

def setup(bot):
    bot.add_cog(Events(bot))
