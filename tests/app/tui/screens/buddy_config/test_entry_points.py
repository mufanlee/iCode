# Copyright (c) Huawei Technologies Co., Ltd. 2026. All rights reserved.
#
"""Both entry points that open the Buddy configuration dialog."""

from __future__ import annotations

from random import Random
from typing import TYPE_CHECKING

from chrys.app.features.buddy import actions
from chrys.app.tui.screens.buddy_config import BuddyConfigDialog
from chrys.app.tui.screens.main.buddy_command import BuddyCommandController
from tests.support.tui_app_harness import make_chrys_app
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


async def test_the_footer_binding_opens_the_dialog(tmp_path: Path) -> None:
    actions.hatch(Random(1))
    app = make_chrys_app(tmp_path)

    async with app.run_test(size=(140, 50)) as pilot:
        await pilot.press("f7")

        await wait_for(
            lambda: isinstance(app.screen, BuddyConfigDialog),
            pilot=pilot,
            description="the Buddy configuration dialog opened",
        )
