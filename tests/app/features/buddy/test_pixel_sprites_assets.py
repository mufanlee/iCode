# Copyright (c) Huawei Technologies Co., Ltd. 2026. All rights reserved.

"""The public assets accessor backs the external frame loader."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from chrys.app.features.buddy import assets, pixel_sprites
from chrys.app.features.buddy.model import Species


def test_public_accessor_matches_the_assets_module() -> None:
    assert pixel_sprites.assets_dir() == assets.assets_dir()


def test_loader_reads_a_planted_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pixel_sprites, "assets_dir", lambda: tmp_path)
    target = tmp_path / f"{Species.MUSHROOM.value}_0.png"
    Image.new("RGBA", (20, 16), (1, 2, 3, 255)).save(target)

    loaded = pixel_sprites.load_external_pixel_frame(Species.MUSHROOM, 0)
    assert loaded is not None
    assert loaded.size == (20, 16)
