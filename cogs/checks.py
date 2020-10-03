from discord.ext import commands


def main_guild_only():
    async def predicate(ctx):
        if ctx.guild != ctx.bot.get_guild(716445624517656727):
            await ctx.send("This command can only be ran in the main guild!")
            return False
        else:
            return True
    return commands.check(predicate)


def verification_guild_only():
    async def predicate(ctx):
        if ctx.guild != ctx.bot.get_guild(734527161289015337):
            await ctx.send("This command can only be ran in the verification guild!")
            return False
        else:
            return True
    return commands.check(predicate)