# Copyright (c) Huawei Technologies Co., Ltd. 2026. All rights reserved.

"""The dialog's Profile tab: a live portrait beside the buddy's read-only facts."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

from chrys.app.features.buddy.commands import buddy_card
from chrys.app.tui.i18n import render_str
from chrys.foundation.i18n import MessageRef, msg
from chrys.foundation.i18n.formatting import format_message

if TYPE_CHECKING:
    from chrys.app.tui.i18n import LocaleController
    from chrys.app.tui.screens.buddy_config.ports import BuddyConfigPorts

_EMPTY_HINT = msg(
    "tui.buddy_config.empty.hint",
    fallback="Nothing has hatched yet.\n\n/buddy hatch finds out what is in the egg.",
    multiline=True,
)

_PORTRAIT_TICK_SECONDS = 1 / 8


class ProfilePane(Widget):
    """Read-only buddy facts, plus a portrait that animates while shown."""

    DEFAULT_CSS = """
    ProfilePane { height: 1fr; }
    ProfilePane #buddy-config-portrait { width: 32; height: auto; }
    ProfilePane #buddy-config-facts { height: auto; }
    """

    def __init__(self, ports: BuddyConfigPorts, *, locale_controller: LocaleController | None = None) -> None:
        super().__init__()
        self._ports = ports
        self._locale_controller = locale_controller

    def compose(self) -> ComposeResult:
        yield _BuddyPortrait(self._ports, id="buddy-config-portrait")
        yield Static("", id="buddy-config-facts")

    def render_body(self) -> str:
        """The fact sheet as plain text (used by tests and the title bar)."""
        buddy = self._ports.buddy()
        if buddy is None:
            return self._render_message(_EMPTY_HINT.bind())
        return buddy_card(buddy, render=self._render_message)

    def on_mount(self) -> None:
        self.query_one("#buddy-config-facts", Static).update(Text(self.render_body()))
        self.set_interval(_PORTRAIT_TICK_SECONDS, self._tick)

    def _tick(self) -> None:
        self.query_one(_BuddyPortrait).tick()

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

    def tick(self) -> None:
        from chrys.app.features.buddy.animation import get_idle_frame
        from chrys.app.features.buddy.portrait import PORTRAIT_WIDTH, render_portrait

        buddy = self._ports.buddy()
        if buddy is None:
            self.update(Text(""))
            return
        frame, blink = get_idle_frame(buddy.species, self._tick_count)
        self._tick_count += 1
        lines = render_portrait(
            buddy.appearance,
            buddy.display_name,
            frame,
            blink,
            width=self.content_size.width or PORTRAIT_WIDTH,
            effect_tick=self._tick_count,
        )
        self.update(Text("\n").join(lines))
