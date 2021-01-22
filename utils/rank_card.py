import functools
from io import BytesIO
from typing import Tuple

from .announcements import _get_unique_id
import asyncio
import discord
from discord.ext.commands import Context
from discord import Member
from PIL import Image, ImageDraw, ImageFont, ImageOps

loop = asyncio.get_event_loop()

def async_executor():
    def outer(func):
        @functools.wraps(func)
        def inner(*args, **kwargs):
            thing = functools.partial(func, *args, **kwargs)
            return loop.run_in_executor(None, thing)

        return inner

    return outer

def calculate_brightness(image):
    greyscale_image = image.convert('L')
    histogram = greyscale_image.histogram()
    pixels = sum(histogram)
    brightness = scale = len(histogram)

    for index in range(0, scale):
        ratio = histogram[index] / pixels
        brightness += ratio * (-scale + index)

    return 1 if brightness == 255 else brightness / scale

class Rank:
    def __init__(self, ctx: Context, member: Member, **kwargs) -> None:
        ctx = ctx
        self.username_font_name = "calibrib.ttf"
        self.position_font_name = "calibri.ttf"
        self.user_font = ImageFont.truetype("calibrib.ttf", 21)
        self.xp_level_font = ImageFont.truetype("calibri.ttf", 18)
        self.bug_hunter = kwargs.get("bug_hunter", False)
        self.developer = kwargs.get("developer", False)
        self.donator = kwargs.get("donator", False)
        self.ctx = ctx
        self.user = member

    @async_executor()
    def get_card(self, xp: int, level: int, position: int, avatar_bytes, badges: dict, custom: dict) -> BytesIO:
        avatar = Image.open(avatar_bytes)
        needed_xp = 50 + level * 50
        #im = Image.new('RGBA', (600, 150), (44, 44, 44, 255))

        border_color = str(self.user.color)
        if custom.get('border_color', None):
            border_color = custom['border_color']
        if custom.get('xp_color', None):
            xp_bar_color = custom['xp_color']
        else:
            xp_bar_color = "text"
        if custom.get('background', None):
            bg = custom['background']
            if isinstance(bg, BytesIO):  # url
                im = Image.open(bg)
                im = im.resize((600, 150))
            else:  # hex
                im = Image.new('RGBA', (600, 150), bg)
        else:
            im = Image.new('RGBA', (600, 150), (44, 44, 44, 255))

        text_color = 'black' if calculate_brightness(im) > 0.5 else 'white'
        xp_bar_color = text_color if xp_bar_color == "text" else xp_bar_color
        # border/outline
        im = ImageOps.expand(im, border = 5, fill = border_color)

        fontsize = 1
        img_fraction = 0.30

        font = ImageFont.truetype(self.username_font_name, fontsize)
        while font.getsize(str(self.user))[0] < img_fraction * im.size[0]:
            # iterate until the text size is just larger than the criteria
            fontsize += 1
            font = ImageFont.truetype(self.username_font_name, fontsize)

        fontsize -= 1
        font = ImageFont.truetype(self.username_font_name, fontsize)
        im_draw = ImageDraw.Draw(im)
        pos_font = ImageFont.truetype(self.position_font_name, fontsize)
        im_draw.text((159, 15), str(self.user), font=font, fill=text_color)
        im_draw.text((380, 15), f"| #{position}", font=pos_font, fill=text_color)
        im_draw.text((159, 85), f"{xp} / {needed_xp}", font=self.xp_level_font, fill=text_color)
        im_draw.text((311, 85), f"Level: {level}", font=self.xp_level_font, fill=text_color)

        im_draw.rectangle((159, 105, 379, 130), fill=(64, 64, 64, 255))
        im_draw.rectangle((159, 105, 179 + (int(int(xp)/needed_xp * 100)) * 2, 130), fill=xp_bar_color)

        im.paste(avatar, (15, 15), avatar)

        badge_x_pos, badge_y_pos = 385, 100
        if self.developer:
            badge_x_pos += 10
            dev_badge = Image.open(badges['developer'])
            dev_badge = dev_badge.resize((30, 30))
            im.paste(dev_badge, (badge_x_pos, badge_y_pos), dev_badge)
        if self.donator:
            badge_x_pos += 30
            donator_badge = Image.open(badges['donator'])
            donator_badge = donator_badge.resize((30, 30))
            im.paste(donator_badge, (badge_x_pos, badge_y_pos), donator_badge)
        if self.bug_hunter:
            badge_x_pos += 30
            bug_hunter_badge = Image.open(badges['bug_hunter'])
            bug_hunter_badge = bug_hunter_badge.resize((30, 30))
            im.paste(bug_hunter_badge, (badge_x_pos, badge_y_pos), bug_hunter_badge)

        buffer = BytesIO()
        im.save(buffer, 'png')
        buffer.seek(0)

        return buffer

    async def customize_rank_card(self, update_type: str, new_value: str = None) -> Tuple[bool, str]:
        queries = {
            "XP_BAR_COLOUR": "UPDATE main_site_leveling SET xp_bar_color = $1 WHERE user_id = $2",
            "BORDER_COLOUR": "UPDATE main_site_leveling SET border_color = $1 WHERE user_id = $2",
            "BACKGROUND": "UPDATE main_site_leveling SET background_color = $1 WHERE user_id = $2"
        }
        try:
            user_id = await _get_unique_id(self.ctx, "USER", self.user.id)
            if not new_value:
                new_value = ""
            await self.ctx.bot.pool.execute(queries[str(update_type)], new_value, user_id)
            return True, str(new_value)
        except Exception as err:
            return False, str(err)
