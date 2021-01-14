import discord
from discord.ext import commands
from jishaku.help_command import MinimalEmbedPaginatorHelp
from jishaku.paginators import PaginatorEmbedInterface


class CustomPaginatorEmbedInterface(PaginatorEmbedInterface):

    @property
    def send_kwargs(self) -> dict:
        display_page = self.display_page
        self._embed.title = self.bot.user.name
        self._embed.description = self.pages[display_page]
        self._embed.color = discord.Colour.blurple()
        self._embed.set_footer(text=str(self.owner.name), icon_url=self.owner.avatar_url_as(static_format="png"))
        # self._embed.set_footer(text = f'Page {display_page + 1}/{self.page_count}')
        return {'embed': self._embed}


class CustomHelpCommand(MinimalEmbedPaginatorHelp):

    async def send_pages(self):
        destination = self.get_destination()
        interface = CustomPaginatorEmbedInterface(
            self.context.bot, self.paginator, owner=self.context.author)
        await interface.send_to(destination)

    def add_bot_commands_formatting(self, _commands, heading):
        if commands:
            # U+2022 Middle Dot
            joined = ', '.join(f"`{c.name}`" for c in _commands)
            self.paginator.add_line(f"> **{heading}**")
            self.paginator.add_line(f"{joined}\n")

    def get_opening_note(self):
        """Returns help command's opening note. This is mainly useful to override for i18n purposes.

        The default implementation returns ::

            Use `{prefix}{command_name} [command]` for more info on a command.
            You can also use `{prefix}{command_name} [category]` for more info on a category.

        """
        return f"To get help on a specific command or category do `{self.clean_prefix}help [command or category name]`"


class Help(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.old_help_command = MinimalEmbedPaginatorHelp(
            command_attrs={'hidden': True})

    def cog_unload(self):
        self.bot.help_command = self.old_help_command


def setup(bot):
    bot.add_cog(Help(bot))