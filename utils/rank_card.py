from io import BytesIO

from PIL import Image, ImageDraw, ImageFont, ImageOps


class Rank:
    def __init__(self, **kwargs) -> None:
        self.font = ImageFont.truetype('arialbd.ttf', 28)
        self.medium_font = ImageFont.truetype('arialbd.ttf', 22)
        self.small_font = ImageFont.truetype('arialbd.ttf', 16)
        self.bug_hunter = kwargs.get("bug_hunter", False)
        self.developer = kwargs.get("developer", False)
        self.donator = kwargs.get("donator", False)

    async def draw(self, ctx, user: str, level: int, position: int, xp: int, profile_bytes: BytesIO) -> BytesIO:
        profile_bytes = Image.open(profile_bytes)
        dev_badge = Image.open(BytesIO(await (await ctx.bot.session.get("https://i.adiscorduser.com/nxPRRls.png")).read()))
        bug_hunter_badge = Image.open(BytesIO(await (await ctx.bot.session.get("https://i.adiscorduser.com/9pi4RtH.png")).read()))
        donator_badge = Image.open(BytesIO(await (await ctx.bot.session.get("https://i.adiscorduser.com/wpd4mRq.png")).read()))
        im = Image.new('RGBA', (600, 150), (44, 44, 44, 255))
        im = ImageOps.expand(im, border = 5, fill = ctx.author.color.to_rgb())

        txt = user
        fontsize = 1
        img_fraction = 0.40

        font = ImageFont.truetype("arial.ttf", fontsize)
        while font.getsize(txt)[0] < img_fraction * im.size[0]:
            # iterate until the text size is just larger than the criteria
            fontsize += 1
            font = ImageFont.truetype("arial.ttf", fontsize)

        fontsize -= 1
        font = ImageFont.truetype("arial.ttf", fontsize)
        im_draw = ImageDraw.Draw(im)

        im_draw.text((159, 15), user, font=font, fill=(255, 255, 255, 255))
        im_draw.text((400, 15), f"| #{position}", font=self.font, fill=(255, 255, 255, 255))
        #im_draw.text((380, 95), f"#{position}", font=self.font, fill=(255, 255, 255, 255))
        im_draw.text((159, 80), f"{xp} / {self.neededxp(level)}", font=self.small_font, fill=(255, 255, 255, 255))
        im_draw.text((311, 80), f"Level: {level}", font=self.small_font, fill=(255, 255, 255, 255))

        im_draw.rectangle((159, 105, 379, 130), fill=(64, 64, 64, 255))
        im_draw.rectangle((159, 105, 179 + (int(int(xp)/self.neededxp(level) * 100)) * 2, 130), fill=(221, 221, 221, 255))

        im.paste(profile_bytes, (15, 15), profile_bytes)

        badge_x_pos, badge_y_pos = 385, 100
        if self.developer:
            badge_x_pos += 10
            dev_badge = dev_badge.resize((30, 30))
            im.paste(dev_badge, (badge_x_pos, badge_y_pos), dev_badge)
        if self.donator:
            badge_x_pos += 30
            donator_badge = donator_badge.resize((30, 30))
            im.paste(donator_badge, (badge_x_pos, badge_y_pos), donator_badge)
        if self.bug_hunter:
            badge_x_pos += 30
            bug_hunter_badge = bug_hunter_badge.resize((30, 30))
            im.paste(bug_hunter_badge, (badge_x_pos, badge_y_pos), bug_hunter_badge)

        buffer = BytesIO()
        im.save(buffer, 'png')
        buffer.seek(0)

        return buffer

    @staticmethod
    def neededxp(level: int) -> int:
        return 50 + level * 50