# Copyright (c) Huawei Technologies Co., Ltd. 2026. All rights reserved.

"""Buddy-config ports and their coordinator."""

from __future__ import annotations

from chrys.app.tui.screens.buddy_config import ports


def test_frame_state_members() -> None:
    assert ports.FrameState.BUILTIN.value == "builtin"
    assert ports.FrameState.CUSTOM.value == "custom"


def _coordinator(*, save_settings=None, notify=None):
    from chrys.app.tui.screens.main.buddy_config_coordinator import BuddyConfigCallbacks, BuddyConfigCoordinator
    from chrys.foundation.config.settings import Settings

    return BuddyConfigCoordinator(
        BuddyConfigCallbacks(
            save_settings=save_settings or _noop_save_settings,
            notify=notify or (lambda *args, **kwargs: None),
            settings=Settings,
            model_options=lambda: [("", "Follow active")],
            open_path=lambda path: None,
        )
    )


async def test_coordinator_renames_through_the_action(monkeypatch) -> None:
    from chrys.app.features.buddy import actions
    from tests.app.tui.screens.buddy_config.support import _record

    seen: list[str] = []
    monkeypatch.setattr(actions, "rename", seen.append)
    monkeypatch.setattr(actions, "current_buddy", _record)

    await _coordinator().rename("Mochi")

    assert seen == ["Mochi"]


async def test_set_reply_model_writes_a_value_and_clears_the_key() -> None:
    recorded: list[tuple[dict[str, str], tuple[str, ...]]] = []

    async def save_settings(values, remove):
        recorded.append((dict(values), tuple(remove)))

    coordinator = _coordinator(save_settings=save_settings)

    await coordinator.set_reply_model("m")
    await coordinator.set_reply_model("")

    assert recorded == [
        ({"model.role.buddy_model_id": "m"}, ()),
        ({}, ("model.role.buddy_model_id",)),
    ]


def test_frame_state_needs_a_present_and_decodable_frame(monkeypatch) -> None:
    from chrys.app.features.buddy import actions, pixel_sprites
    from tests.app.tui.screens.buddy_config.support import _record

    coordinator = _coordinator()

    monkeypatch.setattr(actions, "current_buddy", lambda: None)
    assert coordinator.frame_state(0) is ports.FrameState.BUILTIN

    monkeypatch.setattr(actions, "current_buddy", _record)
    monkeypatch.setattr(pixel_sprites, "load_external_pixel_frame", lambda species, frame: object())
    assert coordinator.frame_state(0) is ports.FrameState.CUSTOM

    monkeypatch.setattr(pixel_sprites, "load_external_pixel_frame", lambda species, frame: None)
    assert coordinator.frame_state(0) is ports.FrameState.BUILTIN


async def test_import_frame_warns_when_the_install_fails(monkeypatch) -> None:
    from pathlib import Path

    from chrys.app.features.buddy import actions, assets
    from tests.app.tui.screens.buddy_config.support import _record

    notifications: list[dict[str, object]] = []
    coordinator = _coordinator(notify=lambda message, **kwargs: notifications.append(kwargs))

    monkeypatch.setattr(actions, "current_buddy", _record)
    monkeypatch.setattr(assets, "install_frame", _raise_oserror)

    await coordinator.import_frame(0, Path("art.png"))

    assert len(notifications) == 1
    assert notifications[0]["severity"] == "warning"


async def test_remove_frame_warns_when_the_removal_fails(monkeypatch) -> None:
    from chrys.app.features.buddy import actions, assets
    from tests.app.tui.screens.buddy_config.support import _record

    notifications: list[dict[str, object]] = []
    coordinator = _coordinator(notify=lambda message, **kwargs: notifications.append(kwargs))

    monkeypatch.setattr(actions, "current_buddy", _record)
    monkeypatch.setattr(assets, "remove_frame", _raise_oserror)

    await coordinator.remove_frame(0)

    assert len(notifications) == 1
    assert notifications[0]["severity"] == "warning"


async def test_no_buddy_edits_are_noops(monkeypatch) -> None:
    from pathlib import Path

    from chrys.app.features.buddy import actions, assets

    writes: list[object] = []

    async def save_settings(values, remove):
        writes.append(("save", values, remove))

    def notify(*args, **kwargs):
        writes.append(("notify", args, kwargs))

    coordinator = _coordinator(save_settings=save_settings, notify=notify)

    monkeypatch.setattr(actions, "current_buddy", lambda: None)
    monkeypatch.setattr(assets, "install_frame", lambda *args: writes.append(("install", args)))
    monkeypatch.setattr(assets, "remove_frame", lambda *args: writes.append(("remove", args)))

    await coordinator.import_frame(0, Path("art.png"))
    await coordinator.remove_frame(0)
    await coordinator.set_muted(True)
    await coordinator.rehatch()

    assert writes == []


def _raise_oserror(*args: object) -> None:
    raise OSError("the file system said no")


async def _noop_save_settings(values, remove) -> None:
    return None
