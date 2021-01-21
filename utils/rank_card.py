from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

class Rank:
    def __init__(self) -> None:
        self.font = ImageFont.truetype('arialbd.ttf', 28)
        self.medium_font = ImageFont.truetype('arialbd.ttf', 22)
        self.small_font = ImageFont.truetype('arialbd.ttf', 16)

    def draw(self, user: str, rank: str, xp: str, profile_bytes: BytesIO) -> BytesIO:
        profile_bytes = Image.open(profile_bytes)
        im = Image.new('RGBA', (600, 150), (44, 44, 44, 255))
        txt = user
        fontsize = 1  # starting font size

        # portion of image width you want text width to be
        img_fraction = 0.50

        font = ImageFont.truetype("arial.ttf", fontsize)
        while font.getsize(txt)[0] < img_fraction * im.size[0]:
            # iterate until the text size is just larger than the criteria
            fontsize += 1
            font = ImageFont.truetype("arial.ttf", fontsize)

        # optionally de-increment to be sure it is less than criteria
        fontsize -= 1
        font = ImageFont.truetype("arial.ttf", fontsize)
        im_draw = ImageDraw.Draw(im)
        im_draw.text((154, 5), user, font=font, fill=(255, 255, 255, 255))

        rank_text = f'| #{rank}'
        im_draw.text((530, 6), rank_text, font=self.font, fill=(255, 255, 255, 255))

        needed_xp = self.neededxp(rank)
        xp_text = f'{xp}/{needed_xp}'
        im_draw.text((154, 62), xp_text, font=self.small_font, fill=(255, 255, 255, 255))

        im_draw.rectangle((174, 95, 374, 125), fill=(64, 64, 64, 255))
        im_draw.rectangle((174, 95, 174+(int(int(xp)/needed_xp*100))*2, 125), fill=(221, 221, 221, 255))

        im.paste(profile_bytes, (10, 10))

        buffer = BytesIO()
        im.save(buffer, 'png')
        buffer.seek(0)

        return buffer

    @staticmethod
    def neededxp(level: str) -> int:
        return 50+level*50