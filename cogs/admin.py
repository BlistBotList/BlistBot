import asyncio
import datetime
import os
import re

import config
import discord
from discord.ext import commands
import country_converter as coco
from textwrap import dedent as wrap

from . import checks  # pylint: disable=relative-beyond-top-level


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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

        ranks = ["Senior Administrator", "Administrator", "Senior Website Moderator", "Website Moderator"]
        if rank not in ranks:
            return await ctx.send(f"{rank} is not a valid rank")

        query = await self.bot.mod_pool.fetch("SELECT * FROM staff WHERE userid = $1", member.id)
        if not query:
            return await ctx.send("This user is not in the database")

        await self.bot.mod_pool.execute("UPDATE staff SET rank = $1 WHERE userid = $2", rank, member.id)
        await ctx.send("Done")

    @commands.has_permissions(administrator = True)
    @commands.command()
    async def add(self, ctx, member: discord.Member, level):
        levels = ["bug_hunter", "developer", "administrator", "staff"]
        if level.lower() not in levels:
            await ctx.send(f"That's not a valid option, valid options are {', '.join(levels)}")
        await self.bot.pool.execute(f"UPDATE main_site_user SET {level} = True WHERE userid = $1", member.id)
        await ctx.send(f"Added {member} as {level}")

    @commands.has_permissions(administrator = True)
    @commands.command()
    async def remove(self, ctx, member: discord.Member, level: str):
        levels = ["bug_hunter", "developer", "administrator", "staff"]
        if level.lower() not in levels:
            await ctx.send(f"That's not a valid option, valid options are {', '.join(levels)}")
        await self.bot.pool.execute(f"UPDATE main_site_user SET {level} = False WHERE userid = $1", member.id)
        await ctx.send(f"Removed {member} from {level}")

    @checks.main_guild_only()
    @commands.has_permissions(administrator = True)
    @commands.group(invoke_without_command = True)
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
        embed = discord.Embed(description = f"Certified {bot.name}", color = discord.Color.blurple())
        await ctx.send(embed = embed)

        owner = ctx.guild.get_member(is_waiting)
        em = discord.Embed(description = f"``{bot.name}`` by ``{owner}`` was certified",
                           color = discord.Color.blurple())

        await self.bot.pool.execute("UPDATE main_site_user SET certified_developer = True WHERE userid = $1", owner.id)
        await self.bot.get_channel(716446098859884625).send(embed = em)
        certified_role = ctx.guild.get_role(716684142766456832)
        certified_dev_role = ctx.guild.get_role(716724317207003206)
        await owner.add_roles(certified_dev_role)
        await bot.add_roles(certified_role)

    @checks.main_guild_only()
    @commands.has_permissions(administrator = True)
    @certify.command()
    async def decline(self, ctx, bot: discord.Member, *, reason):
        if not bot.bot:
            embed = discord.Embed(description = f"❌ That is not a bot.", color = discord.Colour.red())
            await ctx.send(embed = embed)
            return

        is_waiting = await self.bot.pool.fetchval(
            "SELECT main_owner FROM main_site_bot WHERE awaiting_certification = True AND id = $1", bot.id)
        if not is_waiting:
            await ctx.send("That bot is not awaiting certification.")
            return

        await self.bot.pool.execute("UPDATE main_site_bot SET awaiting_certification = False WHERE id = $1", bot.id)
        await ctx.send(f"Denied certification for {bot.name}")
        em = discord.Embed(
            description = f"``{bot.name}`` by ``{ctx.guild.get_member(is_waiting)}`` was denied for certification for: \n```{reason}```",
            color = discord.Color.blurple())
        await self.bot.get_channel(716446098859884625).send(embed = em)

    @commands.has_permissions(administrator=True)
    @commands.command()
    async def poll(self, ctx, poll, image=None):
        embed = discord.Embed(title="**New Poll**:", description=poll, color=discord.Color.blurple())
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
                url = "https://api.cloudflare.com/client/v4/zones/47697d23bd0d042fd63573cc9030177d/purge_cache/",
                headers = headers, json = json) as x:
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
            stdout = asyncio.subprocess.PIPE,
            stderr = asyncio.subprocess.PIPE
        )

        try:
            com = await asyncio.wait_for(process.communicate(), timeout = 5)
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
                    embed = discord.Embed(title = f"There was an issue pulling from GitHub",
                                          description = f"\n```{e}```\n", color = discord.Color.red())
                    await ctx.send(embed = embed)
                    return

            if not updated:
                embed = discord.Embed(
                    title = f"No cogs were updated.", color = discord.Color.red())
                await ctx.send(embed = embed)
            else:
                embed = discord.Embed(
                    title = f"Updated cogs: " + ", ".join([f"`{text}`" for text in updated]),
                    color = discord.Color.blurple())
                await ctx.send(embed = embed)
        else:
            embed = discord.Embed(
                title = f"No cogs were updated.", color = discord.Color.red())
            await ctx.send(embed = embed)

    @commands.has_permissions(administrator = True)
    @commands.command()
    async def blacklist(self, ctx, userid: int, *, reason):
        check = await self.bot.pool.fetch(f"SELECT * FROM blacklisted WHERE userid = {userid}")
        if not check or check == []:
            await self.bot.pool.execute("INSERT INTO blacklisted VALUES ($1, $2)", userid, reason)
            await ctx.send(f"Blacklisted ``{userid}`` for: \n```{reason}```")
        else:
            await self.bot.pool.execute("DELETE FROM blacklisted WHERE userid = $1", userid)
            await ctx.send(f"Un-blacklisted ``{userid}`` for reason: \n```{reason}```")

    @checks.main_guild_only()
    @commands.has_permissions(administrator = True)
    @commands.command()
    async def staff_embed(self, ctx):
        all_staff = {
            "Senior Administrators": [
                f"{ctx.guild.get_member(679118121943957504).mention} :flag_us:"
            ],
            "Administrators": [
                f"{ctx.guild.get_member(712737377524777001).mention} :flag_us:"
            ],
            "Senior Moderators": [
                f"{ctx.guild.get_member(150665783268212746).mention} :flag_nl:",
                f"{ctx.guild.get_member(670684162113667092).mention} :flag_se:"
            ],
            "Moderators": [
                f"{ctx.guild.get_member(296044953576931328).mention} :flag_au:",
                f"{ctx.guild.get_member(664242899105480715).mention} :flag_au:",
                f"{ctx.guild.get_member(691994304885030972).mention} :flag_gb:",
                f"{ctx.guild.get_member(259649217255964672).mention} :flag_gb:",
                
            ]
        }
        embed = discord.Embed(color = discord.Color.blurple(), title = "Staff")
        people = list(all_staff.items())
        embed.add_field(name = f"> {people[0][0]}", value = "\n".join(people[0][1]), inline = False)
        embed.add_field(name = f"> {people[1][0]}", value = "\n".join(people[1][1]), inline = False)
        embed.add_field(name = f"> {people[2][0]}", value = "\n".join(people[2][1]), inline = False)
        embed.add_field(name = f"> {people[3][0]}", value = "\n".join(people[3][1]), inline = False)
        channel = ctx.guild.get_channel(716823743644696586)
        message = await channel.fetch_message(723641541486182410)
        await message.edit(embed = embed)
        await ctx.send(f"Updated the staff embed in {message.channel.mention}")

    @checks.main_guild_only()
    @commands.has_permissions(administrator = True)
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

        assignable_roles_channel = ctx.guild.get_channel(716733254308462702).mention
        server_roles_dict = {
            716722789234638860: "This is for people that report bugs to help improve the site. Gained by reporting bugs, no specific amount.",  # Bug Hunter
            716722845773725806: "This is for people that help improve the site by suggesting things and pring on the public [GitHub repositories](https://github.com/BlistBotList)",  # Community Contributor
            716713293330514041: "First Staff Tier",  # Website Moderator
            716713498360545352: "Second Staff Tier",  # Senior Website Moderator
            716713238955556965: "Third Staff Tier",  # Administrator
            716713266683969626: "Fourth Staff Tier",  # Senior Adminstrator
            716713561233031239: "All staff members have this role. You can [apply here](https://forms.gle/4X8cm1Ce58FR2f3P9)",  # Staff
            716713204159479919: "Site owner & Creator",  # Founder
            716723291011678319: f"This is for if you want to get pinged for updates related to the site. Get it from {assignable_roles_channel}",  # Updates
            716723357336338482: f"This is for if you want access to a channel where you can play with NSFW bots/commands. Get it from {assignable_roles_channel}",  # NSFW
            716723257663029372: f"This is for if you want to get pinged for announcements related to the site or this server. Get it from {assignable_roles_channel}",  # Announcements
            750771398636601354: f"This is for if you want to get pinged for polls related to the site and this server. Get it from {assignable_roles_channel}",  # Polls
            716732766796120156: "Everyone human that joins gets this.",  # Member
            716684805286133840: "Everyone with a bot on the site has this. [Add a bot](https://blist.xyz/bot/add/) to the site to get it.",  # (bot) Developer
            716722689921908756: f"Website developer. DM {ctx.guild.get_member(679118121943957504).mention} if you know django, js and html (Must know all 3) and want to help code the site back or front.",  # (other) Developer
            716724317207003206: "This is for people that have a certified bot. Get it by applying for certification [here](https://blist.xyz/certification/)",  # Certified Developer
            716726167713087589: "Bots with this role help with things around this server like mod related things.",  # Server Bot
            716684129453735936: "This is a role that bots get when they get approved and added to this server.",  # Bot
            716684142766456832: "This is for bots that are certified on the site.",  # Certified Bot
            764686546179325972: "This is for bots with a common prefix."  # Common Prefix
        }

        server_rules_embed = discord.Embed(title = "Blist Server Rules", color = discord.Color.blurple(),
                                           description = "")
        for num, rule in enumerate(server_rules_list, start = 1):
            server_rules_embed.description += f"\n**{num}.** {rule}"
        bot_rules_embed = discord.Embed(title = "Blist Bot Rules/Requirements", color = discord.Color.blurple(),
                                        description = "")
        for num, rule in enumerate(bot_rules_list, start = 1):
            bot_rules_embed.description += f"\n**{num}.** {rule}"

        server_roles_list = []
        guild_role_ids = [x.id for x in ctx.guild.roles]
        ordered_server_roles_list = sorted(server_roles_dict.keys(), key = guild_role_ids.index, reverse = True) # put in order as in server.
        for role_id in ordered_server_roles_list:
            server_roles_list.append(f"{ctx.guild.get_role(role_id).mention} - {server_roles_dict[role_id]}")
        server_roles_embed = discord.Embed(title = "Blist Server Roles", color = discord.Color.blurple(),
                                           description = "\n".join(server_rules_list))
        links_embed = discord.Embed(
            title = "Links", color = discord.Color.blurple(),
            description = wrap(
                """
                [Site](https://blist.xyz)
                [API](https://blist.xyz/api/)
                [API Docs](https://docs.blist.xyz/)
                [Certification Info](https://blist.xyz/certification/)
                """
            )
        )
        faq_embed = discord.Embed(
            title = "FAQ's", color = discord.Color.blurple(),
            description = wrap(
                """
                **How did I get here?**
                When logging in on the website, your grant us the ability to join guilds for you. Whenever you go to add a bot, you get added to the server.
                \n**How do I add a bot?**
                To add a bot, head over the https://blist.xyz/bot/add/.
                \n**How long does the queue take?**
                We try to get every bot done as fast as we can. Please take into consideration we have irl things to do sometimes.
                """
            )
        )

        channel = ctx.guild.get_channel(716717317320605736)
        server_rules = await channel.fetch_message(723643619315023873)
        bot_rules = await channel.fetch_message(723643619700899983)
        server_roles = await channel.fetch_message(723643620313268291)
        links = await channel.fetch_message(723643620946870272)
        faqs = await channel.fetch_message(776576250567196672)

        await server_rules.edit(embed = server_rules_embed)
        await bot_rules.edit(embed = bot_rules_embed)
        await server_roles.edit(embed = server_roles_embed)
        await links.edit(embed = links_embed)
        await faqs.edit(embed = faq_embed)
        await ctx.send(f"Updated all embeds in {channel.mention}")

    @checks.main_guild_only()
    @commands.has_permissions(administrator = True)
    @commands.command()
    async def votesreset(self, ctx, *, message = None):
        top_bots = await self.bot.pool.fetch("SELECT * FROM main_site_bot ORDER BY monthly_votes DESC LIMIT 5")
        embed = discord.Embed(title = f"{datetime.datetime.utcnow().strftime('%B')} top 5 voted bots!",
                              color = discord.Color.blurple())
        for bot in top_bots:
            embed.add_field(name = bot['name'], value = f"Votes: {bot['monthly_votes']}", inline = False)
        await ctx.send(content = message or "", embed = embed)
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
            if not bot_user:
                break
            url = f"https://cdn.discordapp.com/avatars/{bot['id']}/{bot['avatar_hash']}.webp?size=1024"
            async with self.bot.session.head(url=url) as resp:
                if resp.status == 404:
                    await self.bot.pool.execute("UPDATE main_site_bot SET avatar_hash = $1 WHERE id = $2", bot_user.avatar, bot_user.id)

        for user in users:
            user_user = self.bot.main_guild.get_member(user['userid'])
            if not user_user:
                break
            url = f"https://cdn.discordapp.com/avatars/{user['userid']}/{user['avatar_hash']}.webp?size=1024"
            async with self.bot.session.head(url=url) as resp:
                if resp.status == 404:
                    await self.bot.pool.execute("UPDATE main_site_bot SET avatar_hash = $1 WHERE id = $2", user_user.avatar, user_user.id)
        
        await ctx.send("Done")

def setup(bot):
    bot.add_cog(Admin(bot))