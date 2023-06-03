from __future__ import annotations

from typing import Literal, Optional, Union

import discord
from discord.ext.commands import Flag, FlagConverter


class BlistFlags(FlagConverter, prefix="--", delimiter=" ", case_insensitive=True):
    pass


class RestartFlags(BlistFlags):
    """Flags for the restart command."""

    bot: bool = Flag(default=False, aliases=["b"], max_args=1)
    site: bool = Flag(default=False, aliases=["s"], max_args=1)


class ChangeVoteFlags(BlistFlags):
    """Flags for the changevote command."""

    object: Union[discord.Guild, discord.Member, discord.Object] = Flag(aliases=["o"], max_args=1)
    listing: Literal["bot", "server"] = Flag(default="bot", aliases=["l"], max_args=1)
    amount: int = Flag(default=1, aliases=["n"], max_args=1)
    add: bool = Flag(default=False, aliases=["a"], max_args=1)
    remove: bool = Flag(default=False, aliases=["r"], max_args=1)
    monthly: bool = Flag(default=False, aliases=["m"], max_args=1)
    total: bool = Flag(default=False, aliases=["t"], max_args=1)


class CustomRankcardFlags(BlistFlags):
    background: str = Flag(default=None, aliases=["bg"], max_args=1)
    xp_bar: str = Flag(default=None, aliases=["xp"], max_args=1)
    border_color: str = Flag(default=None, aliases=["border"], max_args=1)


class BotAnnouncementCreateFlags(BlistFlags):
    bot: Union[discord.Member, discord.Object] = Flag(aliases=["b"], max_args=1)
    text: str = Flag(aliases=["t"], max_args=1)
    pinned: bool = Flag(default=False, aliases=["p"], max_args=1)


class TranslateFlags(BlistFlags):
    text: str = Flag(aliases=["t"], max_args=1)
    target: str = Flag(aliases=["to"], max_args=1, default="en")
    source: str = Flag(aliases=["from"], max_args=1, default="auto")


class DMCommandFlags(BlistFlags):
    message: str = Flag(aliases=["msg"], max_args=1)
    member: discord.Member = Flag(aliases=["m"], max_args=1)
    title: str = Flag(aliases=["t"], max_args=1, default="Official Warning")
    footer: str = Flag(aliases=["f"], max_args=1, default="blist.xyz")
    signature: str = Flag(aliases=["s"], max_args=1, default=None)


class BotAnnouncementViewFlags(BlistFlags):
    bot: Optional[Union[discord.Member, discord.Object]] = Flag(aliases=["b"], max_args=1, default=None)
    _id: Optional[int] = Flag(name="id", attribute="name", aliases=["i"], max_args=1, default=None)
    oldest: bool = Flag(default=False, aliases=["old", "o"], max_args=1)
    _all: bool = Flag(name="all", attribute="all", default=False, aliases=["a"], max_args=1)
