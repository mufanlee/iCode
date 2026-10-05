# Copyright (c) Huawei Technologies Co., Ltd. 2026. All rights reserved.

"""The Buddy configuration dialog: a tabbed modal over the ports."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from rich.text import Text
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.content import Content
from textual.widgets import Button, TabbedContent, TabPane

from chrys.app.tui.binding_display import CLOSE_BINDING, localized_binding
from chrys.app.tui.i18n import render_str
from chrys.app.tui.screens.buddy_config.panes.appearance import AppearancePane
from chrys.app.tui.screens.buddy_config.panes.profile import ProfilePane
from chrys.app.tui.screens.buddy_config.panes.settings import SettingsPane
from chrys.app.tui.screens.dialogs.base import BaseDialog
from chrys.foundation.i18n import MessageRef, msg
from chrys.foundation.i18n.formatting import format_message

if TYPE_CHECKING:
    from chrys.app.tui.i18n import LocaleController
    from chrys.app.tui.screens.buddy_config.ports import BuddyConfigPorts

PROFILE_TAB_ID = "buddy-config-tab-profile"
APPEARANCE_TAB_ID = "buddy-config-tab-appearance"
SETTINGS_TAB_ID = "buddy-config-tab-settings"

_TITLE = msg("tui.buddy_config.title", fallback="Buddy")
_TAB_PROFILE = msg("tui.buddy_config.tab.profile", fallback="Profile")
_TAB_APPEARANCE = msg("tui.buddy_config.tab.appearance", fallback="Appearance")
_TAB_SETTINGS = msg("tui.buddy_config.tab.settings", fallback="Settings")
_REHATCH = msg("tui.buddy_config.action.rehatch", fallback="Re-hatch")
_CLOSE = msg("tui.buddy_config.action.close", fallback="Close")
_STATUS = msg("tui.buddy_config.status.autosave", fallback="Changes are saved as you make them")
_REHATCH_CONFIRM = msg(
    "tui.buddy_config.rehatch.confirm",
    fallback=(
        "Re-hatch replaces your buddy with a fresh random draw. "
        "Its species, rarity, traits and progress cannot be recovered."
    ),
)


class BuddyConfigDialog(BaseDialog[None]):
    """See a buddy and make the changes the design permits."""

    CSS_PATH = "dialog.tcss"

    BINDINGS: ClassVar[list] = [localized_binding("escape", "close", CLOSE_BINDING, show=False, priority=True)]

    def __init__(self, ports: BuddyConfigPorts, *, locale_controller: LocaleController | None = None) -> None:
        super().__init__()
        self._ports = ports
        self._locale_controller = locale_controller

    @property
    def active_tab(self) -> str:
        """The id of the tab the dialog currently shows."""
        return self.query_one(TabbedContent).active

    def compose(self) -> ComposeResult:
        has_buddy = self._ports.buddy() is not None
        with TabbedContent(initial=PROFILE_TAB_ID, id="buddy-config-tabs") as tabs:
            tabs.border_title = Text(self._render_message(_TITLE.bind()))
            with TabPane(self._tab_label(_TAB_PROFILE.bind()), id=PROFILE_TAB_ID):
                yield ProfilePane(self._ports, locale_controller=self._locale_controller)
            if has_buddy:
                with TabPane(self._tab_label(_TAB_APPEARANCE.bind()), id=APPEARANCE_TAB_ID):
                    yield AppearancePane(self._ports, locale_controller=self._locale_controller)
                with TabPane(self._tab_label(_TAB_SETTINGS.bind()), id=SETTINGS_TAB_ID):
                    yield SettingsPane(self._ports, locale_controller=self._locale_controller)
        with Horizontal(id="buddy-config-footer"):
            yield Button(
                Text(self._render_message(_REHATCH.bind())),
                id="buddy-config-rehatch",
                variant="error",
                disabled=not has_buddy,
            )
            yield Button(Text(self._render_message(_CLOSE.bind())), id="buddy-config-close")
            yield Button(Text(self._render_message(_STATUS.bind())), id="buddy-config-status", disabled=True)

    def action_close(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#buddy-config-close")
    def _on_close_pressed(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#buddy-config-rehatch")
    def _on_rehatch_pressed(self) -> None:
        from chrys.app.tui.screens.dialogs.confirm import ConfirmDialog

        dialog = ConfirmDialog(
            title=self._render_message(_REHATCH.bind()),
            message=self._render_message(_REHATCH_CONFIRM.bind()),
            confirm_label=self._render_message(_REHATCH.bind()),
            confirm_variant="error",
            locale_controller=self._locale_controller,
        )
        self.app.push_screen(dialog, self._rehatch_if_confirmed)

    def _rehatch_if_confirmed(self, confirmed: bool | None) -> None:
        if confirmed:
            self._run_rehatch()

    @work(thread=False)
    async def _run_rehatch(self) -> None:
        await self._ports.rehatch()

    def _tab_label(self, reference: MessageRef) -> Content:
        """A tab caption as literal content; a translated label is never markup."""
        return Content.from_text(self._render_message(reference), markup=False)

    def _render_message(self, reference: MessageRef) -> str:
        controller = self._locale_controller
        if controller is None:
            return format_message(reference)
        return render_str(controller.localizer, reference)
