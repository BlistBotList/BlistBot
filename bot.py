import argparse
import datetime
import os

import asyncpg
import config
import discord
from discord.ext import commands
from jishaku import help_command

extensions = ["jishaku"]

for f in os.listdir("cogs"):
    if f.endswith(".py") and f"cogs.{f[:-3]}" not in extensions:
        extensions.append("cogs." + f[:-3])

parser = argparse.ArgumentParser()
parser.add_argument("-d", "--development", help = "Run the bot in the development state", action = "store_true")
args = parser.parse_args()


class Blist(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix = ["b?", "B?"] if args.development else ["b!", "B!"],
            case_insensitive = True,
            max_messages = 500,
            reconnect = True,
            help_command = help_command.MinimalEmbedPaginatorHelp(),
            intents = discord.Intents(members = True, emojis = True, messages = True, reactions = True, guilds = True)
        )

    async def on_ready(self):
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
        if not hasattr(self, "pool"):
            try:
                self.pool = await asyncpg.create_pool(config.db_url)
            except Exception as error:
                print("There was a problem connecting to the database")
                print(f"\n{error}")

        extensions.remove("cogs.checks")
        extensions.remove("cogs.config")
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

    def run(self):
        loop = self.loop
        try:
            loop.run_until_complete(self.start())
        except KeyboardInterrupt:
            loop.run_until_complete(self.stop())


if __name__ == "__main__":
    Blist().run()
