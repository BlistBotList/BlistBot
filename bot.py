import argparse
import asyncio
import datetime
import os
from typing import Union

import aiohttp
import asyncpg
import discord
import tweepy
from discord.ext import commands

import config
from utils.help import CustomHelpCommand

extensions = [f"cogs.{f[:-3]}" for f in os.listdir("cogs") if f.endswith(".py") and not f.startswith("_")] + ["jishaku"]

parser = argparse.ArgumentParser()
parser.add_argument("-d", "--development", help="Run the bot in the development state", action="store_true")
args = parser.parse_args()

PRINT_LINE: str = "---------------------"


async def get_prefix(bot, message):
    return commands.when_mentioned_or(*(["b?", "B?"] if args.development else ["b!", "B!"]))(bot, message)


class Blist(commands.Bot):
    MAIN_GUILD_ID: int = 716445624517656727
    VERIFICATION_GUILD_ID: int = 734527161289015337

    def __init__(self):
        super().__init__(
            command_prefix=get_prefix,
            case_insensitive=True,
            max_messages=500,
            reconnect=True,
            help_command=CustomHelpCommand(command_attrs={"hidden": True}),
            intents=discord.Intents(
                members=True,
                emojis=True,
                messages=True,
                message_content=True,
                reactions=True,
                guilds=True,
                presences=True,
            ),
        )
        self.staff_roles = {
            716713561233031239,
            716713293330514041,
            716713498360545352,
            716713238955556965,
            716713266683969626,
        }

    @property
    def main_guild(self) -> Union[discord.Guild, discord.Object]:
        return self.get_guild(self.MAIN_GUILD_ID) or discord.Object(self.MAIN_GUILD_ID)

    @property
    def verification_guild(self) -> Union[discord.Guild, discord.Object]:
        return self.get_guild(self.VERIFICATION_GUILD_ID) or discord.Object(self.VERIFICATION_GUILD_ID)

    async def on_ready(self) -> None:
        print(PRINT_LINE, f"{self.user} is ready", PRINT_LINE, sep="\n")

    async def setup_hook(self) -> None:
        try:
            self.pool = await asyncpg.create_pool(config.db_url)
        except Exception as error:
            print("There was a problem connecting to the database")
            print(f"\n{error}")

        try:
            self.mod_pool = await asyncpg.create_pool(config.mod_db_url)
            with open("schema.sql", "r") as schema:
                await self.mod_pool.execute(schema.read())
        except Exception as error:
            print("There was a problem connecting to the mod database")
            print(f"\n{error}")

        self.session = aiohttp.ClientSession()
        approved_bots = await self.pool.fetchval(
            "SELECT COUNT(*) FROM main_site_bot WHERE approved = True AND denied = False"
        )
        users = await self.pool.fetchval("SELECT COUNT(*) FROM main_site_user")
        print(PRINT_LINE, f"{approved_bots} bots", PRINT_LINE, f"Watching {users} site users", PRINT_LINE, sep="\n")
        self.uptime = datetime.datetime.utcnow().strftime("%c")

        auth = tweepy.OAuthHandler(config.consumer_key, config.consumer_secret_key)
        auth.set_access_token(config.access_token, config.access_token_secret)
        self.twitter_api = tweepy.API(auth)

        for extension in extensions:
            await self.load_extension(extension)

    async def start(self):
        return await super().start(config.bot_token_dev if args.development else config.bot_token)

    async def close(self):
        try:
            await self.pool.close()
            await self.mod_pool.close()
        except AttributeError:
            pass

        await self.session.close()
        await super().close()


async def main() -> None:
    async with Blist() as bot:
        try:
            await bot.start()
        except KeyboardInterrupt:
            await bot.close()


if __name__ == "__main__":
    discord.utils.setup_logging()
    asyncio.run(main())
