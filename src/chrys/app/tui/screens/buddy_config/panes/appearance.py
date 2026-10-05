# Copyright (c) Huawei Technologies Co., Ltd. 2026. All rights reserved.

"""The dialog's Appearance tab: manage the current species' six custom frames."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.events import Click
from textual.widget import Widget
from textual.widgets import Button, Static

from chrys.app.features.buddy.animation import FRAME_COUNT
from chrys.app.features.buddy.portrait import PORTRAIT_WIDTH, render_portrait
from chrys.app.tui.i18n import render_str
from chrys.app.tui.screens.buddy_config.ports import FrameState
from chrys.app.tui.screens.dialogs.file_picker import FilePicker, FilePickerMode
from chrys.foundation.i18n import MessageRef, msg
from chrys.foundation.i18n.formatting import format_message

if TYPE_CHECKING:
    from textual.geometry import Region

    from chrys.app.tui.i18n import LocaleController
    from chrys.app.tui.screens.buddy_config.ports import BuddyConfigPorts

_HINT = msg(
    "tui.buddy_config.appearance.hint",
    fallback="Files are <species>_<frame>.png; leaving one out uses the built-in art for that frame.",
)
_STATE_BUILTIN = msg("tui.buddy_config.appearance.state.builtin", fallback="Built-in")
_STATE_CUSTOM = msg("tui.buddy_config.appearance.state.custom", fallback="Custom")
_PREVIEW_LABEL = msg("tui.buddy_config.appearance.preview", fallback="Preview")
_IMPORT = msg("tui.buddy_config.action.import", fallback="Import")
_REMOVE = msg("tui.buddy_config.action.remove", fallback="Remove")
_OPEN = msg("tui.buddy_config.action.open_folder", fallback="Open folder")
_PICKER_TITLE = msg("tui.buddy_config.appearance.picker.title", fallback="Select frame artwork")

_ROW_PREFIX = "frame-row-"
_IMPORT_PREFIX = "frame-import-"
_REMOVE_PREFIX = "frame-remove-"
_OPEN_FOLDER_ID = "buddy-config-open-folder"
_HINT_ID = "buddy-config-appearance-hint"
_PREVIEW_ID = "buddy-config-frame-preview"
_PREVIEW_LABEL_ID = "buddy-config-frame-preview-label"


@dataclass(frozen=True)
class FrameRow:
    """One frame's index and whether it renders custom or built-in art."""

    frame: int
    state: FrameState


class _FramePreview(Static):
    """The selected frame's portrait, repainted in place when the selection or its art changes.

    It has no timer: unlike the Profile tab's live portrait, a still preview only
    needs a repaint when the user picks a row or a frame's artwork is imported
    or removed.
    """

    def __init__(self, ports: BuddyConfigPorts, **kwargs: Any) -> None:
        super().__init__("", **kwargs)
        self._ports = ports

    def refresh(
        self,
        *regions: Region,
        repaint: bool = True,
        layout: bool = False,
        recompose: bool = False,
    ) -> Self:
        if not regions and repaint and not layout and not recompose and self.is_mounted:
            # Static.update(layout=False) otherwise dirties via Widget.size,
            # which resolves the full compositor map. Explicit regions use
            # only cached geometry; include borders/padding in this full repaint.
            regions = (self.outer_size.region - self.content_offset,)
        return super().refresh(*regions, repaint=repaint, layout=layout, recompose=recompose)

    def show_frame(self, frame: int) -> None:
        """Render frame *frame* from the buddy's custom art or the built-in sprite."""
        buddy = self._ports.buddy()
        if buddy is None:
            self.update(Text(""), layout=False)
            return
        # content_size resolves region through the compositor and can arrange
        # the whole screen; outer_size is the latest cached layout size.
        _base_background, background = self.background_colors
        width = max(0, self.outer_size.width - self.styles.gutter.width)
        lines = render_portrait(
            buddy.appearance,
            buddy.display_name,
            frame,
            blink=False,
            width=width or PORTRAIT_WIDTH,
            effect_tick=0,
            bg_rgb=None if self.app.current_theme.ansi else background.rgb,
        )
        # The preview's height is fixed by CSS; a new frame only repaints.
        self.update(Text("\n").join(lines), layout=False)


class AppearancePane(VerticalScroll):
    """A switchable portrait preview over the six frame rows, import and remove controls."""

    DEFAULT_CSS = """
    AppearancePane { height: 1fr; }
    /* Portrait size mirrors features/buddy/portrait.py: PORTRAIT_WIDTH = 24,
       PORTRAIT_HEIGHT = 11. A fixed size lets a repaint stay in place instead
       of re-laying out. */
    AppearancePane #buddy-config-frame-preview { width: 24; height: 11; margin: 0 0 1 0; }
    AppearancePane .frame-row { height: auto; }
    /* Each row is a growing state label plus fixed-size Import/Remove buttons.
       Without an explicit 1fr the label takes the whole 84-wide pane and clips
       the buttons past the right edge, leaving them unreachable by pointer. */
    AppearancePane .frame-row Static { width: 1fr; }
    /* The selected row is the frame the preview shows; tint it so the choice is visible. */
    AppearancePane .frame-row.-selected { background: $primary 16%; }
    """

    def __init__(self, ports: BuddyConfigPorts, *, locale_controller: LocaleController | None = None) -> None:
        super().__init__()
        self._ports = ports
        self._locale_controller = locale_controller
        self._selected_frame = 0

    @property
    def selected_frame(self) -> int:
        """The frame the preview currently shows."""
        return self._selected_frame

    def frame_rows(self) -> list[FrameRow]:
        """One row per animation frame, carrying that frame's current artwork state."""
        return [FrameRow(frame, self._ports.frame_state(frame)) for frame in range(FRAME_COUNT)]

    def compose(self) -> ComposeResult:
        yield Static(
            Text(self._render_message(_PREVIEW_LABEL.bind())),
            id=_PREVIEW_LABEL_ID,
        )
        yield _FramePreview(self._ports, id=_PREVIEW_ID)
        for row in self.frame_rows():
            with Horizontal(classes="frame-row", id=f"{_ROW_PREFIX}{row.frame}"):
                yield Static(
                    Text(f"{row.frame}: {self._state_label(row.state)}"),
                    id=f"frame-state-{row.frame}",
                )
                yield Button(
                    Text(self._render_message(_IMPORT.bind())),
                    id=f"{_IMPORT_PREFIX}{row.frame}",
                    variant="primary",
                    flat=True,
                )
                yield Button(
                    Text(self._render_message(_REMOVE.bind())),
                    id=f"{_REMOVE_PREFIX}{row.frame}",
                    variant="error",
                    flat=True,
                )
        yield Button(Text(self._render_message(_OPEN.bind())), id=_OPEN_FOLDER_ID, variant="primary", flat=True)
        yield Static(
            Text(self._render_message(_HINT.bind())),
            id=_HINT_ID,
            classes="frame-row",
        )

    def on_mount(self) -> None:
        self._apply_selection()
        # The first render waits for a layout pass: at mount time the preview has
        # no size yet, so rendering now would use the width fallback and never
        # correct itself (there is no tick).
        self.call_after_refresh(self._render_preview)

    def on_show(self) -> None:
        # The pane mounts inside a hidden tab, where it has no size; showing the
        # tab lays it out, so render the preview against the real width then.
        self.call_after_refresh(self._render_preview)

    def refresh_buddy(self) -> None:
        """Re-read every row's artwork state after the buddy changed underneath."""
        if not self.is_mounted:
            return
        for frame in range(FRAME_COUNT):
            self._refresh_frame_state(frame)

    def refresh_localization(self) -> None:
        """Re-render the preview label, the per-frame state labels, buttons and the hint."""
        if not self.is_mounted:
            return
        for frame in range(FRAME_COUNT):
            self._refresh_frame_state(frame)
            self.query_one(f"#{_IMPORT_PREFIX}{frame}", Button).label = Text(self._render_message(_IMPORT.bind()))
            self.query_one(f"#{_REMOVE_PREFIX}{frame}", Button).label = Text(self._render_message(_REMOVE.bind()))
        self.query_one(f"#{_OPEN_FOLDER_ID}", Button).label = Text(self._render_message(_OPEN.bind()))
        self.query_one(f"#{_HINT_ID}", Static).update(Text(self._render_message(_HINT.bind())))
        self.query_one(f"#{_PREVIEW_LABEL_ID}", Static).update(Text(self._render_message(_PREVIEW_LABEL.bind())))

    def select_frame(self, frame: int) -> None:
        """Preview *frame* and mark its row as selected."""
        if not 0 <= frame < FRAME_COUNT or frame == self._selected_frame:
            return
        self._selected_frame = frame
        self._apply_selection()
        self._render_preview()

    async def import_into(self, frame: int, source: Path) -> None:
        """Replace one frame's artwork with the art at *source*."""
        await self._ports.import_frame(frame, source)
        self._refresh_frame_state(frame)

    async def remove_frame(self, frame: int) -> None:
        """Drop one frame's custom artwork, restoring the built-in sprite."""
        await self._ports.remove_frame(frame)
        self._refresh_frame_state(frame)

    @on(Button.Pressed)
    async def _on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        button_id = event.button.id or ""
        if button_id.startswith(_IMPORT_PREFIX):
            frame = self._parse_frame(button_id, _IMPORT_PREFIX)
            if frame is not None:
                self._pick_frame_art(frame)
        elif button_id.startswith(_REMOVE_PREFIX):
            frame = self._parse_frame(button_id, _REMOVE_PREFIX)
            if frame is not None:
                await self.remove_frame(frame)
        elif button_id == _OPEN_FOLDER_ID:
            self._ports.open_assets_dir()

    @on(Click)
    def _select_clicked_row(self, event: Click) -> None:
        """Select the frame whose row was clicked; a row's buttons must not change the selection."""
        if isinstance(event.widget, Button):
            return
        frame = self._row_frame_for(event.widget)
        if frame is not None:
            self.select_frame(frame)

    @staticmethod
    def _row_frame_for(widget: Widget | None) -> int | None:
        """Walk from the clicked widget up to its ``frame-row-<n>`` container, if any."""
        node = widget
        while node is not None:
            node_id = node.id or ""
            if node_id.startswith(_ROW_PREFIX):
                suffix = node_id.removeprefix(_ROW_PREFIX)
                if suffix.isdigit():
                    return int(suffix)
            node = node.parent
        return None

    @staticmethod
    def _parse_frame(button_id: str, prefix: str) -> int | None:
        suffix = button_id.removeprefix(prefix)
        if not suffix.isdigit():
            return None
        frame = int(suffix)
        return frame if 0 <= frame < FRAME_COUNT else None

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

    def _apply_selection(self) -> None:
        for frame in range(FRAME_COUNT):
            self.query_one(f"#{_ROW_PREFIX}{frame}", Horizontal).set_class(frame == self._selected_frame, "-selected")

    def _render_preview(self) -> None:
        if not self.is_mounted:
            return
        self.query_one(f"#{_PREVIEW_ID}", _FramePreview).show_frame(self._selected_frame)

    def _refresh_frame_state(self, frame: int) -> None:
        if not self.is_mounted:
            return
        node = self.query_one(f"#frame-state-{frame}", Static)
        node.update(Text(f"{frame}: {self._state_label(self._ports.frame_state(frame))}"))
        if frame == self._selected_frame:
            self._render_preview()

    def _state_label(self, state: FrameState) -> str:
        reference = _STATE_CUSTOM if state is FrameState.CUSTOM else _STATE_BUILTIN
        return self._render_message(reference.bind())

    def _render_message(self, reference: MessageRef) -> str:
        controller = self._locale_controller
        if controller is None:
            return format_message(reference)
        return render_str(controller.localizer, reference)
