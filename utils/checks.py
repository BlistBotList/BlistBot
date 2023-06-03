from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from discord.ext import commands

if TYPE_CHECKING:
    from bot import Blist


class WrongGuild(commands.CheckFailure):
    def __init__(self, ctx: commands.Context["Blist"], guild_id: int, message: Optional[str] = None):
        self.guild_id: int = guild_id
        obj = ctx.bot.get_guild(guild_id)
        guild = f"{obj.name} ({obj.id})" if obj else str(guild_id)
        super().__init__(message or f"That command can only be used in {guild} guild.")


def main_guild_only():
    async def predicate(ctx: commands.Context["Blist"]):
        if ctx.guild and ctx.guild.id != ctx.bot.main_guild.id:
            raise WrongGuild(ctx, ctx.bot.main_guild.id)
        return True

    return commands.check(predicate)


def verification_guild_only():
    async def predicate(ctx: commands.Context["Blist"]):
        if ctx.guild and ctx.guild.id != ctx.bot.verification_guild.id:
            raise WrongGuild(ctx, ctx.bot.verification_guild.id)
        return True

    return commands.check(predicate)
