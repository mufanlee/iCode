# Copyright (c) Huawei Technologies Co., Ltd. 2026. All rights reserved.

"""The Buddy configuration dialog renders and reflects port state."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import Container

from chrys.app.tui.theme import TuiVariableDefaultsMixin
from tests.app.tui.screens.buddy_config.support import StubPorts
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
