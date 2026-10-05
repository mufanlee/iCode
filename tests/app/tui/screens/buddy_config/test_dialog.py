# Copyright (c) Huawei Technologies Co., Ltd. 2026. All rights reserved.

"""The Buddy configuration dialog renders and reflects port state."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Input, Select, Switch

from chrys.app.tui.theme import TuiVariableDefaultsMixin
from tests.app.tui.screens.buddy_config.support import StubPorts
from tests.support.tui_helpers import click_when_settled
from tests.support.waiting import wait_for


def test_profile_pane_shows_the_buddy_name() -> None:
    from chrys.app.tui.screens.buddy_config.panes.profile import ProfilePane

    ports = StubPorts()
    pane = ProfilePane(ports, locale_controller=None)
    rendered = pane.render_body()
    assert ports.buddy().name in rendered


def test_profile_pane_empty_state_shows_the_hatch_hint() -> None:
    from chrys.app.tui.screens.buddy_config.panes.profile import ProfilePane

    pane = ProfilePane(StubPorts(_buddy=None), locale_controller=None)
    assert "Nothing has hatched yet" in pane.render_body()


async def test_profile_pane_parks_its_portrait_timer_while_hidden() -> None:
    """A pane mounted inside a hidden container never gets Show, so its first tick parks the timer."""
    from chrys.app.tui.screens.buddy_config.panes.profile import ProfilePane

    class ProfilePaneApp(TuiVariableDefaultsMixin, App[None]):
        def compose(self) -> ComposeResult:
            container = Container(ProfilePane(StubPorts(), locale_controller=None))
            container.display = False
            yield container

    async with ProfilePaneApp().run_test(size=(60, 24)) as pilot:
        pane = pilot.app.query_one(ProfilePane)
        timer = pane._timer
        assert timer is not None
        await wait_for(
            lambda: not timer._active.is_set(),
            pilot=pilot,
            description="the hidden pane parks its portrait timer",
        )

        pilot.app.query_one(Container).display = True
        await wait_for(timer._active.is_set, pilot=pilot, description="Show restarts the portrait timer")


async def test_settings_pane_commits_a_rename() -> None:
    from chrys.app.tui.screens.buddy_config.panes.settings import SettingsPane

    ports = StubPorts()
    pane = SettingsPane(ports, locale_controller=None)

    await pane.commit_name("Mochi")

    assert ("rename", "Mochi") in ports.calls


async def test_settings_pane_rejects_an_empty_name() -> None:
    from chrys.app.tui.screens.buddy_config.panes.settings import SettingsPane

    ports = StubPorts()
    pane = SettingsPane(ports, locale_controller=None)

    await pane.commit_name("   ")

    assert ("rename", "   ") not in ports.calls
    assert any(kind == "notify" for kind, _ in ports.calls)


def _settings_pane_app(ports: StubPorts) -> App[None]:
    from chrys.app.tui.screens.buddy_config.panes.settings import SettingsPane

    class SettingsPaneApp(TuiVariableDefaultsMixin, App[None]):
        # The dialog supplies this layout; the bare harness needs it so the
        # Apply button sits beside the Input instead of off the right edge.
        CSS = "#buddy-config-name { width: 1fr; }"

        def compose(self) -> ComposeResult:
            yield SettingsPane(ports, locale_controller=None)

    return SettingsPaneApp()


async def test_settings_pane_wires_controls_without_writing_on_mount() -> None:
    """Mounting posts the Select's initial value; it must not be written back."""
    ports = StubPorts(model_choices=[("", "Follow active"), ("m", "M")])

    async with _settings_pane_app(ports).run_test(size=(80, 24)) as pilot:
        await wait_for(
            lambda: list(pilot.app.query("#buddy-config-model")),
            pilot=pilot,
            description="the settings pane mounts its model select",
        )
        assert not any(kind in {"model", "muted"} for kind, _ in ports.calls)

        name = pilot.app.query_one("#buddy-config-name", Input)
        name.value = "Mochi"
        await click_when_settled(pilot, "#buddy-config-name-apply")
        await wait_for(
            lambda: ("rename", "Mochi") in ports.calls,
            pilot=pilot,
            description="applying the name renames the buddy",
        )

        switch = pilot.app.query_one("#buddy-config-muted", Switch)
        muted = not switch.value
        switch.value = muted
        await wait_for(
            lambda: ("muted", muted) in ports.calls,
            pilot=pilot,
            description="toggling the switch writes the muted flag",
        )

        pilot.app.query_one("#buddy-config-model", Select).value = "m"
        await wait_for(
            lambda: ("model", "m") in ports.calls,
            pilot=pilot,
            description="picking a model writes the reply model",
        )


async def test_settings_pane_falls_back_when_the_reply_model_is_stale() -> None:
    """A stored model id that is no longer offered must not abort the mount."""
    ports = StubPorts(reply_model_value="gone", model_choices=[("", "Follow active"), ("m", "M")])

    async with _settings_pane_app(ports).run_test(size=(80, 24)) as pilot:
        select = pilot.app.query_one("#buddy-config-model", Select)
        await wait_for(
            lambda: str(select.value) == "" and ("model", "") in ports.calls,
            pilot=pilot,
            description="the stale reply model falls back to follow and heals the stored id",
        )


def test_model_choices_relabels_the_empty_value() -> None:
    from chrys.app.tui.screens.buddy_config.panes.settings import SettingsPane

    ports = StubPorts(model_choices=[("", "Follow active"), ("m", "M")])
    pane = SettingsPane(ports, locale_controller=None)

    assert pane._model_choices() == [("Follow the active model", ""), ("M", "m")]


async def test_appearance_import_uses_the_picker_result() -> None:
    from pathlib import Path

    from chrys.app.tui.screens.buddy_config.panes.appearance import AppearancePane

    ports = StubPorts()
    pane = AppearancePane(ports, locale_controller=None)

    await pane.import_into(2, Path("/tmp/art.png"))

    assert ("import", (2, Path("/tmp/art.png"))) in ports.calls


async def test_appearance_remove() -> None:
    from chrys.app.tui.screens.buddy_config.panes.appearance import AppearancePane

    ports = StubPorts()
    pane = AppearancePane(ports, locale_controller=None)

    await pane.remove_frame(4)

    assert ("remove", 4) in ports.calls


def _appearance_pane_app(ports: StubPorts) -> App[None]:
    from chrys.app.tui.screens.buddy_config.panes.appearance import AppearancePane

    class AppearancePaneApp(TuiVariableDefaultsMixin, App[None]):
        def compose(self) -> ComposeResult:
            yield AppearancePane(ports, locale_controller=None)

    return AppearancePaneApp()


async def test_appearance_buttons_route_to_ports() -> None:
    from textual.widgets import Button

    ports = StubPorts()

    async with _appearance_pane_app(ports).run_test(size=(60, 30)) as pilot:
        pilot.app.query_one("#frame-remove-3", Button).press()
        pilot.app.query_one("#buddy-config-open-folder", Button).press()
        await wait_for(
            lambda: ("remove", 3) in ports.calls and ("open_dir", None) in ports.calls,
            pilot=pilot,
            description="dispatcher routes frame buttons to ports",
        )


async def test_appearance_import_button_opens_the_picker() -> None:
    from textual.widgets import Button

    from chrys.app.tui.screens.dialogs.file_picker import FilePicker

    ports = StubPorts()

    async with _appearance_pane_app(ports).run_test(size=(60, 30)) as pilot:
        pilot.app.query_one("#frame-import-2", Button).press()
        await wait_for(
            lambda: isinstance(pilot.app.screen, FilePicker),
            pilot=pilot,
            description="the import button opens the frame artwork picker",
        )


async def test_appearance_shows_custom_state_for_an_imported_frame() -> None:
    from textual.widgets import Static

    ports = StubPorts(custom_frames={4})

    async with _appearance_pane_app(ports).run_test(size=(60, 30)) as pilot:
        node = pilot.app.query_one("#frame-state-4", Static)
        assert "Custom" in str(node.content)


async def test_appearance_refreshes_a_row_state_after_import() -> None:
    from pathlib import Path

    from textual.widgets import Static

    from chrys.app.tui.screens.buddy_config.panes.appearance import AppearancePane

    ports = StubPorts()

    async with _appearance_pane_app(ports).run_test(size=(60, 30)) as pilot:
        pane = pilot.app.query_one(AppearancePane)
        node = pilot.app.query_one("#frame-state-2", Static)
        assert "Built-in" in str(node.content)

        ports.custom_frames = {2}
        await pane.import_into(2, Path("/tmp/art.png"))

        assert "Custom" in str(node.content)


def test_appearance_lists_six_frames() -> None:
    from chrys.app.features.buddy.animation import FRAME_COUNT
    from chrys.app.tui.screens.buddy_config.panes.appearance import AppearancePane

    assert FRAME_COUNT == 6
    pane = AppearancePane(StubPorts(), locale_controller=None)
    assert len(pane.frame_rows()) == 6
