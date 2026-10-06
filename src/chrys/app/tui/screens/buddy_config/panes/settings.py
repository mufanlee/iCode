# Copyright (c) Huawei Technologies Co., Ltd. 2026. All rights reserved.

"""The dialog's Settings tab: name, mute and reply-model controls."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalGroup
from textual.widget import Widget
from textual.widgets import Button, Label

from chrys.app.features.buddy.model import clean_name
from chrys.app.tui.i18n import render_str
from chrys.app.tui.widgets import Checkbox, EnhancedInput, Select
from chrys.foundation.i18n import MessageRef, msg
from chrys.foundation.i18n.formatting import format_message

if TYPE_CHECKING:
    from chrys.app.tui.i18n import LocaleController
    from chrys.app.tui.screens.buddy_config.ports import BuddyConfigPorts

_IDENTITY_TITLE = msg("tui.buddy_config.section.identity", fallback="Identity")
_BEHAVIOUR_TITLE = msg("tui.buddy_config.section.behaviour", fallback="Behaviour")
_NAME_LABEL = msg("tui.buddy_config.field.name", fallback="Name")
_MUTED_LABEL = msg("tui.buddy_config.field.muted", fallback="Muted")
_MODEL_LABEL = msg("tui.buddy_config.field.reply_model", fallback="Reply model")
_FOLLOW = msg("tui.buddy_config.reply_model.follow", fallback="Follow the active model")
_APPLY = msg("tui.buddy_config.action.apply", fallback="Apply")
_NAME_EMPTY = msg(
    "tui.buddy_config.toast.name_empty",
    fallback="A name has to be at least one visible character.",
)

_SECTIONS = (_IDENTITY_TITLE, _BEHAVIOUR_TITLE)


class SettingsPane(Widget):
    """Edits that commit the moment they are made."""

    DEFAULT_CSS = """
    SettingsPane {
        width: 1fr;
        height: auto;
    }
    """

    def __init__(self, ports: BuddyConfigPorts, *, locale_controller: LocaleController | None = None) -> None:
        super().__init__()
        self._ports = ports
        self._locale_controller = locale_controller

    def compose(self) -> ComposeResult:
        buddy = self._ports.buddy()
        with VerticalGroup(classes="buddy-config-section") as identity:
            identity.border_title = Text(self._render_message(_IDENTITY_TITLE.bind()))
            with Vertical(classes="buddy-config-row"), Horizontal(classes="buddy-config-row-main"):
                yield Label(
                    self._render_message(_NAME_LABEL.bind()),
                    id="buddy-config-name-label",
                    classes="buddy-config-row-label",
                )
                yield EnhancedInput(value=buddy.name if buddy is not None else "", id="buddy-config-name")
                yield Button(
                    self._render_message(_APPLY.bind()),
                    id="buddy-config-name-apply",
                    classes="buddy-config-link",
                )
        with VerticalGroup(classes="buddy-config-section") as behaviour:
            behaviour.border_title = Text(self._render_message(_BEHAVIOUR_TITLE.bind()))
            with Vertical(classes="buddy-config-row"), Horizontal(classes="buddy-config-row-main"):
                # The checkbox carries its own label, as the settings BoolRow does.
                yield Checkbox(
                    self._render_message(_MUTED_LABEL.bind()),
                    value=buddy.muted if buddy is not None else False,
                    id="buddy-config-muted",
                    classes="buddy-config-row-checkbox",
                )
            with Vertical(classes="buddy-config-row"), Horizontal(classes="buddy-config-row-main"):
                yield Label(
                    self._render_message(_MODEL_LABEL.bind()),
                    id="buddy-config-model-label",
                    classes="buddy-config-row-label",
                )
                choices = self._model_choices()
                value = self._ports.reply_model()
                # Select(allow_blank=False) rejects an initial value that is not among
                # its options: a removed or renamed profile, or a stale stored id,
                # would abort the eagerly mounted dialog. Fall back to the
                # always-present follow option.
                if value and value not in {stored for _, stored in choices}:
                    value = ""
                yield Select(choices, value=value, allow_blank=False, id="buddy-config-model")

    def _model_choices(self) -> list[tuple[str, str]]:
        """Map the ports' ``(value, label)`` pairs to Select's ``(label, value)`` ones."""
        return [
            (self._render_message(_FOLLOW.bind()) if value == "" else label, value)
            for value, label in self._ports.model_options()
        ]

    def refresh_buddy(self) -> None:
        """Resync name and mute from the ports without committing a write back.

        A plain ``Checkbox.value`` assignment runs its real watcher (so the box
        and ``-on`` class repaint) and posts ``Changed``; the guard in
        ``_toggle_muted`` makes that programmatic change a no-op because the
        checkbox now equals the port's value.
        """
        buddy = self._ports.buddy()
        if buddy is None or not self.is_mounted:
            return
        self.query_one("#buddy-config-name", EnhancedInput).value = buddy.name
        self.query_one("#buddy-config-muted", Checkbox).value = buddy.muted
        # the model Select is intentionally not resynced (see below)

    def refresh_localization(self) -> None:
        """Re-render the section titles, field labels, checkbox label and Apply button.

        The model Select is deliberately not resynced: resetting its options
        would re-post ``Changed`` and write the value back through the ports.
        Its labels therefore keep whatever locale was current when it opened --
        a chosen residual, not an API limitation.
        """
        if not self.is_mounted:
            return
        sections = self.query(".buddy-config-section")
        for group, definition in zip(sections, _SECTIONS, strict=True):
            group.border_title = Text(self._render_message(definition.bind()))
        self.query_one("#buddy-config-name-label", Label).update(Text(self._render_message(_NAME_LABEL.bind())))
        self.query_one("#buddy-config-muted", Checkbox).label = self._render_message(_MUTED_LABEL.bind())
        self.query_one("#buddy-config-model-label", Label).update(Text(self._render_message(_MODEL_LABEL.bind())))
        self.query_one("#buddy-config-name-apply", Button).label = Text(self._render_message(_APPLY.bind()))

    async def commit_name(self, value: str) -> None:
        """Apply a typed name. A name that cleans to nothing is refused."""
        if not clean_name(value):
            self._ports.notify(self._render_message(_NAME_EMPTY.bind()), severity="warning", timeout=10)
            return
        await self._ports.rename(value)

    @on(Button.Pressed, "#buddy-config-name-apply")
    async def _apply_name(self) -> None:
        await self.commit_name(self.query_one("#buddy-config-name", EnhancedInput).value)

    @on(EnhancedInput.Submitted, "#buddy-config-name")
    async def _submit_name(self) -> None:
        await self.commit_name(self.query_one("#buddy-config-name", EnhancedInput).value)

    @on(Select.Changed, "#buddy-config-model")
    async def _select_model(self, event: Select.Changed) -> None:
        value = str(event.value)
        if value == self._ports.reply_model():
            return
        await self._ports.set_reply_model(value)

    @on(Checkbox.Changed, "#buddy-config-muted")
    async def _toggle_muted(self, event: Checkbox.Changed) -> None:
        buddy = self._ports.buddy()
        if buddy is not None and event.value == buddy.muted:
            return  # programmatic resync, not a user edit
        await self._ports.set_muted(event.value)

    def _render_message(self, reference: MessageRef) -> str:
        controller = self._locale_controller
        if controller is None:
            return format_message(reference)
        return render_str(controller.localizer, reference)
