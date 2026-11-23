"""The official python illustrations, analysed once.

Each artwork is trimmed to its ink bounds (the PNGs carry transparent
padding) and classified by the palette colours its body uses, so layouts can
pick a python that never shares a colour with the field it sits on.
"""

import io
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from PIL import Image

from social_cards.brand import REPO_ROOT, Brand

OPAQUE_ALPHA = 250  # anti-aliased edges are not body colour


@dataclass(frozen=True)
class PythonArt:
    path: Path
    aspect: float  # width / height of the trimmed artwork
    colors: tuple[str, ...]  # palette keys of its body colours


def _rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


@cache
def trimmed_png(path: Path) -> bytes:
    with Image.open(path) as src:
        im = src.convert("RGBA")
    im = im.crop(im.getchannel("A").getbbox())
    out = io.BytesIO()
    im.save(out, "PNG", optimize=True)
    return out.getvalue()


def _analyse(path: Path, palette: dict[str, str], threshold: float) -> PythonArt:
    with Image.open(io.BytesIO(trimmed_png(path))) as im:
        small = im.reduce(4)
        aspect = im.width / im.height
    targets = {name: _rgb(hex_color) for name, hex_color in palette.items()}
    counts: dict[str, int] = dict.fromkeys(targets, 0)
    opaque = 0
    for r, g, b, a in small.get_flattened_data():
        if a < OPAQUE_ALPHA:
            continue
        opaque += 1
        nearest = min(
            targets,
            key=lambda n: sum(
                (c - t) ** 2 for c, t in zip((r, g, b), targets[n], strict=True)
            ),
        )
        counts[nearest] += 1
    colors = tuple(
        sorted(n for n, c in counts.items() if opaque and c / opaque >= threshold)
    )
    return PythonArt(path=path, aspect=aspect, colors=colors)


@cache
def catalog(brand: Brand) -> tuple[PythonArt, ...]:
    spec = brand.raw["pythons"]
    paths = sorted((REPO_ROOT / spec["directory"]).glob("Python_*.png"))
    if not paths:
        raise FileNotFoundError(f"no python artwork in {spec['directory']}")
    return tuple(
        _analyse(p, brand.palette, spec["body_color_threshold"]) for p in paths
    )


def eligible(brand: Brand, field: str) -> list[PythonArt]:
    """Pythons that contain no pixel of the field colour."""
    return [art for art in catalog(brand) if field not in art.colors]
