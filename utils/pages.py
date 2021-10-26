# subclass menu to add numbers button.
import asyncio
import discord
from discord.ext import menus


class MainMenu(menus.MenuPages):
    def __init__(self, source, **kwargs):
        super().__init__(source=source, check_embeds=True, **kwargs)

    @menus.button("\N{INPUT SYMBOL FOR NUMBERS}", position=menus.Last(1.5))
    async def numbered_page(self, payload):
        """lets you type a page number to go to"""
        channel = self.message.channel
        author_id = payload.user_id
        to_delete = [await channel.send("What page do you want to go to?")]

        def message_check(m):
            return m.author.id == author_id and channel == m.channel and m.content.isdigit()

        try:
            msg = await self.bot.wait_for("message", check=message_check, timeout=30.0)
        except asyncio.TimeoutError:
            to_delete.append(await channel.send("Took too long."))
            await asyncio.sleep(5)
        else:
            page = int(msg.content)
            to_delete.append(msg)
            await self.show_checked_page(page - 1)

        try:
            await channel.delete_messages(to_delete)
        except Exception:
            pass


class LeaderboardPage(menus.ListPageSource):
    def __init__(self, entries, **kwargs):
        super().__init__(entries, **kwargs)

    async def format_page(self, menu, entry):
        em = discord.Embed(
            title="User Leaderboard | Pagination", color=discord.Color.blurple(), url="https://blist.xyz/leaderboard/"
        )
        em.set_thumbnail(url=str(menu.ctx.guild.icon.url))
        em.set_footer(text=f"Page: {menu.current_page + 1} / {self.get_max_pages()}")
        for name, value in entry:
            em.add_field(name=name, value=value, inline=False)

        return em


class AnnouncementPage(menus.ListPageSource):
    def __init__(self, entries, **kwargs):
        super().__init__(entries, **kwargs)

    async def format_page(self, menu, entry):
        announcement, announcement_content, creator, bot = entry
        announcement_id = announcement.id or "-"
        total = f"[{len(self.entries)}] " if len(self.entries) >= 2 else ""
        em = discord.Embed(
            title=f"{total}{'Announcements' if len(self.entries) >= 2 else 'Announcement'} for {str(bot)}",
            color=discord.Color.blurple(),
            url=f"https://blist.xyz/bot/{bot.id}/announcements",
            description=f"{announcement.created_at.strftime('%b. %d, %Y, %I:%M %p')}\n\n{announcement_content}\n\n"
            f"**Pinned?**: {announcement.is_pinned}\n**ID**: {announcement_id}",
        )
        em.set_thumbnail(url=str(bot.display_avatar.url))
        em.set_footer(text=f"Page: {menu.current_page + 1} / {self.get_max_pages()}")
        em.set_author(name=str(creator), icon_url=str(creator.display_avatar.url))
        return em
