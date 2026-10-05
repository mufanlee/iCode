# Copyright (c) Huawei Technologies Co., Ltd. 2026. All rights reserved.

"""Implements ``BuddyConfigPorts`` for the main screen."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from chrys.app.features.buddy import actions, assets, pixel_sprites
from chrys.app.tui.screens.buddy_config import FrameState
from chrys.foundation.i18n import msg

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping, Sequence
    from typing import Any

    from chrys.app.features.buddy.model import Buddy, Species
    from chrys.foundation.config.settings import Settings
    from chrys.foundation.i18n import MessageRef

logger = logging.getLogger(__name__)

REPLY_MODEL_KEY = "model.role.buddy_model_id"
_SAVE_FAILED = msg("tui.buddy_config.toast.save_failed", fallback="Buddy save file could not be updated")
_IMPORT_FAILED = msg("tui.buddy_config.toast.install_failed", fallback="Buddy artwork could not be installed")
_REMOVE_FAILED = msg("tui.buddy_config.toast.remove_failed", fallback="Buddy artwork could not be removed")


@dataclass(frozen=True, slots=True)
class BuddyConfigCallbacks:
    """Screen-supplied effects the coordinator needs but does not own."""

    save_settings: Callable[[Mapping[str, Any], tuple[str, ...]], Awaitable[None]]
    notify: Callable[..., None]
    settings: Callable[[], Settings]
    model_options: Callable[[], Sequence[tuple[str, str]]]
    open_path: Callable[[Path], None]


class BuddyConfigCoordinator:
    """Buddy-config ports; buddy writes run on a thread under the save lock."""

    def __init__(self, callbacks: BuddyConfigCallbacks) -> None:
        self._callbacks = callbacks

    def buddy(self) -> Buddy | None:
        return actions.current_buddy()

    def species(self) -> Species | None:
        buddy = actions.current_buddy()
        return buddy.species if buddy is not None else None

    def frame_state(self, frame: int) -> FrameState:
        # CUSTOM means "custom art is present AND decodes": an unreadable or
        # undecodable file must read as BUILTIN, matching the renderer's silent
        # fallback. ``load_external_pixel_frame`` returns None on any failure.
        species = self.species()
        if species is None:
            return FrameState.BUILTIN
        if pixel_sprites.load_external_pixel_frame(species, frame) is not None:
            return FrameState.CUSTOM
        return FrameState.BUILTIN

    def assets_dir(self) -> Path:
        return assets.assets_dir()

    def reply_model(self) -> str:
        return self._callbacks.settings().buddy_model

    def model_options(self) -> list[tuple[str, str]]:
        return list(self._callbacks.model_options())

    async def rename(self, name: str) -> None:
        await self._buddy_write(actions.rename, name)

    async def set_muted(self, muted: bool) -> None:
        await self._buddy_write(actions.set_muted, muted)

    async def hatch(self) -> None:
        await self._buddy_write(actions.hatch)

    async def rehatch(self) -> None:
        await self._buddy_write(actions.rehatch)

    async def import_frame(self, frame: int, source: Path) -> None:
        species = self.species()
        if species is None:
            return
        try:
            await asyncio.to_thread(assets.install_frame, species, frame, source)
        except OSError:
            logger.warning("Buddy artwork could not be installed", exc_info=True)
            self._warn(_IMPORT_FAILED.bind())

    async def remove_frame(self, frame: int) -> None:
        species = self.species()
        if species is None:
            return
        try:
            await asyncio.to_thread(assets.remove_frame, species, frame)
        except OSError:
            logger.warning("Buddy artwork could not be removed", exc_info=True)
            self._warn(_REMOVE_FAILED.bind())

    async def set_reply_model(self, model_id: str) -> None:
        if model_id:
            await self._callbacks.save_settings({REPLY_MODEL_KEY: model_id}, ())
        else:
            await self._callbacks.save_settings({}, (REPLY_MODEL_KEY,))

    def open_assets_dir(self) -> None:
        directory = self.assets_dir()
        try:
            directory.mkdir(parents=True, exist_ok=True)
            self._callbacks.open_path(directory)
        except OSError:
            logger.warning("Buddy assets folder could not be opened", exc_info=True)

    def notify(self, message: MessageRef | str, *, severity: str = "information", timeout: float = 10) -> None:
        self._callbacks.notify(message, severity=severity, timeout=timeout)

    async def _buddy_write(self, write: Callable[..., Any], *args: Any) -> None:
        try:
            await asyncio.to_thread(write, *args)
        except OSError:
            logger.warning("Buddy save file could not be updated", exc_info=True)
            self._warn(_SAVE_FAILED.bind())

    def _warn(self, reference: MessageRef) -> None:
        self._callbacks.notify(reference, severity="warning", timeout=10)
