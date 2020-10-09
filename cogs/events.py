import re

import discord
from discord.ext import commands, tasks


class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.main_guild = self.bot.get_guild(716445624517656727)
        self.verification_guild = self.bot.get_guild(734527161289015337)
        self.check_join.start() # pylint: disable=no-member

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.guild == self.main_guild:
            if member.bot:
                role = member.guild.get_role(716684129453735936)
                await member.add_roles(role)

        if member.guild == self.verification_guild:
            if member.bot:
                bot_role = self.verification_guild.get_role(763187834219003934)
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
                
                bots = await self.bot.pool.fetch("SELECT * FROM main_site_bot WHERE id = $1", member.id)
                
                website = bots[0]['website'] or 'None'
                invite = bots[0]['invite_url'] or 'Default'
                blist_link = f"https://blist.xyz/bot/{member.id}/"
                prefix = bots[0]['prefix']
                tags = ', '.join([str(x) for x in bots[0]['tags']])
                added = bots[0]['joined'].strftime('%D')

                embed = discord.Embed(title=f"{member.name}#{member.discriminator}", description=f"""
                >>> Owner: ``{self.main_guild.get_member(bots[0]['main_owner'])}``
                Prefix: ``{prefix}``
                Tags: ``{tags}``
                Added: ``{added}``""")
                embed.add_field(name="**Links**", value=f"""
                >>> Privacy Policy: {bots[0]['privacy_policy_url'] if bots[0]['privacy_policy_url'] != '' else 'None'}
                Website: {website}
                Invite: {invite}
                Blist Link: {blist_link}""")
                embed.add_field(name="Short Description",value=bots[0]['short_description'], inline=False)
                embed.set_thumbnail(url=member.avatar_url)
                message = await channel.send(embed=embed)
                await message.pin()

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        if member.guild == self.verification_guild:
            if member.bot:
                category = discord.utils.find(lambda c: c.name == member.name, member.guild.categories)
                for channel in category.channels:
                    await channel.delete()
                await category.delete()

        if member.guild == self.main_guild:
            if member.bot:
                x = await self.bot.pool.fetch("SELECT * FROM main_site_bot WHERE id = $1", member.id)
                if x != []:
                    embed = discord.Embed(description = f"{member} has left the server and is listed on the site! Use `b!delete` to delete the bot", color = discord.Color.red())
                    await self.bot.get_channel(716727091818790952).send(embed = embed)
                    return
            if not member.bot:
                x = await self.bot.pool.fetch("SELECT * FROM main_site_bot WHERE main_owner = $1", member.id)
                if x != []:
                    for y in x:
                        bots = " \n".join([f"{y['name']} (<@{y['id']}>)"])
                        embed = discord.Embed(description = f"{member} left the server and has {len(x)} bot(s) listed: \n\n{bots} \n\nUse the `b!delete` command to delete the bot", color = discord.Color.red())
                        await self.bot.get_channel(716727091818790952).send(embed = embed)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.channel.id == 743127622053003364:
            if message.attachments != [] or re.findall(r"<(?P<animated>a?):(?P<name>[a-zA-Z0-9_]{2,32}):(?P<id>[0-9]{18,22})>", message.content) != []:
                await message.add_reaction("✔️")
                await message.add_reaction("❌")
                
    @tasks.loop(minutes=30)
    async def check_join(self):
        bots = await self.bot.pool.fetch("SELECT * FROM main_site_bot WHERE approved = True")
        channel = self.main_guild.get_channel(716727091818790952)
        for bot in bots:
            b = self.main_guild.get_member(bot['id'])
            if b is None:
                embed = discord.Embed(color=discord.Color.red(), title="Bot Not Joined!!!!")
                embed.add_field(name = bot['name'], value=f"[Invite](https://discordapp.com/api/oauth2/authorize?client_id={bot['id']}&guild_id=716445624517656727&scope=bot&disable_guild_select=true)")
                await channel.send(embed=embed)

def setup(bot):
    bot.add_cog(Events(bot))