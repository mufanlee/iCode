# Copyright (c) Huawei Technologies Co., Ltd. 2026. All rights reserved.
#
"""Opening the Buddy dialog must not pay for the mounted transcript beneath it."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from textual.widgets import TextArea

from chrys.app.tui.screens.buddy_config import BuddyConfigDialog
from chrys.app.tui.screens.main.screen import MainScreen
from chrys.app.tui.widgets.chat.messages import AgentMessage, UserMessage
from chrys.app.tui.widgets.chat.panel import ChatPanel
from chrys.app.tui.widgets.chrome.footer import ChrysFooter
from chrys.app.tui.widgets.chrome.input_bar import InputBar
from chrys.app.tui.widgets.markdown import VirtualizedMarkdown
from tests.app.tui.screens.buddy_config.support import StubPorts
from tests.support.pilot_barrier import screen_is_settled
from tests.support.tui_app_harness import make_chrys_app
from tests.support.waiting import wait_for, wait_until_quiet

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.asyncio

_UI_WAIT_TIMEOUT_SECONDS = 10.0


async def test_populated_main_screen_buddy_dialog_does_not_restyle_recompose_or_relayout(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    app = make_chrys_app(tmp_path)

    async with app.run_test(size=(120, 36)) as pilot:
        main = app.screen
        assert isinstance(main, MainScreen)
        panel = main.query_one(ChatPanel)
        transcript = []
        for index in range(24):
            transcript.extend(
                (
                    UserMessage(f"Question {index}\nwith a second line"),
                    AgentMessage(f"## Answer {index}\n\nA paragraph with `code` and **emphasis**."),
                )
            )
        await panel.mount(*transcript)
        await wait_for(
            lambda: (
                len(panel.walk_children()) >= 96
                and all(markdown.source for markdown in panel.query(VirtualizedMarkdown))
            ),
            pilot=pilot,
            timeout=_UI_WAIT_TIMEOUT_SECONDS,
            description="populated transcript composition",
        )
        main.query_one(InputBar).focus_input()
        await wait_for(
            lambda: main.query_one(InputBar).query_one("#chat-input", TextArea).has_focus,
            pilot=pilot,
            timeout=_UI_WAIT_TIMEOUT_SECONDS,
            description="composer focus before overlay",
        )
        await wait_for(
            lambda: screen_is_settled(app, main),
            pilot=pilot,
            timeout=_UI_WAIT_TIMEOUT_SECONDS,
            description="settled underlay layout",
        )
        # Gate on stability, not a single settled observation: a straggler layout
        # landing after the spies are armed would otherwise fail a loaded worker.
        await wait_until_quiet(
            lambda: screen_is_settled(app, main),
            pilot=pilot,
            description="underlay stays settled before arming the spies",
        )

        # Arm the spies only once the underlay has settled: everything before the
        # dialog opens is the transcript composing itself, not the overlay's cost.
        style_updates: list[bool] = []
        footer_recomposes: list[None] = []
        layout_refreshes: list[None] = []
        monkeypatch.setattr(
            main,
            "update_node_styles",
            lambda animate=True: style_updates.append(animate),
        )
        monkeypatch.setattr(
            main,
            "_refresh_layout",
            lambda *_args, **_kwargs: layout_refreshes.append(None),
        )

        async def record_footer_recompose() -> None:
            footer_recomposes.append(None)

        monkeypatch.setattr(main.query_one(ChrysFooter), "recompose", record_footer_recompose)

        dialog = BuddyConfigDialog(StubPorts(), locale_controller=None)
        app.push_screen(dialog)
        await wait_for(
            lambda: app.screen is dialog and dialog.is_mounted,
            pilot=pilot,
            timeout=_UI_WAIT_TIMEOUT_SECONDS,
            description="buddy dialog open over the populated transcript",
        )
        # Let the dialog's own mount and first layout settle before judging the underlay.
        await pilot.pause()

        assert style_updates == []
        assert footer_recomposes == []
        assert layout_refreshes == []
