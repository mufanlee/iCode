# Copyright (c) Huawei Technologies Co., Ltd. 2026. All rights reserved.

"""Buddy portraits and the egg placeholder shown before one hatches."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.text import Text

from chrys.app.features.buddy.model import Rarity
from chrys.app.features.buddy.pixel_renderer import (
    DEFAULT_BG_RGB,
    image_to_half_block_lines,
    matrix_to_image,
)
from chrys.app.features.buddy.pixel_sprites import PIXEL_HEIGHT, PIXEL_WIDTH, render_pixel_sprite

if TYPE_CHECKING:
    from chrys.app.features.buddy.model import Appearance

# The colour a tier is shown in, wherever it is shown.
RARITY_COLORS: dict[Rarity, str] = {
    Rarity.N: "#808080",
    Rarity.R: "#00ff00",
    Rarity.SR: "#bf00ff",
    Rarity.SSR: "#ffa500",
}

PORTRAIT_WIDTH = PIXEL_WIDTH + 4
PORTRAIT_HEIGHT = PIXEL_HEIGHT // 2 + 3
SHINY_FPS = 10

# The placeholder drawn before a buddy hatches: a 12x16 pixel egg laid out for
# the half-block renderer, so it shares the portraits' pixel look and palette.
EGG_WIDTH = 12
# The art's terminal rows plus the corner rows that frame it, as on a portrait.
EGG_HEIGHT = 16 // 2 + 2
# The egg has no rarity to advertise yet, so its corners stay neutral.
EGG_FRAME_COLOR = "#808080"
_EGG_PALETTE: dict[int, tuple[int, int, int, int]] = {
    0: (0, 0, 0, 0),
    1: (234, 223, 200, 255),  # Warm cream shell
    2: (255, 247, 233, 255),  # Sunlit highlight
    3: (196, 178, 149, 255),  # Shaded shell
}
_EGG_FRAME = [
    "000000000000",
    "000002200000",
    "000022220000",
    "000222233000",
    "002222113300",
    "002222113300",
    "022222111330",
    "022222111330",
    "022211111330",
    "022211111330",
    "022111111330",
    "022111111330",
    "002111111300",
    "002111113300",
    "000111133000",
    "000011330000",
]


def _nameplate(look: Appearance, name: str, width: int, effect_tick: int, bg_rgb: tuple[int, int, int] | None) -> Text:
    badge = Text(f"[{look.rarity.value}]", style=RARITY_COLORS[look.rarity])
    if look.shiny:
        badge.append(" ✧", style="gold1")
        # A short sweep followed by a rest, confined to the badge. Keep the
        # highlight readable on light themes as well as dark terminal panels.
        phase = effect_tick % (len(badge) + 6)
        highlight = "bold reverse" if bg_rgb is None else "bold #6b4400" if sum(bg_rgb) > 384 else "bold #fff1b8"
        if phase < len(badge):
            badge.stylize(highlight, phase, phase + 1)
    badge.truncate(width, overflow="ellipsis")
    label = Text(" ".join(name.split()))
    label.truncate(max(0, width - badge.cell_len - 1), overflow="ellipsis")
    if label:
        label.append(" ")
    label.append(badge)
    label.align("center", width)
    return label


def render_portrait(
    look: Appearance,
    name: str,
    frame: int = 0,
    blink: bool = False,
    *,
    width: int = PORTRAIT_WIDTH,
    effect_tick: int = 0,
    bg_rgb: tuple[int, int, int] | None = DEFAULT_BG_RGB,
) -> list[Text]:
    """Render a fixed-height pixel portrait at the available panel width."""
    width = max(1, min(width, PORTRAIT_WIDTH))
    body = render_pixel_sprite(look.species, frame, blink, bg_rgb=bg_rgb, width=width)
    for row in body:
        row.truncate(width)
        row.align("center", width)

    if width >= PIXEL_WIDTH + 2:
        color = RARITY_COLORS[look.rarity]
        top = Text("┌" + " " * (width - 2) + "┐", style=color)
        bottom = Text("└" + " " * (width - 2) + "┘", style=color)
    else:
        # Corners need their own columns; omit them before crowding the body.
        top = Text(" " * width)
        bottom = Text(" " * width)
    return [top, *body, bottom, _nameplate(look, name, width, effect_tick, bg_rgb)]


def render_egg(*, width: int = EGG_WIDTH, bg_rgb: tuple[int, int, int] | None = DEFAULT_BG_RGB) -> list[Text]:
    """Render the pre-hatch egg placeholder inside neutral portrait corners."""
    frame_width = max(EGG_WIDTH + 2, width)
    body = image_to_half_block_lines(matrix_to_image(_EGG_FRAME, _EGG_PALETTE), bg_rgb=bg_rgb)
    for line in body:
        line.align("center", frame_width)
    top = Text("┌" + " " * (frame_width - 2) + "┐", style=EGG_FRAME_COLOR)
    bottom = Text("└" + " " * (frame_width - 2) + "┘", style=EGG_FRAME_COLOR)
    return [top, *body, bottom]
