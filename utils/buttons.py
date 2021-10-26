import discord
from discord.ext import commands
from typing import Optional, TYPE_CHECKING, Tuple

if TYPE_CHECKING:
    from bot import Blist

    BlistBot = Blist
else:
    BlistBot = commands.Bot


class BotInfoContext:
    def __init__(self, thread: discord.Thread):
        self.channel = thread

    async def send(self, *args, **kwargs):
        await self.channel.send(*args, **kwargs)


class ApprovalFeedbackView(discord.ui.View):
    def __init__(self, self_bot: BlistBot, bot: discord.Member):
        super().__init__(timeout = None)
        self.self_bot = self_bot
        self.bot = bot
        webhook_url = "https://discord.com/api/webhooks/873944696534220820/" \
                      "9KEMKZq1Zs7DQ2an42ezJr-Gx2SgBpeJqDLuajq-E0lL7VfTzszxHsgQjBEpJjIdD_ZZ"
        self.main_webhook = discord.Webhook.from_url(webhook_url, session = self_bot.session)

    async def disable_button(self, message: discord.Message) -> None:
        self.approval_button.style = discord.ButtonStyle.green
        self.approval_button.disabled = True
        await message.edit(view = self)

    def get_bot_id(self, category_id: int) -> Optional[int]:
        test_categories = self.self_bot.get_cog("Events").test_categories
        potential_bot_id = [k for k, v in test_categories.items() if v == category_id]
        if not potential_bot_id:
            return None

        bot_id = potential_bot_id[0]
        return bot_id

    async def get_bot_info(self, category_id: int) -> Optional[Tuple[discord.Member, commands.Command]]:
        bot_id = self.get_bot_id(category_id)
        if not bot_id:
            return None

        bot_owner_id = await self.self_bot.pool.fetchval("SELECT main_owner FROM main_site_bot WHERE id = $1", bot_id)
        if not bot_owner_id:
            return None

        bot_owner = self.self_bot.main_guild.get_member(bot_owner_id)
        if not bot_owner:
            return None

        bot_info_command = self.self_bot.get_command("botinfo")

        return bot_owner, bot_info_command

    async def create_thread(self, bot_id: int) -> discord.Thread:
        approval_feedback_channel = self.self_bot.main_guild.get_channel(733144038873759804)
        created_thread = await approval_feedback_channel.start_thread(
            name = f"feedback-{bot_id}",
            type = discord.ChannelType.public_thread,
            reason = f"Approval Feedback for bot with ID: {bot_id}"
        )
        return created_thread

    async def send_first_message(self, thread: discord.Thread, user: discord.Member, bot_owner: discord.Member):
        user_in_main_guild = self.self_bot.main_guild.get_member(user.id)
        await self.main_webhook.send(
            username = f"{user_in_main_guild.display_name} | {user_in_main_guild.top_role.name}",
            avatar_url = user.avatar,
            content = bot_owner.mention,
            thread = thread  # type: ignore
        )

    @discord.ui.button(label = "Approval Feedback", style = discord.ButtonStyle.blurple)
    async def approval_button(self, button: discord.Button, interaction: discord.Interaction):
        await self.disable_button(interaction.message)
        info = await self.get_bot_info(interaction.channel.category_id)
        if not info:
            await interaction.response.send_message(
                "Something went wrong... i can't find the bot that is being tested here.")
            return

        bot_owner, bot_info_command = info
        thread = await self.create_thread(self.bot.id)
        await thread.add_user(bot_owner)  # type: ignore
        await thread.add_user(interaction.user)
        await bot_info_command(BotInfoContext(thread), bot=self.bot)
        await self.send_first_message(thread, interaction.user, bot_owner)
        await interaction.response.send_message(
            f"Successfully created a thread with the bot owner at {thread.mention}.")

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        await self.disable_button(interaction.message)
        bot_id = self.get_bot_id(interaction.channel.category_id)
        feedback_thread = discord.utils.get(self.self_bot.main_guild.threads, name = f"feedback-{bot_id}")
        if feedback_thread:
            await interaction.response.send_message(
                f"This bot already has a feedback thread at {feedback_thread.mention}."
            )
            return False
        return True
