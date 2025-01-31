import json
from PIL import Image, ImageDraw, ImageFont
import textwrap


def load_submissions():
    submissions = []
    with open("databags/submissions.json", "r") as f:
        j = json.load(f)
        submissions = j['submissions']
    return submissions


def main():
    subs = load_submissions()
    # We are using IBM Plex Sans, since it is a free font
    # that is very close to the not free font Helvetica.
    # It is licensed under the Open Font License.
    headline_font = ImageFont.truetype(
        "assets/static/media/social/talks/IBMPlexSans-Bold.ttf", 80)
    speaker_font = ImageFont.truetype(
        "assets/static/media/social/talks/IBMPlexSans-Medium.ttf", 50)
    color = (255, 255, 255)
    for sub in subs:
        img = Image.open("assets/static/media/social/talks/social-card.png")
        d = ImageDraw.Draw(img)
        headlines = "\n".join(textwrap.wrap(sub["title"], 25))
        d.multiline_text((10, 10), headlines, fill=color, font=headline_font)
        d.text((10, 550), sub["speaker_names"],
               fill=color, font=speaker_font)
        img.save(f"assets/static/media/social/talks/{sub['code']}.png")


if __name__ == "__main__":
    main()
