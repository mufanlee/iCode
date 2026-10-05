# Copyright (c) Huawei Technologies Co., Ltd. 2026. All rights reserved.

"""Buddy-config ports and their coordinator."""

from __future__ import annotations

from chrys.app.tui.screens.buddy_config import ports


def test_frame_state_members() -> None:
    assert ports.FrameState.BUILTIN.value == "builtin"
    assert ports.FrameState.CUSTOM.value == "custom"


async def test_coordinator_renames_through_the_action(monkeypatch) -> None:
    from chrys.app.features.buddy import actions
    from chrys.app.tui.screens.main.buddy_config_coordinator import BuddyConfigCallbacks, BuddyConfigCoordinator
    from chrys.foundation.config.settings import Settings
    from tests.app.tui.screens.buddy_config.support import _record

    seen: list[str] = []
    monkeypatch.setattr(actions, "rename", seen.append)
    monkeypatch.setattr(actions, "current_buddy", _record)

    coordinator = BuddyConfigCoordinator(
        BuddyConfigCallbacks(
            save_settings=_noop_save_settings,
            notify=lambda *a, **k: None,
            push_screen=lambda *a, **k: None,
            settings=Settings,
            model_options=lambda: [("", "Follow active")],
            open_path=lambda path: None,
        )
    )

    await coordinator.rename("Mochi")

    assert seen == ["Mochi"]


async def _noop_save_settings(values, remove) -> None:
    return None
