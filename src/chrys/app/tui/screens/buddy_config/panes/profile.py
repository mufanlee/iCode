# Copyright (c) Huawei Technologies Co., Ltd. 2026. All rights reserved.
#
"""The dialog's Profile tab: a live portrait beside the buddy's read-only facts."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Self

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button, Static

from chrys.app.features.buddy.commands import buddy_card
from chrys.app.features.buddy.portrait import PORTRAIT_WIDTH
from chrys.app.tui.i18n import render_str
from chrys.app.tui.util.visibility import is_widget_shown_on_active_screen
from chrys.foundation.i18n import MessageRef, msg
from chrys.foundation.i18n.formatting import format_message

if TYPE_CHECKING:
    from textual.geometry import Region
    from textual.timer import Timer

    from chrys.app.tui.i18n import LocaleController
    from chrys.app.tui.screens.buddy_config.ports import BuddyConfigPorts

_EMPTY_HINT = msg(
    "tui.buddy_config.empty.hint",
    fallback="Nothing has hatched yet.\n\n/buddy hatch finds out what is in the egg.",
    multiline=True,
)
_HATCH = msg("tui.buddy_config.action.hatch", fallback="Hatch")

# The buddy command's no-buddy intro (tui.buddy.intro_no_buddy) draws this same
# glyph; it is not exposed as a standalone constant, so the empty state renders
# it directly.
_EGG = "🥚"

_PORTRAIT_TICK_SECONDS = 1 / 8


class ProfilePane(Widget):
    """Read-only buddy facts, plus a portrait that animates while shown."""

    DEFAULT_CSS = """
    ProfilePane { width: 1fr; height: 1fr; align-vertical: middle; }
    /* Each element gets its own full-width row so it is centred on its OWN width:
       a vertical container's align centres the widest child's column and
       left-aligns narrower siblings, so the 24-wide portrait would otherwise
       sit at the 66-wide fact sheet's left edge. A single-child row defines the
       column itself, so that child lands truly centred. */
    ProfilePane Horizontal { width: 1fr; height: auto; align: center top; }
    /* Portrait size mirrors features/buddy/portrait.py: PORTRAIT_WIDTH = PIXEL_WIDTH + 4 = 24,
       PORTRAIT_HEIGHT = PIXEL_HEIGHT // 2 + 3 = 11. A fixed size lets a tick repaint in
       place instead of re-laying out (a bare width or height:auto would). */
    ProfilePane #buddy-config-portrait { width: 24; height: 11; }
    /* auto width (not full-bleed) so the fact sheet and the hint read as a centered
       block rather than hugging the left edge; the block keeps its internal alignment. */
    ProfilePane #buddy-config-facts { width: auto; height: auto; }
    ProfilePane #buddy-config-hatch { width: auto; }
    """

    class Hatched(Message):
        """Posted once the inline hatch button has landed a buddy."""

    def __init__(self, ports: BuddyConfigPorts, *, locale_controller: LocaleController | None = None) -> None:
        super().__init__()
        self._ports = ports
        self._locale_controller = locale_controller
        self._timer: Timer | None = None
        self._portrait: _BuddyPortrait | None = None

    def compose(self) -> ComposeResult:
        with Horizontal(id="buddy-config-portrait-row"):
            yield _BuddyPortrait(self._ports, id="buddy-config-portrait")
        with Horizontal(id="buddy-config-facts-row"):
            yield Static("", id="buddy-config-facts")
        with Horizontal(id="buddy-config-hatch-row"):
            yield Button(
                Text(self._render_message(_HATCH.bind())),
                id="buddy-config-hatch",
                classes="buddy-config-link",
            )

    def render_body(self) -> str:
        """The pane's plain-text body."""
        buddy = self._ports.buddy()
        if buddy is None:
            return self._render_message(_EMPTY_HINT.bind())
        return buddy_card(buddy, render=self._render_message)

    def on_mount(self) -> None:
        self.query_one("#buddy-config-facts", Static).update(Text(self.render_body()))
        self._sync_empty_state()
        self._portrait = self.query_one(_BuddyPortrait)
        self._timer = self.set_interval(_PORTRAIT_TICK_SECONDS, self._tick)
        # Paint the first frame (or the egg) unconditionally: the animation tick
        # below is visibility-gated and may not run before the first interval.
        self._portrait.draw()
        # A pane mounted inside a hidden container never receives Show, so the
        # first tick parks the timer until an on_show resumes it.
        self._tick()

    def on_show(self) -> None:
        if self._timer is not None:
            self._timer.resume()

    def on_hide(self) -> None:
        if self._timer is not None:
            self._timer.pause()

    def refresh_buddy(self) -> None:
        """Repaint the facts and the portrait after the buddy changed underneath."""
        if not self.is_mounted:
            return
        self.query_one("#buddy-config-facts", Static).update(Text(self.render_body()))
        self._sync_empty_state()
        if self._portrait is not None:
            self._portrait.draw()
        self._tick()

    def refresh_localization(self) -> None:
        """Re-render the facts; its labels resolve through the live localizer."""
        if not self.is_mounted:
            return
        self.query_one("#buddy-config-facts", Static).update(Text(self.render_body()))
        self.query_one("#buddy-config-hatch", Button).label = Text(self._render_message(_HATCH.bind()))

    @on(Button.Pressed, "#buddy-config-hatch")
    async def _on_hatch_pressed(self) -> None:
        button = self.query_one("#buddy-config-hatch", Button)
        if button.disabled:
            return  # a hatch is already in flight
        button.disabled = True
        try:
            await self._ports.hatch()
        finally:
            button.disabled = False
        self.post_message(self.Hatched())

    def _sync_empty_state(self) -> None:
        """Show the inline hatch button only while no buddy has hatched."""
        self.query_one("#buddy-config-hatch", Button).display = self._ports.buddy() is None

    def _tick(self) -> None:
        if not is_widget_shown_on_active_screen(self):
            if self._timer is not None:
                self._timer.pause()
            return
        if self._portrait is not None:
            self._portrait.tick()

    def _render_message(self, reference: MessageRef) -> str:
        controller = self._locale_controller
        if controller is None:
            return format_message(reference)
        return render_str(controller.localizer, reference)


class _BuddyPortrait(Static):
    """A portrait that repaints itself on a fixed cadence."""

    def __init__(self, ports: BuddyConfigPorts, **kwargs: Any) -> None:
        super().__init__("", **kwargs)
        self._ports = ports
        self._tick_count = 0

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

    def draw(self) -> None:
        """Paint the current idle frame in place, or the egg when there is no buddy."""
        from chrys.app.features.buddy.animation import get_idle_frame
        from chrys.app.features.buddy.portrait import render_portrait

        buddy = self._ports.buddy()
        if buddy is None:
            self.update(Text(_EGG), layout=False)
            return
        frame, blink = get_idle_frame(buddy.species, self._tick_count)
        # content_size resolves region through the compositor and can arrange
        # the entire screen. outer_size is the latest cached layout size.
        _base_background, background = self.background_colors
        width = max(0, self.outer_size.width - self.styles.gutter.width)
        lines = render_portrait(
            buddy.appearance,
            buddy.display_name,
            frame,
            blink,
            width=width or PORTRAIT_WIDTH,
            effect_tick=self._tick_count,
            bg_rgb=None if self.app.current_theme.ansi else background.rgb,
        )
        # The portrait size is fixed by CSS; frames only repaint. layout=True
        # here would force a full-screen arrange per animation tick.
        self.update(Text("\n").join(lines), layout=False)

    def tick(self) -> None:
        """Advance the idle animation and paint the next frame."""
        self.draw()
        self._tick_count += 1
