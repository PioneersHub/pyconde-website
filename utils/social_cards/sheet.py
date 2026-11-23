"""Contact sheets: rendered cards side by side for visual review."""

from pathlib import Path

from PIL import Image, ImageDraw

from social_cards.brand import REPO_ROOT

REFERENCE_CARD = REPO_ROOT / "assets/static/media/social_card.png"
TILE_WIDTH = 560
GAP = 24
LABEL_H = 28


def contact_sheet(
    items: list[tuple[str, Image.Image]],
    path: Path,
    columns: int = 3,
    reference: bool = True,
) -> Path:
    """Grid of labelled tiles; the official 2027 default card comes first."""
    tiles = []
    if reference:
        with Image.open(REFERENCE_CARD) as ref:
            tiles.append(
                ("reference: assets/static/media/social_card.png", ref.convert("RGB"))
            )
    tiles += items
    scaled = [
        (
            label,
            im.resize(
                (TILE_WIDTH, round(TILE_WIDTH * im.height / im.width)),
                Image.Resampling.LANCZOS,
            ),
        )
        for label, im in tiles
    ]
    rows = [scaled[i : i + columns] for i in range(0, len(scaled), columns)]
    heights = [max(im.height for _, im in row) + LABEL_H for row in rows]
    sheet = Image.new(
        "RGB",
        (columns * (TILE_WIDTH + GAP) + GAP, sum(heights) + GAP * (len(rows) + 1)),
        "#e6e6e6",
    )
    draw = ImageDraw.Draw(sheet)
    y = GAP
    for row, h in zip(rows, heights, strict=True):
        for i, (label, im) in enumerate(row):
            x = GAP + i * (TILE_WIDTH + GAP)
            sheet.paste(im, (x, y))
            draw.text((x, y + im.height + 6), label, fill="#333333")
        y += h + GAP
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path, "PNG", optimize=True)
    return path
