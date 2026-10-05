# Copyright (c) Huawei Technologies Co., Ltd. 2026. All rights reserved.

"""Shared stub ports for buddy-config dialog tests."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path

from chrys.app.features.buddy.model import Buddy, Species
from chrys.app.tui.screens.buddy_config.ports import FrameState


def _record(seed: int = 7, *, muted: bool = False) -> Buddy:
    from random import Random

    from chrys.app.features.buddy.hatchery import hatchling

    return Buddy.of(replace(hatchling(Random(seed)), muted=muted))


@dataclass
class StubPorts:
    """A minimal BuddyConfigPorts good enough to render every pane."""

    _buddy: Buddy | None = field(default_factory=_record)
    reply_model_value: str = ""
    model_choices: list[tuple[str, str]] = field(default_factory=lambda: [("", "Follow active")])
    custom_frames: set[int] = field(default_factory=set)
    calls: list[tuple[str, object]] = field(default_factory=list)

    def buddy(self) -> Buddy | None:
        return self._buddy

    def species(self) -> Species | None:
        return self._buddy.species if self._buddy else None

    def frame_state(self, frame: int) -> FrameState:
        return FrameState.CUSTOM if frame in self.custom_frames else FrameState.BUILTIN

    def assets_dir(self) -> Path:
        return Path("assets")

    async def rename(self, name: str) -> None:
        self.calls.append(("rename", name))

    async def set_muted(self, muted: bool) -> None:
        self.calls.append(("muted", muted))

    async def set_reply_model(self, model_id: str) -> None:
        self.calls.append(("model", model_id))

    async def hatch(self) -> None:
        self.calls.append(("hatch", None))
        # A fresh draw so a test can see the dialog gain a buddy.
        self._buddy = _record(9)

    async def rehatch(self) -> None:
        self.calls.append(("rehatch", None))
        # A different draw (and mute state) so a stale pane is detectable.
        self._buddy = _record(8, muted=True)

    async def import_frame(self, frame: int, source: Path) -> None:
        self.calls.append(("import", (frame, source)))

    async def remove_frame(self, frame: int) -> None:
        self.calls.append(("remove", frame))

    def reply_model(self) -> str:
        return self.reply_model_value

    def model_options(self) -> list[tuple[str, str]]:
        return self.model_choices

    def open_assets_dir(self) -> None:
        self.calls.append(("open_dir", None))

    def notify(self, message, *, severity: str = "information", timeout: float = 10) -> None:
        self.calls.append(("notify", message))
