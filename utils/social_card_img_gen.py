import json
from PIL import Image, ImageDraw, ImageFont
import textwrap


def load_talks():
    talks = []
    with open("databags/talks.json", "r") as f:
        j = json.load(f)
        talks = j['talks']
    return talks


def main():
    talks = load_talks()
    # We are using IBM Plex Sans, since it is a free font
    # that is very close to the not free font Helvetica.
    # It is licensed under the Open Font License.
    font = ImageFont.truetype(
        "assets/static/media/social/talks/IBMPlexSans-SemiBold.ttf", 110)
    code_font = ImageFont.truetype(
        "assets/static/media/social/talks/IBMPlexSans-Medium.ttf", 60)
    for talk in talks:
        img = Image.open("assets/static/media/social/talks/social-card.png")
        d = ImageDraw.Draw(img)
        headlines = "\n".join(textwrap.wrap(talk["title"], 55))
        d.multiline_text((227, 1196), headlines,
                         fill=(55, 120, 190), font=font)
        d.text((227, 1500), talk["speaker_names"],
               fill=(0, 170, 65), font=font)
        d.text((227, 1735), talk["code"], fill=(55, 120, 190), font=code_font)
        img.save(f"assets/static/media/social/talks/{talk['code']}.png")


if __name__ == "__main__":
    main()
