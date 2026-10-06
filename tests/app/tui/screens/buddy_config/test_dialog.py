# Copyright (c) Huawei Technologies Co., Ltd. 2026. All rights reserved.

"""The Buddy configuration dialog renders and reflects port state."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Input, Select, Switch

from chrys.app.tui.theme import TuiVariableDefaultsMixin
from chrys.app.tui.widgets import Checkbox, EnhancedInput
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
    from pathlib import Path

    from textual.containers import VerticalGroup

    import chrys.app.tui.screens.buddy_config.dialog as buddy_dialog
    from chrys.app.tui.screens.buddy_config.panes.settings import SettingsPane

    # The row/control styling lives in the dialog stylesheet, scoped to the
    # container, so mount the pane the way the dialog does.
    css_path = Path(buddy_dialog.__file__).with_name("dialog.tcss")

    class SettingsPaneApp(TuiVariableDefaultsMixin, App[None]):
        CSS_PATH = str(css_path)

        def compose(self) -> ComposeResult:
            with VerticalGroup(id="buddy-config-container"):
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

        checkbox = pilot.app.query_one("#buddy-config-muted", Checkbox)
        muted = not checkbox.value
        checkbox.value = muted
        await wait_for(
            lambda: ("muted", muted) in ports.calls,
            pilot=pilot,
            description="toggling the checkbox writes the muted flag",
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


async def test_dialog_opens_on_the_profile_tab(tmp_path) -> None:
    from chrys.app.tui.screens.buddy_config import BuddyConfigDialog
    from tests.support.tui_app_harness import make_chrys_app
    from tests.support.waiting import wait_for

    app = make_chrys_app(tmp_path)
    ports = StubPorts()

    async with app.run_test() as pilot:
        await pilot.pause()
        dialog = BuddyConfigDialog(ports, locale_controller=None)
        app.push_screen(dialog)
        await wait_for(lambda: app.screen is dialog and dialog.is_mounted, pilot=pilot, description="dialog mounted")

        assert dialog.active_tab == "buddy-config-tab-profile"
        await pilot.press("escape")
        await wait_for(lambda: app.screen is not dialog, pilot=pilot, description="dialog closed")


async def test_dialog_frames_the_tabs_and_buttons_in_one_centered_container(tmp_path) -> None:
    """The dialog is one centred, bordered box holding the tabs and the buttons."""
    from textual.containers import VerticalGroup
    from textual.widgets import TabbedContent

    from chrys.app.tui.screens.buddy_config import BuddyConfigDialog
    from tests.support.tui_app_harness import make_chrys_app

    app = make_chrys_app(tmp_path)
    ports = StubPorts()

    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        dialog = BuddyConfigDialog(ports, locale_controller=None)
        app.push_screen(dialog)
        await wait_for(lambda: dialog.is_mounted, pilot=pilot, description="dialog mounted")

        # One bordered container carries the frame and its title; the tabs no
        # longer do, and no sibling footer sits outside the box.
        container = dialog.query_one("#buddy-config-container", VerticalGroup)
        assert container.border_title is not None
        assert dialog.query_one("#buddy-config-tabs", TabbedContent).border_title is None
        assert list(dialog.query("#buddy-config-footer")) == []

        # The tabbed content is contained by the framed box.
        tabs = dialog.query_one("#buddy-config-tabs", TabbedContent)
        assert container.region.contains_region(tabs.region)

        # Defect 1: the container is centred in the screen (equal side margins).
        screen = dialog.region
        left_margin = container.region.x - screen.x
        right_margin = screen.right - container.region.right
        assert left_margin > 0
        assert left_margin == right_margin

        await pilot.press("escape")
        await wait_for(lambda: app.screen is not dialog, pilot=pilot, description="dialog closed")


async def test_profile_content_is_horizontally_centered(tmp_path) -> None:
    """Each Profile element is centred on its own width, not aligned to its widest sibling.

    A vertical container's align centres the widest child's column and left-aligns
    narrower siblings, so the 24-wide portrait used to sit at the 66-wide fact
    sheet's left edge. Giving each element its own single-child row fixes that.
    """
    from textual.widgets import Static

    from chrys.app.tui.screens.buddy_config import BuddyConfigDialog
    from chrys.app.tui.screens.buddy_config.panes.profile import ProfilePane
    from tests.support.tui_app_harness import make_chrys_app

    app = make_chrys_app(tmp_path)
    ports = StubPorts()

    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        dialog = BuddyConfigDialog(ports, locale_controller=None)
        app.push_screen(dialog)
        await wait_for(lambda: dialog.is_mounted, pilot=pilot, description="dialog mounted")
        await pilot.pause()

        pane = dialog.query_one(ProfilePane)
        portrait = dialog.query_one("#buddy-config-portrait", Static)
        facts = dialog.query_one("#buddy-config-facts", Static)

        pane_center = pane.content_region.x + pane.content_region.width // 2
        assert abs((portrait.region.x + portrait.region.width // 2) - pane_center) <= 1
        assert abs((facts.region.x + facts.region.width // 2) - pane_center) <= 1
        # The narrower portrait now sits centred OVER the wider facts block rather
        # than pinned to its left edge — exactly what was broken.
        assert portrait.region.x > facts.region.x
        # The block is centred VERTICALLY too: equal slack above the portrait and
        # below the facts.
        top_gap = portrait.region.y - pane.content_region.y
        bottom_gap = pane.content_region.bottom - facts.region.bottom
        assert top_gap > 0
        assert abs(top_gap - bottom_gap) <= 1

        await pilot.press("escape")
        await wait_for(lambda: app.screen is not dialog, pilot=pilot, description="dialog closed")


async def test_profile_empty_state_hatch_is_horizontally_centered(tmp_path) -> None:
    from textual.widgets import Button

    from chrys.app.tui.screens.buddy_config import BuddyConfigDialog
    from chrys.app.tui.screens.buddy_config.panes.profile import ProfilePane
    from tests.support.tui_app_harness import make_chrys_app

    app = make_chrys_app(tmp_path)
    ports = StubPorts(_buddy=None)

    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        dialog = BuddyConfigDialog(ports, locale_controller=None)
        app.push_screen(dialog)
        await wait_for(lambda: dialog.is_mounted, pilot=pilot, description="dialog mounted")
        await pilot.pause()

        pane = dialog.query_one(ProfilePane)
        hatch = dialog.query_one("#buddy-config-hatch", Button)
        assert hatch.display

        pane_center = pane.content_region.x + pane.content_region.width // 2
        assert abs((hatch.region.x + hatch.region.width // 2) - pane_center) <= 1


async def test_dialog_without_a_buddy_offers_only_the_profile_tab(tmp_path) -> None:
    from textual.widgets import TabbedContent

    from chrys.app.tui.screens.buddy_config import BuddyConfigDialog
    from chrys.app.tui.screens.buddy_config.panes.appearance import AppearancePane
    from chrys.app.tui.screens.buddy_config.panes.profile import ProfilePane
    from chrys.app.tui.screens.buddy_config.panes.settings import SettingsPane
    from tests.support.tui_app_harness import make_chrys_app

    app = make_chrys_app(tmp_path)
    ports = StubPorts(_buddy=None)

    async with app.run_test(size=(110, 40)) as pilot:
        await pilot.pause()
        dialog = BuddyConfigDialog(ports, locale_controller=None)
        app.push_screen(dialog)
        await wait_for(lambda: app.screen is dialog and dialog.is_mounted, pilot=pilot, description="dialog mounted")

        assert dialog.query_one(TabbedContent).tab_count == 1
        assert len(dialog.query(ProfilePane)) == 1
        assert list(dialog.query(AppearancePane)) == []
        assert list(dialog.query(SettingsPane)) == []


async def test_dialog_empty_state_shows_the_egg_and_hatches_inline(tmp_path) -> None:
    from textual.widgets import Button, Static

    from chrys.app.tui.screens.buddy_config import BuddyConfigDialog
    from tests.support.tui_app_harness import make_chrys_app

    app = make_chrys_app(tmp_path)
    ports = StubPorts(_buddy=None)

    async with app.run_test(size=(110, 40)) as pilot:
        await pilot.pause()
        dialog = BuddyConfigDialog(ports, locale_controller=None)
        app.push_screen(dialog)
        await wait_for(lambda: dialog.is_mounted, pilot=pilot, description="dialog mounted")

        # The portrait area shows the egg while there is no buddy.
        portrait = dialog.query_one("#buddy-config-portrait", Static)
        assert "🥚" in str(portrait.content)

        hatch = dialog.query_one("#buddy-config-hatch", Button)
        assert hatch.display

        await click_when_settled(pilot, "#buddy-config-hatch")
        await wait_for(
            lambda: ("hatch", None) in ports.calls,
            pilot=pilot,
            description="the inline hatch button hatches a buddy",
        )


async def test_dialog_reflects_a_freshly_hatched_buddy(tmp_path) -> None:
    from textual.widgets import Button, Static, TabbedContent

    from chrys.app.tui.screens.buddy_config import BuddyConfigDialog
    from chrys.app.tui.screens.buddy_config.panes.appearance import AppearancePane
    from chrys.app.tui.screens.buddy_config.panes.settings import SettingsPane
    from tests.support.tui_app_harness import make_chrys_app

    app = make_chrys_app(tmp_path)
    ports = StubPorts(_buddy=None)

    async with app.run_test(size=(110, 40)) as pilot:
        await pilot.pause()
        dialog = BuddyConfigDialog(ports, locale_controller=None)
        app.push_screen(dialog)
        await wait_for(lambda: dialog.is_mounted, pilot=pilot, description="dialog mounted")

        await click_when_settled(pilot, "#buddy-config-hatch")
        await wait_for(
            lambda: ports.buddy() is not None and dialog.query_one(TabbedContent).tab_count == 3,
            pilot=pilot,
            description="the hatch lands a buddy and adds the buddy-only tabs",
        )

        # Appending the buddy-only tabs must not steal the active tab.
        assert dialog.active_tab == "buddy-config-tab-profile"
        assert len(dialog.query(AppearancePane)) == 1
        assert len(dialog.query(SettingsPane)) == 1
        # The empty hint gives way to the fresh buddy's facts.
        assert ports.buddy().name in str(dialog.query_one("#buddy-config-facts", Static).content)
        assert not dialog.query_one("#buddy-config-hatch", Button).display


async def test_dialog_hatch_that_yields_no_buddy_keeps_the_empty_state(tmp_path) -> None:
    from textual.widgets import Button, TabbedContent

    from chrys.app.tui.screens.buddy_config import BuddyConfigDialog
    from tests.support.tui_app_harness import make_chrys_app

    class _BarrenPorts(StubPorts):
        """A hatch that records the attempt but leaves no buddy behind."""

        async def hatch(self) -> None:
            self.calls.append(("hatch", None))

    app = make_chrys_app(tmp_path)
    ports = _BarrenPorts(_buddy=None)

    async with app.run_test(size=(110, 40)) as pilot:
        await pilot.pause()
        dialog = BuddyConfigDialog(ports, locale_controller=None)
        app.push_screen(dialog)
        await wait_for(lambda: dialog.is_mounted, pilot=pilot, description="dialog mounted")

        hatch = dialog.query_one("#buddy-config-hatch", Button)
        await click_when_settled(pilot, "#buddy-config-hatch")
        await wait_for(
            lambda: ("hatch", None) in ports.calls,
            pilot=pilot,
            description="the inline hatch button records the attempt",
        )
        await pilot.pause()

        # A hatch that lands nothing must not mount the buddy-only tabs or
        # disable the hatch button.
        assert dialog.query_one(TabbedContent).tab_count == 1
        assert hatch.display
        assert not hatch.disabled


async def test_dialog_switches_tabs_by_clicking_a_header(tmp_path) -> None:
    from textual.widgets import TabbedContent

    from chrys.app.tui.screens.buddy_config import BuddyConfigDialog
    from chrys.app.tui.screens.buddy_config.dialog import PROFILE_TAB_ID, SETTINGS_TAB_ID
    from tests.support.tui_app_harness import make_chrys_app

    app = make_chrys_app(tmp_path)
    ports = StubPorts()

    async with app.run_test(size=(110, 40)) as pilot:
        await pilot.pause()
        dialog = BuddyConfigDialog(ports, locale_controller=None)
        app.push_screen(dialog)
        await wait_for(lambda: app.screen is dialog and dialog.is_mounted, pilot=pilot, description="dialog mounted")

        tabs = dialog.query_one(TabbedContent)
        assert dialog.active_tab == PROFILE_TAB_ID

        await click_when_settled(pilot, tabs.get_tab(SETTINGS_TAB_ID))
        await wait_for(
            lambda: tabs.active == SETTINGS_TAB_ID,
            pilot=pilot,
            description="clicking the Settings tab header switches to it",
        )
        assert dialog.active_tab == SETTINGS_TAB_ID


class _MarkerLocalizer:
    """A ``Localizer`` double whose every message renders as one mutable marker."""

    def __init__(self, marker: str) -> None:
        self.marker = marker

    def render(self, _reference: object) -> str:
        return self.marker


class _StubLocaleController:
    """Records surface registration and exposes the marker localizer the test flips."""

    def __init__(self, marker: str = "EN-MARK") -> None:
        self.localizer = _MarkerLocalizer(marker)
        self.registered: list[object] = []
        self.unregistered: list[object] = []

    def register_surface(self, surface: object) -> None:
        self.registered.append(surface)

    def unregister_surface(self, surface: object) -> None:
        self.unregistered.append(surface)


async def test_dialog_registers_and_unregisters_its_localization_surface(tmp_path) -> None:
    from chrys.app.tui.screens.buddy_config import BuddyConfigDialog
    from tests.support.tui_app_harness import make_chrys_app

    app = make_chrys_app(tmp_path)
    controller = app.locale_controller
    ports = StubPorts()

    async with app.run_test(size=(110, 40)) as pilot:
        await pilot.pause()
        dialog = BuddyConfigDialog(ports, locale_controller=controller)
        app.push_screen(dialog)
        await wait_for(lambda: dialog.is_mounted, pilot=pilot, description="dialog mounted")
        assert dialog in controller._surfaces

        await pilot.press("escape")
        await wait_for(
            lambda: dialog not in controller._surfaces,
            pilot=pilot,
            description="the dialog unregisters its surface on close",
        )

    assert dialog not in controller._surfaces


async def test_refresh_localization_swaps_the_dialog_chrome(tmp_path) -> None:
    from textual.widgets import Static

    from chrys.app.tui.screens.buddy_config import BuddyConfigDialog
    from chrys.app.tui.screens.buddy_config.panes.appearance import AppearancePane
    from chrys.app.tui.screens.buddy_config.panes.settings import SettingsPane
    from tests.support.tui_app_harness import make_chrys_app

    app = make_chrys_app(tmp_path)
    controller = _StubLocaleController()
    ports = StubPorts()

    async with app.run_test(size=(110, 40)) as pilot:
        await pilot.pause()
        dialog = BuddyConfigDialog(ports, locale_controller=controller)
        app.push_screen(dialog)
        await wait_for(lambda: dialog.is_mounted, pilot=pilot, description="dialog mounted")

        # The three section.* titles: Identity/Behaviour on Settings, Frames on
        # Appearance (its first section is the Preview, keyed separately).
        settings_sections = list(dialog.query_one(SettingsPane).query(".buddy-config-section"))
        appearance_sections = list(dialog.query_one(AppearancePane).query(".buddy-config-section"))
        identity, behaviour = settings_sections
        _preview, frames = appearance_sections
        titled_sections = (identity, behaviour, frames)

        assert dialog in controller.registered
        assert [str(section.border_title) for section in titled_sections] == ["EN-MARK"] * 3

        controller.localizer.marker = "ZH-MARK"
        dialog.refresh_localization()
        await pilot.pause()

        container = dialog.query_one("#buddy-config-container")
        assert str(container.border_title) == "ZH-MARK"
        assert str(container.border_subtitle) == "ZH-MARK"
        assert str(dialog.query_one("#buddy-config-name-label", Static).content) == "ZH-MARK"
        # The section.* titles re-set too, not only the chrome and the name label.
        assert [str(section.border_title) for section in titled_sections] == ["ZH-MARK"] * 3

        await pilot.press("escape")
        await wait_for(lambda: app.screen is not dialog, pilot=pilot, description="dialog closed")

    assert dialog in controller.unregistered


async def _open_mounted_dialog(pilot, app, ports):
    from chrys.app.tui.screens.buddy_config import BuddyConfigDialog

    dialog = BuddyConfigDialog(ports, locale_controller=None)
    app.push_screen(dialog)
    await wait_for(lambda: dialog.is_mounted, pilot=pilot, description="dialog mounted")
    return dialog


async def _show_tab(pilot, dialog, tab_id: str) -> None:
    from textual.widgets import TabbedContent

    tabs = dialog.query_one(TabbedContent)
    tabs.active = tab_id
    await wait_for(
        lambda: tabs.active == tab_id and dialog.query_one(f"#{tab_id}").region.width > 0,
        pilot=pilot,
        description=f"the {tab_id} tab is shown",
    )


async def test_dialog_commits_a_rename_through_the_settings_tab(tmp_path) -> None:
    from tests.support.tui_app_harness import make_chrys_app

    app = make_chrys_app(tmp_path)
    ports = StubPorts()

    async with app.run_test(size=(110, 40)) as pilot:
        await pilot.pause()
        dialog = await _open_mounted_dialog(pilot, app, ports)
        await _show_tab(pilot, dialog, "buddy-config-tab-settings")

        dialog.query_one("#buddy-config-name", Input).value = "Mochi"
        await click_when_settled(pilot, "#buddy-config-name-apply")
        await wait_for(
            lambda: ("rename", "Mochi") in ports.calls,
            pilot=pilot,
            description="applying the name in the dialog renames the buddy",
        )


async def test_dialog_toggles_mute_through_the_settings_tab(tmp_path) -> None:
    from tests.support.tui_app_harness import make_chrys_app

    app = make_chrys_app(tmp_path)
    ports = StubPorts()

    async with app.run_test(size=(110, 40)) as pilot:
        await pilot.pause()
        dialog = await _open_mounted_dialog(pilot, app, ports)
        await _show_tab(pilot, dialog, "buddy-config-tab-settings")

        checkbox = dialog.query_one("#buddy-config-muted", Checkbox)
        muted = not checkbox.value
        checkbox.value = muted
        await wait_for(
            lambda: ("muted", muted) in ports.calls,
            pilot=pilot,
            description="toggling the checkbox in the dialog writes the muted flag",
        )


async def test_dialog_selects_a_reply_model_through_the_settings_tab(tmp_path) -> None:
    from tests.support.tui_app_harness import make_chrys_app

    app = make_chrys_app(tmp_path)
    ports = StubPorts(model_choices=[("", "Follow active"), ("m", "M")])

    async with app.run_test(size=(110, 40)) as pilot:
        await pilot.pause()
        dialog = await _open_mounted_dialog(pilot, app, ports)
        await _show_tab(pilot, dialog, "buddy-config-tab-settings")

        dialog.query_one("#buddy-config-model", Select).value = "m"
        await wait_for(
            lambda: ("model", "m") in ports.calls,
            pilot=pilot,
            description="picking a model in the dialog writes the reply model",
        )


async def test_dialog_imports_a_frame_through_the_picker_result(tmp_path) -> None:
    from pathlib import Path

    from chrys.app.tui.screens.dialogs.file_picker import FilePicker
    from tests.support.tui_app_harness import make_chrys_app

    target = tmp_path / "art.png"
    target.write_bytes(b"\x89PNG\r\n\x1a\n")
    app = make_chrys_app(tmp_path)
    ports = StubPorts()

    async with app.run_test(size=(110, 40)) as pilot:
        await pilot.pause()
        dialog = await _open_mounted_dialog(pilot, app, ports)
        await _show_tab(pilot, dialog, "buddy-config-tab-appearance")

        await click_when_settled(pilot, "#frame-import-2")
        await wait_for(
            lambda: isinstance(app.screen, FilePicker),
            pilot=pilot,
            description="the import button opens the frame artwork picker",
        )
        picker = app.screen
        assert isinstance(picker, FilePicker)

        # Choose a path, then take the picker's own Select path so its dismissal
        # result flows back through the dialog's on_result callback.
        picker._selected_path = str(target)
        picker._update_select_button()
        await click_when_settled(pilot, "#fsd-select")

        await wait_for(
            lambda: ("import", (2, Path(target))) in ports.calls,
            pilot=pilot,
            description="the picker result imports the chosen path into the frame",
        )


async def test_dialog_removes_a_frame_through_the_appearance_tab(tmp_path) -> None:
    from tests.support.tui_app_harness import make_chrys_app

    app = make_chrys_app(tmp_path)
    ports = StubPorts()

    async with app.run_test(size=(110, 40)) as pilot:
        await pilot.pause()
        dialog = await _open_mounted_dialog(pilot, app, ports)
        await _show_tab(pilot, dialog, "buddy-config-tab-appearance")

        await click_when_settled(pilot, "#frame-remove-3")
        await wait_for(
            lambda: ("remove", 3) in ports.calls,
            pilot=pilot,
            description="removing a frame in the dialog drops its custom artwork",
        )


async def test_appearance_preview_defaults_to_frame_zero() -> None:
    from textual.containers import Horizontal
    from textual.widgets import Static

    from chrys.app.tui.screens.buddy_config.panes.appearance import AppearancePane

    ports = StubPorts()

    async with _appearance_pane_app(ports).run_test(size=(60, 30)) as pilot:
        pane = pilot.app.query_one(AppearancePane)
        assert pane.selected_frame == 0
        assert pilot.app.query_one("#frame-row-0", Horizontal).has_class("-selected")

        preview = pilot.app.query_one("#buddy-config-frame-preview", Static)
        await wait_for(
            lambda: getattr(preview.content, "markup", ""),
            pilot=pilot,
            description="the preview renders the buddy portrait for the default frame",
        )


async def test_appearance_clicking_a_row_switches_the_previewed_frame() -> None:
    from textual.containers import Horizontal
    from textual.widgets import Static

    from chrys.app.tui.screens.buddy_config.panes.appearance import AppearancePane

    ports = StubPorts()

    async with _appearance_pane_app(ports).run_test(size=(60, 30)) as pilot:
        pane = pilot.app.query_one(AppearancePane)
        preview = pilot.app.query_one("#buddy-config-frame-preview", Static)
        await wait_for(
            lambda: getattr(preview.content, "markup", ""),
            pilot=pilot,
            description="the preview renders frame 0",
        )
        frame_zero = preview.content.markup

        await click_when_settled(pilot, "#frame-state-3")
        await wait_for(
            lambda: pane.selected_frame == 3,
            pilot=pilot,
            description="clicking a frame row selects that frame",
        )

        assert pilot.app.query_one("#frame-row-3", Horizontal).has_class("-selected")
        assert not pilot.app.query_one("#frame-row-0", Horizontal).has_class("-selected")
        await wait_for(
            lambda: preview.content.markup != frame_zero,
            pilot=pilot,
            description="the preview repaints for the newly selected frame",
        )


async def test_appearance_import_repaints_the_selected_preview(tmp_path, monkeypatch) -> None:
    from PIL import Image
    from textual.widgets import Static

    from chrys.app.tui.screens.buddy_config.panes.appearance import AppearancePane

    ports = StubPorts()
    species = ports.buddy().species.value
    monkeypatch.setattr("chrys.app.features.buddy.pixel_sprites.assets_dir", lambda: tmp_path)

    async with _appearance_pane_app(ports).run_test(size=(60, 30)) as pilot:
        pane = pilot.app.query_one(AppearancePane)
        preview = pilot.app.query_one("#buddy-config-frame-preview", Static)
        await wait_for(
            lambda: getattr(preview.content, "markup", ""),
            pilot=pilot,
            description="the preview renders the built-in frame",
        )
        built_in = preview.content.markup

        # The pane is selected on frame 0 by default, so importing frame 0 must repaint it.
        target = tmp_path / f"{species}_0.png"
        Image.new("RGBA", (20, 16), (255, 0, 0, 255)).save(target)
        ports.custom_frames = {0}
        await pane.import_into(0, target)

        await wait_for(
            lambda: preview.content.markup != built_in,
            pilot=pilot,
            description="the imported custom artwork repaints the preview",
        )
        assert preview.content.markup != built_in


async def test_appearance_removal_repaints_the_selected_preview(tmp_path, monkeypatch) -> None:
    from PIL import Image
    from textual.widgets import Static

    from chrys.app.tui.screens.buddy_config.panes.appearance import AppearancePane

    ports = StubPorts()
    species = ports.buddy().species.value
    monkeypatch.setattr("chrys.app.features.buddy.pixel_sprites.assets_dir", lambda: tmp_path)

    async with _appearance_pane_app(ports).run_test(size=(60, 30)) as pilot:
        pane = pilot.app.query_one(AppearancePane)
        preview = pilot.app.query_one("#buddy-config-frame-preview", Static)
        await wait_for(
            lambda: getattr(preview.content, "markup", ""),
            pilot=pilot,
            description="the preview renders the built-in frame",
        )
        built_in = preview.content.markup

        # The pane is selected on frame 0 by default, so removing frame 0's custom
        # artwork must paint the preview back to the built-in sprite.
        target = tmp_path / f"{species}_0.png"
        Image.new("RGBA", (20, 16), (255, 0, 0, 255)).save(target)
        ports.custom_frames = {0}
        await pane.import_into(0, target)
        await wait_for(
            lambda: preview.content.markup != built_in,
            pilot=pilot,
            description="the imported custom artwork repaints the preview",
        )

        target.unlink()
        ports.custom_frames = set()
        await pane.remove_frame(0)
        await wait_for(
            lambda: preview.content.markup == built_in,
            pilot=pilot,
            description="removing the custom artwork restores the built-in preview",
        )
        assert preview.content.markup == built_in


async def test_appearance_last_row_buttons_stay_reachable(tmp_path) -> None:
    from textual.containers import Horizontal

    from chrys.app.tui.screens.buddy_config.panes.appearance import AppearancePane
    from chrys.app.tui.screens.dialogs.file_picker import FilePicker
    from tests.support.tui_app_harness import make_chrys_app

    app = make_chrys_app(tmp_path)
    ports = StubPorts()

    async with app.run_test(size=(110, 40)) as pilot:
        await pilot.pause()
        dialog = await _open_mounted_dialog(pilot, app, ports)
        await _show_tab(pilot, dialog, "buddy-config-tab-appearance")

        pane = dialog.query_one(AppearancePane)
        # The pane scrolls its preview + six rows; bring the last row into view.
        dialog.query_one("#frame-row-5", Horizontal).scroll_visible(animate=False)
        await pilot.pause()

        await click_when_settled(pilot, "#frame-remove-5")
        await wait_for(
            lambda: ("remove", 5) in ports.calls,
            pilot=pilot,
            description="the last row's Remove button is still clickable",
        )
        # A row's button must not change the previewed frame.
        assert pane.selected_frame == 0

        await click_when_settled(pilot, "#frame-import-5")
        await wait_for(
            lambda: isinstance(app.screen, FilePicker),
            pilot=pilot,
            description="the last row's Import button is still clickable",
        )

        # The import check leaves its picker on top; close it so the dialog is
        # active again, then the open-folder button below the last row must
        # stay reachable too.
        await pilot.press("escape")
        await wait_for(lambda: app.screen is dialog, pilot=pilot, description="the picker closes back to the dialog")
        dialog.query_one("#buddy-config-open-folder").scroll_visible(animate=False)
        await pilot.pause()
        await click_when_settled(pilot, "#buddy-config-open-folder")
        await wait_for(
            lambda: ("open_dir", None) in ports.calls,
            pilot=pilot,
            description="the open-folder button below the last row is still clickable",
        )


async def test_each_buddy_tab_has_one_scroll_container(tmp_path) -> None:
    """A pane must not nest its own scroll inside the tab body's wrapper scroll."""
    from textual.containers import VerticalScroll

    from chrys.app.tui.screens.buddy_config.panes.appearance import AppearancePane
    from chrys.app.tui.screens.buddy_config.panes.profile import ProfilePane
    from chrys.app.tui.screens.buddy_config.panes.settings import SettingsPane
    from tests.support.tui_app_harness import make_chrys_app

    app = make_chrys_app(tmp_path)
    ports = StubPorts()

    async with app.run_test(size=(110, 40)) as pilot:
        await pilot.pause()
        dialog = await _open_mounted_dialog(pilot, app, ports)

        # No pane scrolls itself: the tab body's wrapper is the single scroller.
        for pane_type in (ProfilePane, SettingsPane, AppearancePane):
            assert not isinstance(dialog.query_one(pane_type), VerticalScroll)

        for tab_id in ("buddy-config-tab-profile", "buddy-config-tab-settings", "buddy-config-tab-appearance"):
            scrollers = list(dialog.query_one(f"#{tab_id}").query(VerticalScroll))
            assert len(scrollers) == 1
            assert scrollers[0].has_class("buddy-config-pane-scroll")


async def test_appearance_tab_renders_sections_and_frame_rows(tmp_path) -> None:
    """The Appearance tab mirrors the Settings tab: bordered sections of rows."""
    from chrys.app.tui.screens.buddy_config.panes.appearance import AppearancePane
    from tests.support.tui_app_harness import make_chrys_app

    app = make_chrys_app(tmp_path)
    ports = StubPorts()

    async with app.run_test(size=(110, 40)) as pilot:
        await pilot.pause()
        dialog = await _open_mounted_dialog(pilot, app, ports)
        await _show_tab(pilot, dialog, "buddy-config-tab-appearance")
        await pilot.pause()

        pane = dialog.query_one(AppearancePane)
        sections = list(pane.query(".buddy-config-section"))
        assert [str(section.border_title) for section in sections] == ["Preview", "Frames"]

        preview, frames = sections
        # The six frame rows live under the Frames section, one per frame.
        assert [row.id for row in frames.query(".frame-row")] == [f"frame-row-{frame}" for frame in range(6)]
        # The still portrait preview lives under the Preview section.
        assert len(list(preview.query("#buddy-config-frame-preview"))) == 1
        assert list(frames.query("#buddy-config-frame-preview")) == []


async def test_appearance_preview_is_horizontally_centered(tmp_path) -> None:
    """The 24-wide preview is centred on the pane, not pinned to its left edge.

    A vertical container's align centres the widest child's column and
    left-aligns narrower siblings, so the preview used to sit at the pane's left
    edge. Giving it its own full-width single-child row fixes that.
    """
    from textual.widgets import Static

    from chrys.app.tui.screens.buddy_config.panes.appearance import AppearancePane
    from tests.support.tui_app_harness import make_chrys_app

    app = make_chrys_app(tmp_path)
    ports = StubPorts()

    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        dialog = await _open_mounted_dialog(pilot, app, ports)
        await _show_tab(pilot, dialog, "buddy-config-tab-appearance")
        await pilot.pause()

        pane = dialog.query_one(AppearancePane)
        preview = dialog.query_one("#buddy-config-frame-preview", Static)

        pane_center = pane.content_region.x + pane.content_region.width // 2
        assert abs((preview.region.x + preview.region.width // 2) - pane_center) <= 1
        # The narrower preview now sits centred INSIDE the pane rather than at
        # its left edge — exactly what was broken.
        assert preview.region.x > pane.content_region.x


async def test_settings_tab_renders_sections_and_rows(tmp_path) -> None:
    """The Settings tab mirrors the Settings dialog: bordered sections of rows."""
    from textual.widgets import Label

    from chrys.app.tui.screens.buddy_config.panes.settings import SettingsPane
    from tests.support.tui_app_harness import make_chrys_app

    app = make_chrys_app(tmp_path)
    ports = StubPorts()

    async with app.run_test(size=(110, 40)) as pilot:
        await pilot.pause()
        dialog = await _open_mounted_dialog(pilot, app, ports)
        await _show_tab(pilot, dialog, "buddy-config-tab-settings")
        await pilot.pause()

        pane = dialog.query_one(SettingsPane)
        sections = list(pane.query(".buddy-config-section"))
        assert len(sections) == 2
        assert {str(section.border_title) for section in sections} == {"Identity", "Behaviour"}

        # Rows sit inside the sections, each a main row of label + control.
        rows = list(pane.query(".buddy-config-row-main"))
        assert len(rows) == 3

        # The Name row is one main row holding the label, the EnhancedInput and
        # the Apply link button — and no plain Input/Switch control survives.
        name_label = dialog.query_one("#buddy-config-name-label", Label)
        name_row = name_label.parent
        assert name_row.has_class("buddy-config-row-main")
        assert [child.id for child in name_row.children] == [
            "buddy-config-name-label",
            "buddy-config-name",
            "buddy-config-name-apply",
        ]
        assert name_row.query_one("#buddy-config-name-apply").has_class("buddy-config-link")
        inputs = list(pane.query(Input))
        assert [field.id for field in inputs] == ["buddy-config-name"]
        assert isinstance(inputs[0], EnhancedInput)
        assert list(pane.query(Switch)) == []

        assert dialog.query_one("#buddy-config-model-label", Label)

        # The Muted control is a Checkbox carrying its own label, not a Switch.
        muted = dialog.query_one("#buddy-config-muted", Checkbox)
        assert muted.label.plain == "Muted"


async def test_buddy_container_matches_the_settings_size(tmp_path) -> None:
    """The dialog box grows like the Settings one instead of a fixed 84x32."""
    from textual.containers import VerticalGroup

    from chrys.app.tui.screens.buddy_config import BuddyConfigDialog
    from tests.support.tui_app_harness import make_chrys_app

    app = make_chrys_app(tmp_path)
    ports = StubPorts()

    async with app.run_test(size=(200, 60)) as pilot:
        await pilot.pause()
        dialog = BuddyConfigDialog(ports, locale_controller=None)
        app.push_screen(dialog)
        await wait_for(lambda: dialog.is_mounted, pilot=pilot, description="dialog mounted")

        container = dialog.query_one("#buddy-config-container", VerticalGroup)
        # 92% of 200 caps at 92 wide; 85% of 60 caps at 48 tall.
        assert container.region.width == 92
        assert container.region.height == 48
