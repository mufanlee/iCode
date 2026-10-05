# Copyright (c) Huawei Technologies Co., Ltd. 2026. All rights reserved.

"""Custom buddy artwork: where it lives and how one frame is installed."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from chrys.app.features.buddy import assets
from chrys.app.features.buddy.model import Species


def _write_png(path: Path, size: tuple[int, int] = (20, 16)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", size, (255, 0, 0, 255)).save(path)


def test_frame_path_names_the_species_and_frame() -> None:
    assert assets.frame_path(Species.MUSHROOM, 3).name == "mushroom_3.png"


def test_install_then_remove_round_trips_a_frame(tmp_path: Path) -> None:
    source = tmp_path / "art.png"
    _write_png(source, (40, 32))

    assert not assets.is_custom_frame(Species.MUSHROOM, 0)
    assets.install_frame(Species.MUSHROOM, 0, source)
    assert assets.is_custom_frame(Species.MUSHROOM, 0)
    assert assets.frame_path(Species.MUSHROOM, 0).read_bytes() == source.read_bytes()

    assets.remove_frame(Species.MUSHROOM, 0)
    assert not assets.is_custom_frame(Species.MUSHROOM, 0)


def test_install_rejects_a_non_image_and_writes_nothing(tmp_path: Path) -> None:
    source = tmp_path / "notes.txt"
    source.write_text("not an image", encoding="utf-8")

    with pytest.raises(OSError):
        assets.install_frame(Species.MUSHROOM, 1, source)

    assert not assets.is_custom_frame(Species.MUSHROOM, 1)


def test_remove_a_missing_frame_is_a_no_op() -> None:
    assets.remove_frame(Species.MUSHROOM, 5)  # must not raise
