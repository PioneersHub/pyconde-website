import json
from pathlib import Path
from random import choice

from PIL import Image, ImageDraw, ImageFont
import textwrap

src_path = Path(__file__).parents[1]


def load_talks():
    talks = []
    with (src_path / "databags/talks.json").open() as f:
        j = json.load(f)
        talks = j["talks"]
    return talks


def opt_break(text, max_chars, keep_line=False):
    """
    Make more visually appealing breaks
    :param text:
    :param max_chars:
    :param keep_line: break line of if line length is exceeded, e.g., for speakers
    :return:
    """
    if keep_line and len(text) <= max_chars:
        return text
    for c in (":", " - ", ", "):
        if c in text:
            idx = text.rfind(c, 0, max_chars)
            if 0 < idx <= max_chars and len(text[idx + 1 :]) <= max_chars:
                return text[: idx + 1].strip() + "\n" + text[idx + 1 :].strip()
    if len(text) <= max_chars:
        return text
    return "\n".join(textwrap.wrap(text, max_chars))


blue = (0, 200, 225)
darkblue = (55, 120, 190)
green = (150, 220, 0)
darkgreen = (0, 170, 65)
orange = (255, 155, 0)
yellow = (250, 200, 0)
grey = (183, 188, 191)
white = (255, 255, 255)
black = (0, 0, 0)

card_colors = {
    "blue": {
        "title": darkblue,
        "speaker": darkgreen,
        "company": white,
    },
    "darkblue": {
        "title": orange,
        "speaker": green,
        "company": white,
    },
    "green": {
        "title": darkblue,
        "speaker": orange,
        "company": white,
    },
    "darkgreen": {
        "title": yellow,
        "speaker": blue,
        "company": white,
    },
    "orange": {
        "title": darkblue,
        "speaker": yellow,
        "company": white,
    },
    "yellow": {
        "title": darkblue,
        "speaker": darkgreen,
        "company": white,
    },
    "grey": {
        "title": darkblue,
        "speaker": white,
        "company": black,
    },
}


def load_random_color():
    return choice(list(card_colors.keys()))


def main():
    talks = load_talks()
    # We are using IBM Plex Sans, since it is a free font
    # that is very close to the not free font Helvetica.
    # It is licensed under the Open Font License.
    fonts = src_path / "assets/static/fonts"
    cards = src_path / "assets/static/media/social/social-card-templates"
    font = ImageFont.truetype(fonts / "IBMPlexSans-Medium.ttf", 110)
    code_font = ImageFont.truetype(fonts / "IBMPlexSans-Regular.ttf", 37)
    for talk in talks:
        dst = src_path / f"assets/static/media/social/talks/{talk['code']}.png"
        # make colors consistent
        card_color = load_random_color()
        inf = src_path / f"assets/static/media/social/talks/{talk['code']}.json"
        if inf.exists():
            with inf.open() as f:
                j = json.load(f)
            if (talk["title"] == j["title"]) and (
                talk["speaker_names"] == j["speaker_names"] and dst.exists()
            ):
                continue
            card_color = j["color"]

        img = Image.open(cards / f"social-card-{card_color}.png")
        d = ImageDraw.Draw(img)
        # we must limit to two lines, the title can be max 100 chars
        # headlines = "\n".join(textwrap.wrap(talk["title"], 60))
        headlines = opt_break(talk["title"], 60)
        d.multiline_text(
            (227, 1196), headlines, fill=card_colors[card_color]["title"], font=font
        )
        speakers = opt_break(talk["speaker_names"], 60, keep_line=True)
        d.text(
            (227, 1500), speakers, fill=card_colors[card_color]["speaker"], font=font
        )
        d.text(
            (227, 1735),
            talk["code"],
            fill=card_colors[card_color]["title"],
            font=code_font,
        )
        img.save(dst)
        with inf.open("w") as f:
            json.dump(
                {
                    "title": talk["title"],
                    "speaker_names": talk["speaker_names"],
                    "color": card_color,
                },
                f,
            )


if __name__ == "__main__":
    main()
