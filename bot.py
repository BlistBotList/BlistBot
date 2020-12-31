import argparse
import asyncio
import datetime
import os

import aiohttp
import asyncpg
import discord
import tweepy
from discord.ext import commands

import config
from cogs.help import CustomHelpCommand

extensions = ["jishaku"]

for f in os.listdir("cogs"):
    if f.endswith(".py") and f"cogs.{f[:-3]}" not in extensions:
        extensions.append("cogs." + f[:-3])

parser = argparse.ArgumentParser()
parser.add_argument("-d", "--development",
                    help="Run the bot in the development state", action="store_true")
args = parser.parse_args()


class Blist(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=["b?", "B?"] if args.development else ["b!", "B!"],
            case_insensitive=True,
            max_messages=500,
            reconnect=True,
            help_command=CustomHelpCommand(command_attrs={'hidden': True}),
            intents=discord.Intents(
                members=True, emojis=True, messages=True, reactions=True, guilds=True, presences=True)
        )
        self.staff_roles = {716713561233031239, 716713293330514041,
                            716713498360545352, 716713238955556965, 716713266683969626}

    async def on_ready(self):
        self.session = aiohttp.ClientSession()
        approved_bots = await self.pool.fetchval(
            "SELECT COUNT(*) FROM main_site_bot WHERE approved = True AND denied = False")
        users = await self.pool.fetchval("SELECT COUNT(*) FROM main_site_user")
        print("---------------------")
        print(f"{self.user} is ready")
        print("---------------------")
        print(f"{approved_bots} bots")
        print("---------------------")
        print(f"Watching {users} users")
        print("---------------------")
        self.uptime = datetime.datetime.utcnow().strftime("%c")

    async def on_connect(self):
        auth = tweepy.OAuthHandler(
            config.consumer_key, config.consumer_secret_key)
        auth.set_access_token(config.access_token, config.access_token_secret)
        self.twitter_api = tweepy.API(auth)

        self.main_guild = self.get_guild(716445624517656727)
        self.verification_guild = self.get_guild(734527161289015337)
        if not hasattr(self, "pool"):
            try:
                self.pool = await asyncpg.create_pool(config.db_url)
            except Exception as error:
                print("There was a problem connecting to the database")
                print(f"\n{error}")
        if not hasattr(self, "mod_pool"):
            try:
                self.mod_pool = await asyncpg.create_pool(config.mod_db_url)
                with open("schema.sql", "r") as schema:
                    await self.mod_pool.execute(schema.read())
            except Exception as error:
                print("There was a problem connecting to the mod database")
                print(f"\n{error}")

        extensions.remove("cogs.checks")
        extensions.remove("cogs.time")
        for extension in extensions:
            self.load_extension(extension)

    async def start(self):
        await self.login(config.bot_token_dev if args.development else config.bot_token)
        try:
            await self.connect()
        except KeyboardInterrupt:
            await self.stop()

    async def stop(self):
        await self.pool.close()
        await super().logout()
        await self.session.close()

    def run(self):
        loop = self.loop
        try:
            loop.run_until_complete(self.start())
        except KeyboardInterrupt:
            loop.run_until_complete(self.stop())


if __name__ == "__main__":
    Blist().run()