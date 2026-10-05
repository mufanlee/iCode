# Copyright (c) Huawei Technologies Co., Ltd. 2026. All rights reserved.
#
"""Both entry points that open the Buddy configuration dialog."""

from __future__ import annotations

from random import Random
from typing import TYPE_CHECKING

import pytest
from textual.widgets import Button, TabbedContent

from chrys.app.features.buddy import actions
from chrys.app.tui.screens.buddy_config import BuddyConfigDialog
from chrys.app.tui.screens.main.buddy_command import BuddyCommandController
from chrys.app.tui.widgets.sidebar.buddy import BuddyPanel
from chrys.app.tui.widgets.sidebar.panel import SidebarPanel
from tests.support.tui_app_harness import make_chrys_app
from tests.support.tui_helpers import click_when_settled
from tests.support.waiting import wait_for

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from chrys.foundation.i18n import MessageRef


class _BuddyView:
    """A ``BuddyCommandView`` double: only the open request is of interest here."""

    def __init__(self) -> None:
        self.opened = 0

    def notify_buddy(self, message: MessageRef | str, *, severity: str = "information", timeout: float = 10) -> None:
        raise AssertionError("config must not toast")

    def refresh_buddy_panel(self, *, focus_tab: bool) -> None:
        raise AssertionError("config must not refresh the panel")

    def call_after_refresh(self, callback: Callable[[], None]) -> None:
        callback()

    def open_buddy_config(self) -> None:
        self.opened += 1


def test_the_config_slash_command_opens_the_dialog() -> None:
    view = _BuddyView()
    controller = BuddyCommandController(view)

    controller.handle("config")

    assert view.opened == 1


async def test_the_sidebar_button_opens_the_dialog_without_petting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    petted: list[str] = []
    monkeypatch.setattr(BuddyPanel, "pet", lambda _panel: petted.append("pet"))
    actions.hatch(Random(1))
    app = make_chrys_app(tmp_path)

    async with app.run_test(size=(140, 50)) as pilot:
        main = app.screen
        assert main is not None
        sidebar = main.query_one(SidebarPanel)
        sidebar.focus_tab("tab-buddy")
        await wait_for(
            lambda: sidebar.query_one(TabbedContent).active == "tab-buddy",
            pilot=pilot,
            description="the Buddy tab is open",
        )
        assert main.query_one("#buddy-configure", Button).is_mounted

        await click_when_settled(pilot, "#buddy-configure")

        await wait_for(
            lambda: isinstance(app.screen, BuddyConfigDialog),
            pilot=pilot,
            description="the Buddy configuration dialog opened",
        )
        assert petted == []
