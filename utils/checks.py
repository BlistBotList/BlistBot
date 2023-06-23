from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import discord
from discord.ext import commands

from utils.constants import STAFF_ROLES

if TYPE_CHECKING:
    from bot import Blist


class WrongGuild(commands.CheckFailure):
    def __init__(self, ctx: commands.Context["Blist"], guild_id: int, message: Optional[str] = None):
        self.guild_id: int = guild_id
        obj = ctx.bot.get_guild(guild_id)
        guild = f"{obj.name} ({obj.id})" if obj else str(guild_id)
        super().__init__(message or f"That command can only be used in {guild} guild.")


class NotStaff(commands.CheckFailure):
    def __init__(self, message: Optional[str] = None):
        super().__init__(message or "You are not a staff member.")


class RankTooLow(commands.CheckFailure):
    def __init__(self, role: discord.Role, message: Optional[str] = None):
        self.role: discord.Role = role
        super().__init__(
            message
            or f"Your rank (role) is too low to use this command. You need to be a {role.name} or higher to use this command."
        )


def guild_only(guild_id: int):
    async def predicate(ctx: commands.Context["Blist"]):
        if not ctx.guild:
            raise commands.NoPrivateMessage()

        if ctx.guild.id != guild_id:
            raise WrongGuild(ctx, guild_id)

        return True

    return commands.check(predicate)


def staff_only(above_or_equal_role_id: Optional[int] = None):
    async def predicate(ctx: commands.Context["Blist"]):
        if not ctx.guild or not isinstance(ctx.author, discord.Member):
            raise commands.NoPrivateMessage()

        author = ctx.bot.main_guild.get_member(ctx.author.id)  # type: ignore
        if not author:
            raise commands.NoPrivateMessage()

        if not above_or_equal_role_id:
            if not any(author.get_role(role_id) for role_id in STAFF_ROLES):
                raise NotStaff()

            return True

        role = ctx.guild.get_role(above_or_equal_role_id)
        if not role:
            raise RuntimeError(f"Role with ID {above_or_equal_role_id} not found in {ctx.guild.name} ({ctx.guild.id})")

        if author.top_role < role:
            raise RankTooLow(role)

        return True

    return commands.check(predicate)
