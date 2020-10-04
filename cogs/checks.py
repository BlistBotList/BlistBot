from discord.ext import commands


def main_guild_only():
    async def predicate(ctx):
        if ctx.guild != ctx.bot.get_guild(716445624517656727):
            return False
        else:
            return True
    return commands.check(predicate)


def verification_guild_only():
    async def predicate(ctx):
        if ctx.guild != ctx.bot.get_guild(734527161289015337):
            return False
        else:
            return True
    return commands.check(predicate)