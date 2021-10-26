from discord.ext.commands import FlagConverter, flag
from typing import Tuple, Literal


class BaseFlagConverter(FlagConverter, case_sensitive=True):  # type: ignore
    """
    Base flag converter for the bot.
    """

    pass


__all__: Tuple[str, ...] = ("RestartFlags", "ChangeVotesFlags")


class RestartFlags(BaseFlagConverter):
    bot: bool = flag(default=False, aliases=["b"])
    site: bool = flag(default=False, aliases=["s"])
    all: bool = flag(default=False, aliases=["a"])


class ChangeVotesFlags(BaseFlagConverter):
    amount: str
    _type: Literal["month", "total", "both"] = flag(name="type", aliases=["t"], default="both")
    _list: Literal["bot", "server"] = flag(name="list", default="bot", aliases=["l"])
    _id = int = flag(name="id")


class DMFlags(BaseFlagConverter):
    message: str = flag(aliases=["m"])
    title: str = flag(default="Official Warning", aliases=["t"])
    footer: str = flag(default="blist.xyz", aliases=["f"])
    signature: str = flag(default=None, aliases=["s"])


class TranslateFlags(BaseFlagConverter):
    message: str = flag(aliases=["m"])
    to: str = flag(default="en", aliases=["l"])
    _from: str = flag(name="from", default="(auto)", aliases=["f"])
