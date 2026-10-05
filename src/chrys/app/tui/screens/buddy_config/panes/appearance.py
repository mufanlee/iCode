# Copyright (c) Huawei Technologies Co., Ltd. 2026. All rights reserved.

"""The dialog's Appearance tab: manage the current species' six custom frames."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Button, Static

from chrys.app.features.buddy.animation import FRAME_COUNT
from chrys.app.tui.i18n import render_str
from chrys.app.tui.screens.buddy_config.ports import FrameState
from chrys.app.tui.screens.dialogs.file_picker import FilePicker, FilePickerMode
from chrys.foundation.i18n import MessageRef, msg
from chrys.foundation.i18n.formatting import format_message

if TYPE_CHECKING:
    from chrys.app.tui.i18n import LocaleController
    from chrys.app.tui.screens.buddy_config.ports import BuddyConfigPorts

_HINT = msg(
    "tui.buddy_config.appearance.hint",
    fallback="Files are <species>_<frame>.png; leaving one out uses the built-in art for that frame.",
)
_STATE_BUILTIN = msg("tui.buddy_config.appearance.state.builtin", fallback="Built-in")
_STATE_CUSTOM = msg("tui.buddy_config.appearance.state.custom", fallback="Custom")
_IMPORT = msg("tui.buddy_config.action.import", fallback="Import")
_REMOVE = msg("tui.buddy_config.action.remove", fallback="Remove")
_OPEN = msg("tui.buddy_config.action.open_folder", fallback="Open folder")
_PICKER_TITLE = msg("tui.buddy_config.appearance.picker.title", fallback="Select frame artwork")

_IMPORT_PREFIX = "frame-import-"
_REMOVE_PREFIX = "frame-remove-"
_OPEN_FOLDER_ID = "buddy-config-open-folder"


@dataclass(frozen=True)
class FrameRow:
    """One frame's index and whether it renders custom or built-in art."""

    frame: int
    state: FrameState


class AppearancePane(Widget):
    """Import or remove a custom PNG for each of the six animation frames."""

    DEFAULT_CSS = """
    AppearancePane { height: 1fr; }
    AppearancePane .frame-row { height: auto; }
    """

    def __init__(self, ports: BuddyConfigPorts, *, locale_controller: LocaleController | None = None) -> None:
        super().__init__()
        self._ports = ports
        self._locale_controller = locale_controller

    def frame_rows(self) -> list[FrameRow]:
        """One row per animation frame, carrying that frame's current artwork state."""
        return [FrameRow(frame, self._ports.frame_state(frame)) for frame in range(FRAME_COUNT)]

    def compose(self) -> ComposeResult:
        for row in self.frame_rows():
            yield Static(
                Text(f"{row.frame}: {self._state_label(row.state)}"),
                classes="frame-row",
                id=f"frame-state-{row.frame}",
            )
            yield Button(Text(self._render_message(_IMPORT.bind())), id=f"{_IMPORT_PREFIX}{row.frame}")
            yield Button(Text(self._render_message(_REMOVE.bind())), id=f"{_REMOVE_PREFIX}{row.frame}")
        yield Button(Text(self._render_message(_OPEN.bind())), id=_OPEN_FOLDER_ID)
        yield Static(Text(self._render_message(_HINT.bind())), classes="frame-row")

    async def import_into(self, frame: int, source: Path) -> None:
        """Replace one frame's artwork with the art at *source*."""
        await self._ports.import_frame(frame, source)

    async def remove(self, frame: int) -> None:  # ty: ignore[invalid-method-override]  # The domain name "remove a frame" shadows Widget.remove(); the pane owns no removals of itself.
        """Drop one frame's custom artwork, restoring the built-in sprite."""
        await self._ports.remove_frame(frame)

    @on(Button.Pressed)
    async def _on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id.startswith(_IMPORT_PREFIX):
            self._pick_frame_art(int(button_id.removeprefix(_IMPORT_PREFIX)))
        elif button_id.startswith(_REMOVE_PREFIX):
            await self.remove(int(button_id.removeprefix(_REMOVE_PREFIX)))
        elif button_id == _OPEN_FOLDER_ID:
            self._ports.open_assets_dir()

    def _pick_frame_art(self, frame: int) -> None:
        """Ask for a PNG, then import the chosen file into *frame*."""

        async def on_result(result: str | None) -> None:
            if result:
                await self.import_into(frame, Path(result))

        self.app.push_screen(
            FilePicker(
                mode=FilePickerMode.FILE,
                extensions=frozenset({".png"}),
                title=_PICKER_TITLE.bind(),
            ),
            on_result,
        )

    def _state_label(self, state: FrameState) -> str:
        reference = _STATE_CUSTOM if state is FrameState.CUSTOM else _STATE_BUILTIN
        return self._render_message(reference.bind())

    def _render_message(self, reference: MessageRef) -> str:
        controller = self._locale_controller
        if controller is None:
            return format_message(reference)
        return render_str(controller.localizer, reference)
