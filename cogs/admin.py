import asyncio
import datetime
import importlib
import os
import re
from textwrap import dedent as wrap

import config
import country_converter as coco
import discord
from discord.ext import commands

from utils import checks


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.has_permissions(administrator=True)
    @commands.command()
    async def reloadutils(self, ctx, name: str):
        """ Reloads a utils module. """
        name_maker = f"utils/{name}.py"
        try:
            module_name = importlib.import_module(f"utils.{name}")
            importlib.reload(module_name)
        except ModuleNotFoundError:
            return await ctx.send(f"Couldn't find module named **{name_maker}**")
        except Exception as e:
            return await ctx.send(f"Module **{name_maker}** returned error and was not reloaded...\n{e}")
        await ctx.send(f"Reloaded module **{name_maker}**", delete_after = 5)

    @commands.has_permissions(administrator=True)
    @commands.command()
    async def hire(self, ctx, member: discord.Member, *, country: str):
        """
        Command to hire someone as staff this will do the following:

        1. Add Website Moderator & Staff role
        2. Add the staff bot role to the member's bot(s)
        3. Send member a invite to the verification guild if they are not offline.
        4. Set member's country flag.
        5. Update staff embed.

        **Warning:** This command should only be used once and only supports the first tier.\n
        **Warning:** This will take affect immediately, no confirmation.
        """
        verification_guild = self.bot.verification_guild
        main_guild = self.bot.main_guild
        staff_bot_role = main_guild.get_role(777575976124547072)
        staff_role = self.bot.main_guild.get_role(716713561233031239)
        web_mod_role = self.bot.main_guild.get_role(716713293330514041)
        user_bots = await self.bot.pool.fetch("SELECT * FROM main_site_bot WHERE main_owner = $1 AND approved = True", member.id)
        verification_guild_channel = self.bot.verification_guild.get_channel(
            734527843098165269)
        staff_chat_channel = self.bot.main_guild.get_channel(
            716717923359784980)

        if staff_role in member.roles or member.bot:
            return await ctx.send("That is a bot or already a staff member.")

        await self.bot.mod_pool.execute("INSERT INTO staff VALUES($1, $2)", member.id, datetime.datetime.utcnow())
        success_text = []
        roles_to_add = [staff_role, web_mod_role]
        for role in roles_to_add:
            if role not in member.roles:
                await member.add_roles(role)
                success_text.append(f"✅ **Added staff role:** {role}.")
            else:
                success_text.append(
                    f"❌ **{member} already has the:** {role} staff role.")

        if user_bots:
            for x in user_bots:
                bot = self.bot.main_guild.get_member(x['id'])
                if staff_bot_role not in bot.roles:
                    await bot.add_roles(staff_bot_role)
                    success_text.append(
                        f"✅ **Added staff bot role to: {bot} ({bot.id}).**")
                else:
                    success_text.append(
                        f"❌ **{member}'s bot: {bot} ({bot.id}) already has the staff bot role.**")
        else:
            success_text.append(
                f"❌ **{member} doesn't have any bots listed on the site.**")

        if member not in verification_guild.members:
            if member.status.value in ['online', 'idle', 'dnd']:
                generated_invite = await verification_guild_channel.create_invite(reason="new staff member", max_age=1800, max_uses=1)
                try:
                    await member.send(
                        discord.utils.escape_markdown(
                            f"Hello {member.name},\n\nHere is your personal invite to our testing server: <{generated_invite.url}>."
                            f" See more in {staff_chat_channel.mention}\n\nSincerely,\n{ctx.author.name}, on behalf of Blist"
                        )
                    )
                    success_text.append(f"✅ **Send {member} a invite to the verification server. "
                                        f"The invite is valid for 30 minutes and can only be used once.**")
                except Exception:
                    success_text.append(f"❌ **Couldn't DM {member} a invite to the verification server. DM's closed?** "
                                        f"**Here is the invite i generated for them:** <{generated_invite.url}>, "
                                        f"**it's valid for 30 minutes and can only be used once.**")
            else:
                success_text.append(f"❌ **{member} is not online, "
                                    f"therefore i didn't send them a invite to the verification server.**")
        else:
            success_text.append(
                f"❌ **{member} is already in the verification server...**")

        # set country flag from forum ---------------
        iso2_country = coco.convert(names=country, to='ISO2')
        if iso2_country != "not found":

            member_in_db = await self.bot.mod_pool.fetch("SELECT * FROM staff WHERE userid = $1", member.id)
            if not member_in_db:
                success_text.append(
                    f"❌ **Couldn't set {member}'s country flag because:** they aren't in the database.")
            else:
                await self.bot.mod_pool.execute("UPDATE staff SET country_code = $1 WHERE userid = $2", iso2_country, member.id)
                success_text.append(
                    f"✅ **Set {member}'s country to:** {iso2_country}.")
        else:
            success_text.append(f"❌ **Couldn't set {member}'s country flag because:** "
                                f"{country} is not a valid country or something else happened.")

        join_list = "\n".join(success_text)
        await self.bot.pool.execute("UPDATE main_site_user SET staff = True WHERE userid = $1", member.id)
        await self.bot.mod_pool.execute("UPDATE staff SET rank = $1 WHERE userid = $2", web_mod_role.name, member.id)
        await self.bot.get_cog("Events").update_staff_embed(self.bot.main_guild)
        await ctx.send(f"Successfully hired {member} ({member.id}).\n\n{join_list}")

    @commands.has_permissions(administrator=True)
    @commands.command()
    async def fire(self, ctx, member: discord.Member):
        """
        Fire someone with confirmation from Blist.
        """
        verification_guild = self.bot.verification_guild
        main_guild = self.bot.main_guild
        staff_bot_role = main_guild.get_role(777575976124547072)
        staff_role = self.bot.main_guild.get_role(716713561233031239)
        user_bots = await self.bot.pool.fetch("SELECT * FROM main_site_bot WHERE main_owner = $1 AND approved = True", member.id)

        if staff_role not in member.roles or member.bot:
            return await ctx.send("That is a bot or not a staff member.")
        if member.id == ctx.author.id:
            atc = str(self.bot.main_guild.get_member(679118121943957504))
            adu = str(self.bot.main_guild.get_member(712737377524777001)
                      ) if ctx.author.id != 712737377524777001 else atc
            return await ctx.send(f"**{ctx.author}**, I can't let you do that. Please contact {adu} if you want to resign from your staff position at Blist. ")
        if member.top_role >= ctx.author.top_role:
            return await ctx.send(f"**{ctx.author}**, I won't let you fire someone higher than you or with the same rank.")

        msg = await ctx.send(f"**{ctx.author.name}**, do you really want to fire {member}? "
                             f"React with ✅ or ❌ in 30 seconds. **This action will remove __all__ staff privileges from {member}!**")
        await msg.add_reaction("\U00002705")
        await msg.add_reaction("\U0000274c")

        def check(r, u):
            return u.id == ctx.author.id and r.message.channel.id == ctx.channel.id and str(r.emoji) in ["\U00002705", "\U0000274c"]

        try:
            reaction, user = await self.bot.wait_for('reaction_add', check=check, timeout=30)
        except asyncio.TimeoutError:
            await msg.remove_reaction("\U00002705", ctx.guild.me)
            await msg.remove_reaction("\U0000274c", ctx.guild.me)
            await msg.edit(content=f"~~{msg.content}~~ i guess not, cancelled.")
            return
        else:
            if str(reaction.emoji) == "\U00002705":
                await msg.remove_reaction("\U00002705", ctx.guild.me)
                await msg.remove_reaction("\U0000274c", ctx.guild.me)
                await msg.edit(content=f"~~{msg.content}~~ You reacted with ✅:")
                pass
            if str(reaction.emoji) == "\U0000274c":
                await msg.remove_reaction("\U00002705", ctx.guild.me)
                await msg.remove_reaction("\U0000274c", ctx.guild.me)
                await msg.edit(content=f"~~{msg.content}~~ okay, cancelled.")
                return

        success_text = []
        for role_id in self.bot.staff_roles:
            author_roles = [role.id for role in member.roles]
            if role_id in author_roles:
                await member.remove_roles(self.bot.main_guild.get_role(role_id))
                success_text.append(
                    f"✅ **Removed staff role:** {self.bot.main_guild.get_role(role_id)}.")
            else:
                success_text.append(
                    f"❌ **{member} didn't have the staff role:** {self.bot.main_guild.get_role(role_id)}.")

        if user_bots:
            for x in user_bots:
                bot = self.bot.main_guild.get_member(x['id'])
                if staff_bot_role in bot.roles:
                    await bot.remove_roles(staff_bot_role)
                    success_text.append(
                        f"✅ **Removed staff bot role from:** {bot} ({bot.id}).")
                else:
                    success_text.append(
                        f"❌ **{member}'s bot:** {bot} ({bot.id}) **didn't have the staff bot role.**")
        else:
            success_text.append(
                f"❌ **{member} didn't have any bots listed on the site.**")

        if member in verification_guild.members:
            await self.bot.verification_guild.get_member(member.id).kick()
            success_text.append(
                f"✅ **Kicked {member} from the verification server.**")
        else:
            success_text.append(
                f"❌ **{member} wasn't in the verification server...**")

        join_list = "\n".join(success_text)
        await self.bot.mod_pool.execute("DELETE FROM staff WHERE userid = $1", member.id)
        await ctx.send(f"Successfully fired {member} ({member.id}).\n\n{join_list}")

    @commands.has_permissions(administrator=True)
    @commands.command()
    async def rr(self, ctx):
        embed = discord.Embed(color=discord.Color.blurple(),
                              title="Assignable Roles", inline=False)
        embed.add_field(name="> <a:updating:780103995879325696>",
                        value="Get updates from our site", inline=False)
        embed.add_field(
            name="> :underage:", value="Allows access to NSFW channels. 18+ ONLY", inline=False)
        embed.add_field(name="> <a:giveaway:780103641519358013>",
                        value="Be notified when we host giveaways", inline=False)
        embed.add_field(name="> <a:check_animated:780103746432139274>",
                        value="Get pinged when we host polls for our site", inline=False)
        embed.add_field(name="> <:announcementchannel:780103872668237835>",
                        value="Get pinged when we have announcements", inline=False)
        embed.add_field(name="> <a:Loading:784923587785916487>",
                        value="Get pinged when we have new leaks", inline=False)
        ch = self.bot.main_guild.get_channel(716733254308462702)
        msg = await ch.fetch_message(780106851961667614)
        await msg.edit(embed=embed)
        await msg.add_reaction(self.bot.get_emoji(780103995879325696))
        await msg.add_reaction("🔞")
        await msg.add_reaction(self.bot.get_emoji(780103641519358013))
        await msg.add_reaction(self.bot.get_emoji(780103746432139274))
        await msg.add_reaction(self.bot.get_emoji(780103872668237835))
        await msg.add_reaction(self.bot.get_emoji(784923587785916487))
        await ctx.send("Done")

    @commands.has_permissions(administrator=True)
    @commands.command()
    async def set_country(self, ctx, member: discord.Member, *, country):
        if member.bot:
            return await ctx.send("Shut Up")

        iso2 = coco.convert(names=country, to='ISO2')
        if iso2 == "not found":
            return await ctx.send("This is not a valid country")

        query = await self.bot.mod_pool.fetch("SELECT * FROM staff WHERE userid = $1", member.id)
        if not query:
            return await ctx.send("This user is not in the database")

        await self.bot.mod_pool.execute("UPDATE staff SET country_code = $1 WHERE userid = $2", iso2, member.id)
        await ctx.send("Done")

    @commands.has_permissions(administrator=True)
    @commands.command()
    async def set_rank(self, ctx, member: discord.Member, *, rank):
        if member.bot:
            return await ctx.send("Shut Up")

        ranks = ["Senior Administrator", "Administrator",
                 "Senior Website Moderator", "Website Moderator"]
        if rank not in ranks:
            return await ctx.send(f"{rank} is not a valid rank")

        query = await self.bot.mod_pool.fetch("SELECT * FROM staff WHERE userid = $1", member.id)
        if not query:
            return await ctx.send("This user is not in the database")

        await self.bot.mod_pool.execute("UPDATE staff SET rank = $1 WHERE userid = $2", rank, member.id)
        await ctx.send("Done")

    @commands.has_permissions(administrator=True)
    @commands.command()
    async def add(self, ctx, member: discord.Member, level):
        levels = ["bug_hunter", "developer", "administrator", "staff"]
        if level.lower() not in levels:
            await ctx.send(f"That's not a valid option, valid options are {', '.join(levels)}")
        await self.bot.pool.execute(f"UPDATE main_site_user SET {level} = True WHERE userid = $1", member.id)
        await ctx.send(f"Added {member} as {level}")

    @commands.has_permissions(administrator=True)
    @commands.command()
    async def remove(self, ctx, member: discord.Member, level: str):
        levels = ["bug_hunter", "developer", "administrator", "staff"]
        if level.lower() not in levels:
            await ctx.send(f"That's not a valid option, valid options are {', '.join(levels)}")
        await self.bot.pool.execute(f"UPDATE main_site_user SET {level} = False WHERE userid = $1", member.id)
        await ctx.send(f"Removed {member} from {level}")

    @checks.main_guild_only()
    @commands.has_permissions(administrator=True)
    @commands.group(invoke_without_command=True)
    async def certify(self, ctx, *, bot: discord.Member):
        if not bot.bot:
            await ctx.send("That is not a bot.")
            return

        is_waiting = await self.bot.pool.fetchval(
            "SELECT main_owner FROM main_site_bot WHERE certified = False AND awaiting_certification = True AND id = $1",
            bot.id
        )
        if not is_waiting:
            await ctx.send("This bot is not awaiting certification")
            return

        await self.bot.pool.execute(
            "UPDATE main_site_bot SET certified = True, awaiting_certification = False WHERE id = $1", bot.id
        )
        embed = discord.Embed(
            description=f"Certified {bot.name}", color=discord.Color.blurple())
        await ctx.send(embed=embed)

        owner = ctx.guild.get_member(is_waiting)
        em = discord.Embed(description=f"``{bot}`` by ``{owner}`` was certified",
                           color=discord.Color.blurple())

        await self.bot.pool.execute("UPDATE main_site_user SET certified_developer = True WHERE userid = $1", owner.id)
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
            embed = discord.Embed(
                description=f"❌ That is not a bot.", color=discord.Colour.red())
            await ctx.send(embed=embed)
            return

        is_waiting = await self.bot.pool.fetchval(
            "SELECT main_owner FROM main_site_bot WHERE awaiting_certification = True AND id = $1", bot.id)
        if not is_waiting:
            await ctx.send("That bot is not awaiting certification.")
            return

        await self.bot.pool.execute("UPDATE main_site_bot SET awaiting_certification = False WHERE id = $1", bot.id)
        await ctx.send(f"Denied certification for {bot.name}")
        em = discord.Embed(
            description=f"``{bot}`` by ``{ctx.guild.get_member(is_waiting)}`` was denied for certification for: \n```{reason}```",
            color=discord.Color.blurple())
        await self.bot.get_channel(716446098859884625).send(embed=em)

    @commands.has_permissions(administrator=True)
    @commands.command()
    async def poll(self, ctx, poll, image=None):
        embed = discord.Embed(title="**New Poll**:",
                              description=poll, color=discord.Color.blurple())
        if image:
            embed.set_image(url=image)
        await ctx.message.delete()
        msg = await ctx.send(content="<@&750771398636601354>", embed=embed)
        await msg.add_reaction("✅")
        await msg.add_reaction("❌")

    @commands.is_owner()
    @commands.command()
    async def purge_cache(self, ctx):
        json = {"purge_everything": True}
        headers = {
            "X-Auth-Key": config.cloudflare_token,
            "X-Auth-Email": config.cloudflare_email, "Content-Type": "application/json"}
        async with self.bot.session.post(
                url="https://api.cloudflare.com/client/v4/zones/47697d23bd0d042fd63573cc9030177d/purge_cache/",
                headers=headers, json=json) as x:
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
                    title=f"Updated cogs: " +
                    ", ".join([f"`{text}`" for text in updated]),
                    color=discord.Color.blurple())
                await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title=f"No cogs were updated.", color=discord.Color.red())
            await ctx.send(embed=embed)

    @commands.has_permissions(administrator=True)
    @commands.command()
    async def blacklist(self, ctx, userid: int, *, reason=None):
        user = await self.bot.pool.fetch(f"SELECT * FROM main_site_user WHERE userid = $1", userid)
        # headers = {
        #    "X-Auth-Key": config.cloudflare_token,
        #    "X-Auth-Email": config.cloudflare_email, "Content-Type": "application/json"}
        try:
            user = user[0]
            if user["blacklisted"] is True:
                await self.bot.pool.execute("UPDATE main_site_user SET blacklisted = False WHERE userid = $1", userid)
                await ctx.send(f"Un-Blacklisted {userid}")
                #json = {"cascade": "none"}
                # async with self.bot.session.delete(
                #    url="https://api.cloudflare.com/client/v4/zones/47697d23bd0d042fd63573cc9030177d/firewall/access_rules/rules",
                #    headers=headers, json=json) as x:
                #    await ctx.send(f'{await x.json()}')
            else:
                await self.bot.pool.execute("UPDATE main_site_user SET blacklisted = True WHERE userid = $1", userid)
                await ctx.send(f"Blacklisted {userid}")
                # json = {"mode": "block", "configuration": {
                #    "target": "ip", "value": user["ip"]}, "notes": reason}
                # async with self.bot.session.post(
                #    url="https://api.cloudflare.com/client/v4/zones/47697d23bd0d042fd63573cc9030177d/firewall/access_rules/rules",
                #    headers=headers, json=json) as x:
                #    await ctx.send(f'{await x.json()}')
        except KeyError:
            return await ctx.send("This user is not in the Database!")


    @commands.has_role(716713266683969626)
    @commands.command()
    async def xpblacklist(self, ctx, user: discord.Member):
        db_user = await self.bot.pool.fetch(f"SELECT * FROM main_site_user WHERE userid = $1", user.id)
        try:
            db_user = db_user[0]
            leveling_user = await self.bot.pool.fetch(f"SELECT * FROM main_site_leveling WHERE user_id = $1", db_user["unique_id"])
            try:
                leveling_user = leveling_user[0]
                if leveling_user["blacklisted"]:
                    await self.bot.pool.execute("UPDATE main_site_leveling SET blacklisted = False WHERE user_id = $1", db_user["unique_id"])
                    await ctx.send(f"Un-Blacklisted {user} from using leveling!")
                else:
                    await self.bot.pool.execute("UPDATE main_site_leveling SET blacklisted = True WHERE user_id = $1", db_user["unique_id"])
                    await ctx.send(f"Blacklisted {user} from using leveling!")
            except KeyError:
                return await ctx.send("This user is not in the Leveling Database!")
        except KeyError:
            return await ctx.send("This user is not in the Database!")


    @checks.main_guild_only()
    @commands.has_permissions(administrator=True)
    @commands.command(aliases=['forcestaffembed', 'staffembed', 'staff_embed'])
    async def force_update_staff_embed(self, ctx):
        event_cog = self.bot.get_cog("Events")
        await event_cog.update_staff_embed(self.bot.main_guild)
        await ctx.send(f"Updated the staff embed!")

    @checks.main_guild_only()
    @commands.has_permissions(administrator=True)
    @commands.command()
    async def rulesninfo(self, ctx):
        server_rules_list = [
            "Don't MINI MOD.",
            "Don't tag mod roles for no reason",
            "Be respectful.",
            "Don't spam.",
            "Use common sense.",
            "No Evading punishments.",
            "No NSFW.",
            "Please use the channels accordingly.",
            "Posting invites when it is relevant to the conversation(such as asking "
            "for a bot support server, minecraft server) is completely fine.However, "
            "advertising your server ( or any advertising in general) is not okay.",
            "Don't break Discord ToS"
        ]
        bot_rules_list = [
            "NSFW Commands must be restricted to NSFW only channels.",
            "Bots cannot be duplicates of other bots.",
            "Cannot contain scripts that affects the page.",
            "Bots must be online for testing.",
            "Can not violate Discord ToS.",
            "Bots must have features and at least 5 commands (Excluding any type of help commands, i.e. info, commands, etc.).",
            "Cannot send level up messages.",
            "Cannot reply to other bots.",
            "Bots must not break server rules.",
            "May not randomly respond to messages or commands not invoked without the specified prefix.",
            "Bots cannot have NSFW avatars.",
            "Must have a clean description, not junk filled.",
            "Bot owner must be in/remain in server for the bot to be listed"
        ]

        assignable_roles_channel = ctx.guild.get_channel(
            716733254308462702).mention
        server_roles_dict = {
            716722789234638860: "This is for people that report bugs to help improve the site. Gained by reporting bugs, no specific amount.",  # Bug Hunter
            # Community Contributor
            716722845773725806: "This is for people that help improve the site by suggesting things and pr'ing on our public [GitHub repositories](https://github.com/BlistBotList)",
            716713293330514041: "First Staff Tier",  # Website Moderator
            716713498360545352: "Second Staff Tier",  # Senior Website Moderator
            716713238955556965: "Third Staff Tier",  # Administrator
            716713266683969626: "Fourth Staff Tier",  # Senior Adminstrator
            # Staff
            716713561233031239: "All staff members have this role. You can [apply here](https://forms.gle/4X8cm1Ce58FR2f3P9)",
            716713204159479919: "Site owner & Creator",  # Founder
            # Updates
            716723291011678319: f"This is for if you want to get pinged for updates related to the site. Get it from {assignable_roles_channel}",
            # NSFW
            716723357336338482: f"This is for if you want access to a channel where you can play with NSFW bots/commands. Get it from {assignable_roles_channel}",
            # Announcements
            716723257663029372: f"This is for if you want to get pinged for announcements related to the site or this server. Get it from {assignable_roles_channel}",
            # Polls
            779891942464421928: f"This is for if you want to get pinged for giveaways. Get it from {assignable_roles_channel}",
            # Giveaways
            750771398636601354: f"This is for if you want to get pinged for polls related to the site and this server. Get it from {assignable_roles_channel}",
            716732766796120156: "Everyone human that joins gets this.",  # Member
            # Developer
            716684805286133840: "Everyone with a bot on the site has this. [Add a bot](https://blist.xyz/bot/add/) to the site to get it.",
            # Development Team
            716722689921908756: f"Website developer. DM {ctx.guild.get_member(679118121943957504).mention} if you know django, js and html (Must know all 3) and want to help code the site back or front.",
            # Certified Developer
            716724317207003206: "This is for people that have a certified bot. Get it by applying for certification [here](https://blist.xyz/certification/)",
            716726167713087589: "Bots with this role help with things around this server like mod related things.",  # Server Bot
            716684129453735936: "This is a role that bots get when they get approved and added to this server.",  # Bot
            716684142766456832: "This is for bots that are certified on the site.",  # Certified Bot
            764686546179325972: "This is for bots with a common prefix.",  # Common Prefix
            # Premium
            716724716299091980: "This is for if you have premium on the site. You can get it by donating 5$ or more [here](https://www.paypal.com/paypalme/trashcoder/5)",
            779817680488103956: "This is for our Social Media Manager, they manage our Official Social accounts like twitter."  # Social Media Access
        }

        main_embed = discord.Embed(color=discord.Color.blurple())
        main_embed.set_author(name="Blist.xyz", icon_url=ctx.bot.user.avatar_url_as(
            format="png"), url="https://blist.xyz/")
        main_embed.set_thumbnail(
            url=ctx.guild.icon_url_as(static_format="png"))
        main_embed.add_field(
            name="**Blist Server Rules**",
            value="\n".join(
                [f"**{num}.** {rule}" for num, rule in enumerate(server_rules_list, start=1)]),
            inline=False
        )
        main_embed.add_field(
            name="**Blist Bot Rules/Requirements**",
            value="\n".join([f"**{num}.** {rule}" for num,
                             rule in enumerate(bot_rules_list, start=1)]),
            inline=False
        )
        main_embed.add_field(
            name="**Links**",
            value=wrap(
                """
                [Site](https://blist.xyz)
                [API](https://blist.xyz/api/)
                [API Docs](https://docs.blist.xyz/)
                [Certification Info](https://blist.xyz/certification/)
                """
            ),
            inline=False
        )

        server_roles_list = []
        server_roles_embeds = []
        roles_paginator = commands.Paginator(
            prefix="", suffix="", max_size=2048)
        guild_role_ids = [x.id for x in ctx.guild.roles]
        ordered_server_roles_list = sorted(server_roles_dict.keys(
        ), key=guild_role_ids.index, reverse=True)  # put in order as in server.
        for role_id in ordered_server_roles_list:
            server_roles_list.append(
                f"{ctx.guild.get_role(role_id).mention}: {server_roles_dict[role_id]}")

        join_dict = "\n".join(server_roles_list)
        server_roles_content = [join_dict[i:i + 2000]
                                for i in range(0, len(join_dict), 2000)]
        for page in server_roles_content:
            roles_paginator.add_line(page)

        for page_content in roles_paginator.pages:
            server_roles_embeds.append(discord.Embed(
                description=page_content, color=discord.Color.blurple()))

        server_roles_embed1 = server_roles_embeds[0]
        server_roles_embed1.title = "Blist Server Roles"
        server_roles_embed2 = server_roles_embeds[1]

        server_bot_link = "https://discord.com/oauth2/authorize?client_id=791415200175751171&scope=bot"
        faq_embed = discord.Embed(
            title="FAQ's", color=discord.Color.blurple(),
            description=f"""
**How did I get here?**
When logging in on the website, you grant us the ability to join guilds for you. Whenever you go to add a bot, you get added to the server."
\n**How do I level up / get XP?**
XP is earned by talking in all channel except the bots category in this server. It is awarded once per minute, with a random value of 1-10. Leveling up is determined from multiplying your level by 50. I.e. a person of level 5 needs 250 XP.
To check your xp and level, do the b!rank command or b!leaderboard for all.
\n**How do I add a bot?**
To add a bot, head over the https://blist.xyz/bot/add/.
\n**How long does the queue take?**
We try to get every bot done as fast as we can. Please take into consideration we have irl things to do sometimes.
\n**How do I add my server?**
Add our bot using [this]({server_bot_link} '{server_bot_link}') link. Then, go to your profile at [/user/me](https://blist.xyz/user/me), scroll, then click your server. Fill out the corresponding fields and click publish. Tada, your server is now on our list.
            """
        )

        channel = ctx.guild.get_channel(716717317320605736)
        all_info = await channel.fetch_message(723643619315023873)
        server_roles1 = await channel.fetch_message(723643619700899983)
        server_roles2 = await channel.fetch_message(723643620313268291)
        faqs = await channel.fetch_message(781643618091270173)

        await all_info.edit(embed=main_embed)
        await faqs.edit(embed=faq_embed)

        # just to be sure.
        try:
            await server_roles1.edit(embed=server_roles_embed1)
            await server_roles2.edit(embed=server_roles_embed2)
        except Exception as e:
            await ctx.send(f"{e}\nRoles embeds.")
            pass

        await ctx.send(f"Updated all embeds in {channel.mention}")

    @checks.main_guild_only()
    @commands.has_permissions(administrator=True)
    @commands.command()
    async def votesreset(self, ctx, *, message=None):
        top_bots = await self.bot.pool.fetch("SELECT * FROM main_site_bot ORDER BY monthly_votes DESC LIMIT 5")
        embed = discord.Embed(title=f"{datetime.datetime.utcnow().strftime('%B')} top 5 voted bots!",
                              color=discord.Color.blurple())
        for bot in top_bots:
            embed.add_field(
                name=bot['name'], value=f"Votes: {bot['monthly_votes']}", inline=False)
        await ctx.send(content=message or "", embed=embed)
        bots = await self.bot.pool.fetch("SELECT * FROM main_site_bot")
        for bot in bots:
            await self.bot.pool.execute("UPDATE main_site_bot SET monthly_votes = 0 WHERE id = $1", bot["id"])
        await ctx.send("Monthly votes reset!")

    @commands.has_permissions(administrator=True)
    @commands.command()
    async def avatars(self, ctx):
        await ctx.send("Doing Avatars")
        bots = await self.bot.pool.fetch("SELECT * FROM main_site_bot WHERE approved = True")
        users = await self.bot.pool.fetch("SELECT * FROM main_site_user")

        for bot in bots:
            bot_user = self.bot.main_guild.get_member(bot['id'])
            try:
                await self.bot.pool.execute("UPDATE main_site_bot SET avatar_hash = $1 WHERE id = $2", bot_user.avatar, bot_user.id)
            except:
                pass

        for user in users:
            user_user = self.bot.main_guild.get_member(user['userid'])
            try:
                await self.bot.pool.execute("UPDATE main_site_bot SET avatar_hash = $1 WHERE id = $2", user_user.avatar, user_user.id)
            except:
                pass

        await ctx.send("Done")

    @commands.has_role(779817680488103956)
    @commands.command()
    async def tweet(self, ctx, *, message):
        self.bot.twitter_api.update_status(
            f"{message} \n\n- {ctx.author.name}")
        await ctx.send("Done")


def setup(bot):
    bot.add_cog(Admin(bot))