# Copyright (c) Huawei Technologies Co., Ltd. 2026. All rights reserved.

"""Buddy-config ports and their coordinator."""

from __future__ import annotations

from chrys.app.tui.screens.buddy_config import ports


def test_frame_state_members() -> None:
    assert ports.FrameState.BUILTIN.value == "builtin"
    assert ports.FrameState.CUSTOM.value == "custom"
