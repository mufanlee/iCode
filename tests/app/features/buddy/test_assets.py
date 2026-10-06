# Copyright (c) Huawei Technologies Co., Ltd. 2026. All rights reserved.

"""Custom buddy artwork: where it lives and how one frame is installed."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image

from chrys.app.features.buddy import assets
from chrys.app.features.buddy.model import Species


def _write_png(path: Path, size: tuple[int, int] = (20, 16)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", size, (255, 0, 0, 255)).save(path)


def _corrupt_png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGBA", (20, 16), (10, 20, 30, 255)).save(buffer, format="PNG")
    data = bytearray(buffer.getvalue())
    data[len(data) // 2] ^= 0xFF  # break a chunk so PIL raises while decoding
    return bytes(data)


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


def test_install_rejects_a_corrupt_png_and_writes_nothing(tmp_path: Path) -> None:
    source = tmp_path / "corrupt.png"
    source.write_bytes(_corrupt_png_bytes())

    with pytest.raises(OSError):
        assets.install_frame(Species.MUSHROOM, 2, source)

    assert not assets.is_custom_frame(Species.MUSHROOM, 2)


def test_frame_path_rejects_an_out_of_range_frame() -> None:
    with pytest.raises(ValueError):
        assets.frame_path(Species.MUSHROOM, 6)
    with pytest.raises(ValueError):
        assets.frame_path(Species.MUSHROOM, -1)


def test_reinstall_overwrites_the_frame(tmp_path: Path) -> None:
    first = tmp_path / "first.png"
    Image.new("RGBA", (20, 16), (255, 0, 0, 255)).save(first)
    second = tmp_path / "second.png"
    Image.new("RGBA", (20, 16), (0, 255, 0, 255)).save(second)

    assets.install_frame(Species.MUSHROOM, 0, first)
    assets.install_frame(Species.MUSHROOM, 0, second)

    assert assets.frame_path(Species.MUSHROOM, 0).read_bytes() == second.read_bytes()
