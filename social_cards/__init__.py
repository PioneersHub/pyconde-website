"""Generate social cards, which are just pngs, for all talks"""
# taken from https://gist.github.com/digitaltembo/eb7c8a7fdef987e6689ee8de050720c4
# code from Theodore Meynard and copied in by Florian Wilhelm from Pytanis
from collections import namedtuple
from pathlib import Path
import unicodedata

import pandas as pd
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pytanis.utils import implode
from pytanis.review import Col
from pytanis.pretalx import speakers_as_df, subs_as_df
from tqdm.auto import tqdm


ALLIGNMENT_LEFT = 0
ALLIGNMENT_CENTER = 1
ALLIGNMENT_RIGHT = 2
ALLIGNMENT_TOP = 3
ALLIGNMENT_BOTTOM = 4

TalkInfo = namedtuple("talkinfo", ["name", "affiliation", "title", "key"])

curr_dir = Path(__file__).resolve().parent
# see readme inside the folder se see how to modify the template
template_path = curr_dir / Path("./template.png")
font_path = curr_dir / Path("./Roboto-Regular.ttf")


def text_box(text, image_draw, font, box, horizontal_allignment=ALLIGNMENT_LEFT, vertical_allignment=ALLIGNMENT_TOP, **kwargs):
    """write text in the box by breaking down the string on multiple lines"""
    x = box[0]
    y = box[1]
    width = box[2]
    height = box[3]
    lines = text.split('\n')
    true_lines = []
    for line in lines:
        if font.getsize(line)[0] <= width:
            true_lines.append(line)
        else:
            current_line = ''
            for word in line.split(' '):
                if font.getsize(current_line + word)[0] <= width:
                    current_line += ' ' + word
                else:
                    true_lines.append(current_line)
                    current_line = word
            true_lines.append(current_line)

    x_offset = y_offset = 0
    lineheight = font.getsize(true_lines[0])[1] * 1.2  # Give a margin of 0.2x the font height
    if vertical_allignment == ALLIGNMENT_CENTER:
        y = int(y + height / 2)
        y_offset = - (len(true_lines) * lineheight) / 2
    elif vertical_allignment == ALLIGNMENT_BOTTOM:
        y = int(y + height)
        y_offset = - (len(true_lines) * lineheight)

    for line in true_lines:
        linewidth = font.getsize(line)[0]
        if horizontal_allignment == ALLIGNMENT_CENTER:
            x_offset = (width - linewidth) / 2
        elif horizontal_allignment == ALLIGNMENT_RIGHT:
            x_offset = width - linewidth
        image_draw.text(
            (int(x + x_offset), int(y + y_offset)),
            line,
            font=font,
            **kwargs
        )
        y_offset += lineheight


def font(font_path, size=12):
    """load font file (*.ttf) and return an image font to write text box with text"""
    return ImageFont.truetype(str(font_path), size=size, encoding="unic")

def remove_emojis(input_string):
    """remove emojis from the string"""
    return ''.join(c for c in input_string if c == 'µ' or unicodedata.category(c) not in ('So', 'Cn'))

def create_social_card(talkInfo: TalkInfo):
    """create soclai card from template by adding the title, authors and affilition"""
    img = Image.open(template_path)
    imgDraw = ImageDraw.Draw(img)
    # remoe the emoji from the title as they are not supported by the font
    tile_without_emojy = remove_emojis(talkInfo.title)
    text_box(
        text=tile_without_emojy,
        image_draw=imgDraw,
        font=font(font_path, 40),
        box=(80, 200, 650, 300),
        horizontal_allignment=ALLIGNMENT_RIGHT,
        vertical_allignment=ALLIGNMENT_CENTER,
        fill="#eb9041",
    )

    text_box(
        text=talkInfo.name,
        image_draw=imgDraw,
        font=font(font_path, 20),
        box=(80, 475, 650, 475),
        horizontal_allignment=ALLIGNMENT_RIGHT,
        fill="#000000",
    )

    text_box(
        text=talkInfo.affiliation,
        image_draw=imgDraw,
        font=font(font_path, 15),
        box=(80, 500, 650, 500),
        horizontal_allignment=ALLIGNMENT_RIGHT,
        fill="#000000",
    )

    text_box(
        text=talkInfo.key,
        image_draw=imgDraw,
        font=font(font_path, 10),
        box=(900, 500, 900, 500),
        fill="#aaaaaa",
    )

    return img.resize((1200, 630))


def make_store_social_cards(speakers, submissions, dest_path):
    # create the dataframe from raw pretalx api result
    spkrs_df = speakers_as_df(speakers, with_questions=True)
    subs_df = subs_as_df(submissions, with_questions=True)
    # join submission and speakers together
    subs_df = subs_df.explode([Col.speaker_code, Col.speaker_name])
    subs_df = pd.merge(subs_df, spkrs_df.drop(columns=[Col.speaker_name, Col.submission]), on=Col.speaker_code)
    subs_df = implode(subs_df, [col for col in spkrs_df if col not in [Col.submission]])

    # create all the social cards for all the talks and write them in 40_talk_image/output/ folder
    for _, submission in tqdm(subs_df.iterrows(), total=len(subs_df)):
        # get all speakers from a talk togethers
        names = " & ".join(submission["Speaker name"])
        # we only want the affiliation if it is not nan
        affiliation_list = submission["Q: Company / Institute"]
        affiliation = " " if np.nan in affiliation_list else " & ".join(affiliation_list)
        affiliation = affiliation.replace("\n", "")
        # other attributes where no preprocessing is needed
        title = submission["Title"]
        key = submission["Submission"]
        talkInfo = TalkInfo(
            name=names,
            affiliation=affiliation,
            title=title,
            key=key,
        )
        img = create_social_card(talkInfo)
        img.save(Path(dest_path) / Path(f"{key}.png"))
