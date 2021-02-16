from __future__ import annotations
from datetime import datetime
import asyncpg
import typing
from markdownify import markdownify as md


#def get_avatar(user_id: int, av_hash: str) -> str:
    #av_format = "png"
    #if av_hash.startswith("a_"):
        #av_format = "gif"
    #return f"https://cdn.discordapp.com/avatars/{user_id}/{av_hash}.{av_format}?size=1024"

async def is_bot_on_site(ctx, bot_id: int) -> bool:
    check_bot = await ctx.bot.pool.fetchrow("SELECT * FROM main_site_bot WHERE id = $1", bot_id)
    if not check_bot:
        return False
    return True

async def _get_unique_id(ctx, table_type: str, bot_user_id: int) -> typing.Optional[int]:
    queries = {
        "BOT": "SELECT unique_id FROM main_site_bot WHERE id = $1",
        "USER": "SELECT unique_id FROM main_site_user WHERE id = $1"
    }
    return await ctx.bot.pool.fetchval(queries[table_type], int(bot_user_id))


async def _from_unique_id(ctx, table_type: str, unique_id: int) -> typing.Union[Bot, Author, None]:
    queries = {
        "BOT": "SELECT username, id, avatar_url, discriminator FROM main_site_bot WHERE unique_id = $1",
        "USER": "SELECT username, id, avatar_url, discriminator FROM main_site_user WHERE unique_id = $1"
    }
    fetched = await ctx.bot.pool.fetchrow(queries[table_type], int(unique_id))
    if table_type == "BOT":
        return Bot(fetched)
    elif table_type == "USER":
        return Author(fetched)
    else:
        return None

class Author:
    def __init__(self, data: dict) -> None:
        self.name: str = data.get('username', None)
        self.id: int = data.get('id', None)
        self.discriminator: int = data.get('discriminator', None)
        self.avatar_url: str = data.get('avatar_url', None)

    def __str__(self) -> str:
        return f"{self.name}#{self.discriminator}"

    def __eq__(self, other) -> bool:
        return isinstance(other, Author) and self.id == other.id

class Bot:
    def __init__(self, data: dict) -> None:
        self.name: str = data.get('username', None)
        self.id: int = data.get('id', None)
        self.discriminator: int = data.get('discriminator', None)
        self.avatar_url: str = data.get('avatar_url', None)

    def __str__(self) -> str:
        return f"{self.name}#{self.discriminator}"

    def __eq__(self, other) -> bool:
        return isinstance(other, Bot) and self.id == other.id


class Announcement:

    __slots__ = ("content", "created_at", "is_pinned", "id", "bot_id", "author_id")

    def __init__(self, data: dict) -> None:
        self.content: str = str(md(str(data.get('announcement', None)))).strip()
        self.created_at: datetime = data.get('time', None)
        self.is_pinned: bool = data.get('pinned', None)
        self.id: int = data.get('unique_id', None)
        self.bot_id: int = data.get('bot_id', None)
        self.author_id: int = data.get('creator_id', None)

    def __str__(self) -> str:
        return str(self.content) if self.content else ""

    def __eq__(self, other) -> bool:
        return isinstance(other, Announcement) and self.id == other.id

    async def get_author_object(self, ctx) -> typing.Optional[Author]:
        """ Returns an AnnouncementCreator object. """
        return await _from_unique_id(ctx, "USER", self.author_id)

    async def get_bot_object(self, ctx) -> typing.Optional[Bot]:
        """ Returns an AnnouncementBot object. """
        return await _from_unique_id(ctx, "BOT", self.bot_id)

    @classmethod
    async def insert(cls, ctx, announcement: str, bot_id: int, pinned: bool = False) -> typing.Union[Announcement, str]:
        """ Insert the announcement in the db. This will return an Announcement object but with the id being None,
            if successful, else, will return the error.
        """
        announcement_query = "INSERT INTO main_site_announcement (bot_id, creator_id, announcement, time, pinned) VALUES ($1, $2, $3, $4, $5) RETURNING *"
        bot_id = await _get_unique_id(ctx, "BOT", bot_id)
        author_id = await _get_unique_id(ctx, "USER", ctx.author.id)
        time = datetime.utcnow()
        try:
            return_columns = await ctx.bot.pool.fetchrow(announcement_query, bot_id, author_id, announcement, time, pinned)
            return cls(dict(return_columns))
        except Exception as err:
            return str(err)

    @classmethod
    async def from_unique_id(cls, ctx, unique_id: int) -> typing.Optional[Announcement]:
        """ Gets an announcement via the unique_id and returns an Announement object,
            if successful, else, will return None.
        """
        announcement_fetched = await ctx.bot.pool.fetchrow("SELECT * FROM main_site_announcement WHERE unique_id = $1", int(unique_id))
        if not announcement_fetched:
            return None
        return cls(dict(announcement_fetched))

    @classmethod
    async def fetch_bot_announcements(cls, ctx, bot_id: int, limit = None, *, oldest: bool = False, is_unique: bool = False) -> typing.List[Announcement]:
        """
            Gets all bot announcements via their id and returns an Announement object if successful.

            bot_id: the bot's id.
            limit: the amount of announcements you want, None for all.
            oldest: sort announcement on oldest.
            is_unique: determine if the bot_id is the bot's unique ID instead of the user id.
        """
        bot_id = await _get_unique_id(ctx, "BOT", bot_id)
        if is_unique:
            bot_id = bot_id

        limit = limit or "ALL"
        query = "SELECT * FROM main_site_announcement WHERE bot_id = $1 ORDER BY time DESC LIMIT {}"
        if oldest:
            query = "SELECT * FROM main_site_announcement WHERE bot_id = $1 ORDER BY time ASC LIMIT {}"

        announcements_fetched = await ctx.bot.pool.fetch(query.format(limit), int(bot_id))
        returning_announcements = []
        for x in announcements_fetched:
            returning_announcements.append(cls(x))

        return returning_announcements

    async def delete(self, ctx, bot_id: int) -> typing.Optional[Announcement]:
        """ Deletes an announcement with check if bot id matches the announcement bot id. """
        return_announcement = self
        announcement_bot = await self.get_bot_object(ctx)
        if announcement_bot.id == bot_id:
            bot_id = await _get_unique_id(ctx, "BOT", bot_id)
            await ctx.bot.pool.execute("DELETE FROM main_site_announcement WHERE unique_id = $1 AND bot_id = $2", int(self.id), int(bot_id))
            return return_announcement

        return None

    async def edit(self, ctx, new_content: str, bot_id: int) -> typing.Optional[Announcement]:
        """ Edit an announcement with check if bot id matches the announcement bot id. """
        announcement_bot = await self.get_bot_object(ctx)
        if announcement_bot.id == bot_id:
            bot_id = await _get_unique_id(ctx, "BOT", bot_id)
            returned_columns = await ctx.bot.pool.fetchrow(
                "UPDATE main_site_announcement SET announcement = $1 WHERE unique_id = $2 AND bot_id = $3 RETURNING *",
                str(new_content), int(self.id), int(bot_id))
            return Announcement(returned_columns)

        return None

