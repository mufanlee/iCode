# Copyright (c) Huawei Technologies Co., Ltd. 2026. All rights reserved.

"""Re-hatching replaces the saved buddy; it never reuses one."""

from __future__ import annotations

import random

from chrys.app.features.buddy import actions
from chrys.app.features.buddy.hatchery import hatchling


def _rng(seed: int) -> random.Random:
    return random.Random(seed)


def test_rehatch_without_a_buddy_is_a_no_op() -> None:
    assert actions.current_buddy() is None
    assert actions.rehatch(_rng(1)) is None
    assert actions.current_buddy() is None


def test_rehatch_replaces_an_existing_buddy_with_the_fresh_draw() -> None:
    first = actions.hatch(_rng(1))
    assert first is not None

    # A fresh Random(2) draws the same buddy whether it is built directly or
    # through rehatch; comparing to it proves rehatch stored the NEW draw, not
    # the existing record it was asked to replace.
    expected = hatchling(_rng(2))
    second = actions.rehatch(_rng(2))

    assert second is not None
    assert second.record.species == expected.species
    assert second.record.rarity == expected.rarity
    assert second.record.name == expected.name
    assert second.record.shiny == expected.shiny
    assert dict(second.record.traits) == dict(expected.traits)

    stored = actions.current_buddy()
    assert stored is not None
    assert stored.record.name == expected.name
    assert stored.record.hatched_at >= first.record.hatched_at
