# Copyright (c) Huawei Technologies Co., Ltd. 2026. All rights reserved.

"""Custom pixel artwork for a buddy species.

One file per species and frame, ``<species>_<frame>.png``, under the buddy
assets directory. Art is stored exactly as supplied; the renderer normalizes it
to the 20x16 canvas with nearest-neighbor sampling when it loads.
"""

from __future__ import annotations

from pathlib import Path

from chrys.app.features.buddy.animation import FRAME_COUNT
from chrys.app.features.buddy.model import Species
from chrys.foundation.platform import get_platform
from chrys.foundation.platform.files import atomic_write_owner_only_bytes

_ASSETS = Path("extras") / "buddy" / "assets"


def assets_dir() -> Path:
    """The directory custom buddy artwork is read from and written to."""
    return get_platform().config_dir / _ASSETS


def frame_path(species: Species, frame: int) -> Path:
    """The file that overrides *frame* of *species*, whether or not it exists."""
    _require_frame(frame)
    return assets_dir() / f"{species.value}_{frame}.png"


def is_custom_frame(species: Species, frame: int) -> bool:
    """Whether a custom file is installed for *frame* of *species*."""
    return frame_path(species, frame).is_file()


def install_frame(species: Species, frame: int, source: Path) -> None:
    """Copy *source* into *species*'s *frame* slot, atomically.

    Raises:
        OSError: *source* cannot be read, or is not a decodable PNG, or the
            destination cannot be written. Nothing is written on failure.
    """
    from io import BytesIO

    from PIL import Image

    destination = frame_path(species, frame)
    payload = Path(source).read_bytes()
    try:
        # Custom artwork is PNG by contract; no other decoder ever reads this file.
        with Image.open(BytesIO(payload), formats=("PNG",)) as opened:
            opened.verify()
    except (SyntaxError, ValueError, Image.DecompressionBombError) as exc:
        raise OSError(f"not a decodable image: {source}") from exc
    atomic_write_owner_only_bytes(destination, payload)


def remove_frame(species: Species, frame: int) -> None:
    """Delete *species*'s custom *frame*, if any. A missing file is fine."""
    frame_path(species, frame).unlink(missing_ok=True)


def _require_frame(frame: int) -> None:
    if not 0 <= frame < FRAME_COUNT:
        raise ValueError(f"frame must be in 0..{FRAME_COUNT - 1}, got {frame}")
