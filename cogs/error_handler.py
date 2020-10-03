import discord
from discord.ext import commands


class ErrorHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return
        if isinstance(error, commands.CheckFailure):
            return

        errors = {
            commands.MissingPermissions: {"msg": "You do not have permissions to run this command."},
            discord.HTTPException: {"msg": "There was an error connecting to Discord. Please try again."},
            commands.CommandInvokeError: {"msg": "There was an issue running the command."},
            commands.NotOwner: {"msg": "You are not the owner."},
        }

        if not isinstance(error, (commands.MissingRequiredArgument)):
            ets = errors.get(error.__class__)
            if ets == None:
                ets = {}
                ets["msg"] = "[ERROR]"

            em = discord.Embed(
                description=ets["msg"].replace("[ERROR]", f"{error}"))

            try:
                await ctx.send(embed=em)
            except discord.Forbidden:
                pass

        elif isinstance(error, commands.MissingRequiredArgument):
            em = discord.Embed(
                description=f"`{str(error.param).partition(':')[0]}` is a required argument!")
            await ctx.send(embed=em)


def setup(bot):
    bot.add_cog(ErrorHandler(bot))