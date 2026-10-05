# Buddy Configuration Dialog — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a unified `/buddy config` modal that shows a buddy's identity/progress and lets the user rename it, mute it, pick its reply model, manage custom PNG artwork, and re-hatch.

**Architecture:** A new modal dialog package `screens/buddy_config/` (mirroring `screens/settings/`) that talks only through a `BuddyConfigPorts` protocol. A `BuddyConfigCoordinator` owned by `MainScreen` implements the ports and does all blocking buddy/settings writes on `asyncio.to_thread`. A new `features/buddy/assets.py` owns the custom-art file operations, and `features/buddy/actions.py` gains `rehatch()`.

**Tech Stack:** Python 3.14, Textual 8.2.7, pytest (pytest-asyncio), Pillow; project tooling via `uv run`.

**Spec:** `src/chrys/app/features/buddy/docs/buddy-config-design.md`.

**Project rules that bind every task:**
- Run tools through `uv run`. Verify with `uv run python scripts/chrys_test.py --smart --paths <changed files…>` unless a task says otherwise.
- **Do not commit unless the user explicitly authorizes it.** The `Commit` steps below are the plan's default; if authorization is withheld, stop after the verification step. When authorized, run `uv run ruff check --fix <paths>` and `uv run ruff format <paths>` first, stage explicit paths (never `git add -A`), and commit with `--no-verify`.
- Do not run i18n concurrently with pytest.

---

## File Structure

**Create**
- `src/chrys/app/features/buddy/assets.py` — custom-art file operations for one species' frames.
- `src/chrys/app/tui/screens/buddy_config/__init__.py` — package facade.
- `src/chrys/app/tui/screens/buddy_config/ports.py` — `FrameState`, `BuddyConfigPorts`.
- `src/chrys/app/tui/screens/buddy_config/dialog.py` — `BuddyConfigDialog`.
- `src/chrys/app/tui/screens/buddy_config/dialog.tcss` — layout/styling.
- `src/chrys/app/tui/screens/buddy_config/panes/__init__.py`
- `src/chrys/app/tui/screens/buddy_config/panes/profile.py` — `ProfilePane`.
- `src/chrys/app/tui/screens/buddy_config/panes/appearance.py` — `AppearancePane`.
- `src/chrys/app/tui/screens/buddy_config/panes/settings.py` — `SettingsPane`.
- `src/chrys/app/tui/screens/main/buddy_config_coordinator.py` — `BuddyConfigCoordinator` + `BuddyConfigCallbacks`.
- Tests: `tests/app/features/buddy/test_assets.py`, `tests/app/features/buddy/test_rehatch.py`,
  `tests/app/tui/screens/buddy_config/test_dialog.py`,
  `tests/app/tui/screens/buddy_config/test_coordinator.py`,
  `tests/app/tui/screens/buddy_config/test_overlay_budget.py`.

**Modify**
- `src/chrys/app/features/buddy/actions.py` — add `rehatch()`.
- `src/chrys/app/features/buddy/pixel_sprites.py` — `_get_assets_dir` → `assets_dir` (imported from `assets`).
- `src/chrys/app/tui/screens/main/ports.py` — add `open_buddy_config()` to `BuddyCommandView`.
- `src/chrys/app/tui/screens/main/view_adapter.py` — implement `open_buddy_config()`.
- `src/chrys/app/tui/screens/main/buddy_command.py` — route `config`.
- `src/chrys/app/tui/screens/main/config_actions.py` — `open_buddy_config` + callback field.
- `src/chrys/app/tui/screens/main/screen.py` — own the coordinator; handle the sidebar message.
- `src/chrys/app/tui/widgets/sidebar/buddy.py` — ⚙ button + `ConfigRequested` message.
- `tests/foundation/i18n/_buddy_catalog_oracle_ids.py` + `tests/foundation/i18n/test_catalog_oracle.py` — new ids + count.
- `docs/en/reference/tui-slash-commands.md`, `docs/zh-Hans/reference/tui-slash-commands.md` — `/buddy config` row and text.

---

## Task 1: Custom-art file operations

**Files:**
- Create: `src/chrys/app/features/buddy/assets.py`
- Test: `tests/app/features/buddy/test_assets.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/app/features/buddy/test_assets.py
# Copyright (c) Huawei Technologies Co., Ltd. 2026. All rights reserved.

"""Custom buddy artwork: where it lives and how one frame is installed."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from chrys.app.features.buddy import assets
from chrys.app.features.buddy.model import Species


def _write_png(path: Path, size: tuple[int, int] = (20, 16)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", size, (255, 0, 0, 255)).save(path)


def test_frame_path_names_the_species_and_frame() -> None:
    assert assets.frame_path(Species.MUSHROOM, 3).name == "mushroom_3.png"


def test_install_then_remove_round_trips_a_frame(tmp_path: Path) -> None:
    source = tmp_path / "art.png"
    _write_png(source, (40, 32))

    assert not assets.is_custom_frame(Species.MUSHROOM, 0)
    assets.install_frame(Species.MUSHROOM, 0, source)
    assert assets.is_custom_frame(Species.MUSHROOM, 0)
    assert assets.frame_path(Species.MUSHROOM, 0).read_bytes() == source.read_bytes()

    assets.remove_frame(Species.MUSHROOM, 0)
    assert not assets.is_custom_frame(Species.MUSHROOM, 0)


def test_install_rejects_a_non_image_and_writes_nothing(tmp_path: Path) -> None:
    source = tmp_path / "notes.txt"
    source.write_text("not an image", encoding="utf-8")

    with pytest.raises(OSError):
        assets.install_frame(Species.MUSHROOM, 1, source)

    assert not assets.is_custom_frame(Species.MUSHROOM, 1)


def test_remove_a_missing_frame_is_a_no_op() -> None:
    assets.remove_frame(Species.MUSHROOM, 5)  # must not raise
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/app/features/buddy/test_assets.py -n0 -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'chrys.app.features.buddy.assets'`.

- [ ] **Step 3: Write the implementation**

```python
# src/chrys/app/features/buddy/assets.py
# Copyright (c) Huawei Technologies Co., Ltd. 2026. All rights reserved.

"""Custom pixel artwork for a buddy species.

One file per species and frame, ``<species>_<frame>.png``, under the buddy
assets directory. Art is stored exactly as supplied; the renderer normalizes it
to the 20x16 canvas with nearest-neighbor sampling when it loads.
"""

from __future__ import annotations

from pathlib import Path

from chrys.app.features.buddy.animation import FRAME_COUNT
from chrys.app.features.buddy.model import Species
from chrys.foundation.platform import get_platform
from chrys.foundation.platform.files import atomic_write_owner_only_bytes

_ASSETS = Path("extras") / "buddy" / "assets"


def assets_dir() -> Path:
    """The directory custom buddy artwork is read from and written to."""
    return get_platform().config_dir / _ASSETS


def frame_path(species: Species, frame: int) -> Path:
    """The file that overrides *frame* of *species*, whether or not it exists."""
    _require_frame(frame)
    return assets_dir() / f"{species.value}_{frame}.png"


def is_custom_frame(species: Species, frame: int) -> bool:
    """Whether a custom file is installed for *frame* of *species*."""
    return frame_path(species, frame).is_file()


def install_frame(species: Species, frame: int, source: Path) -> None:
    """Copy *source* into *species*'s *frame* slot, atomically.

    Raises:
        OSError: *source* cannot be read, or is not a decodable image, or the
            destination cannot be written. Nothing is written on failure.
    """
    from PIL import Image

    destination = frame_path(species, frame)
    with Image.open(source) as opened:  # raises OSError/UnidentifiedImageError on non-images
        opened.verify()
    payload = Path(source).read_bytes()
    atomic_write_owner_only_bytes(destination, payload)


def remove_frame(species: Species, frame: int) -> None:
    """Delete *species*'s custom *frame*, if any. A missing file is fine."""
    frame_path(species, frame).unlink(missing_ok=True)


def _require_frame(frame: int) -> None:
    if not 0 <= frame < FRAME_COUNT:
        raise ValueError(f"frame must be in 0..{FRAME_COUNT - 1}, got {frame}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/app/features/buddy/test_assets.py -n0 -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Verify + commit**

Run: `uv run python scripts/chrys_test.py --smart --paths src/chrys/app/features/buddy/assets.py tests/app/features/buddy/test_assets.py`
Then (only if authorized):
```bash
git add src/chrys/app/features/buddy/assets.py tests/app/features/buddy/test_assets.py
git commit --no-verify -m "feat(buddy): add custom-art asset operations"
```

---

## Task 2: `rehatch()` action

**Files:**
- Modify: `src/chrys/app/features/buddy/actions.py`
- Test: `tests/app/features/buddy/test_rehatch.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/app/features/buddy/test_rehatch.py
# Copyright (c) Huawei Technologies Co., Ltd. 2026. All rights reserved.

"""Re-hatching replaces the saved buddy; it never reuses one."""

from __future__ import annotations

import random

from chrys.app.features.buddy import actions
from chrys.app.features.buddy.model import Rarity, Species


def _rng(seed: int) -> random.Random:
    return random.Random(seed)


def test_rehatch_without_a_buddy_is_a_no_op() -> None:
    assert actions.current_buddy() is None
    assert actions.rehatch(_rng(1)) is None
    assert actions.current_buddy() is None


def test_rehatch_replaces_an_existing_buddy() -> None:
    first = actions.hatch(_rng(1))
    second = actions.rehatch(_rng(2))

    assert second is not None
    assert actions.current_buddy() is not None
    assert (second.record.species, second.record.rarity) == (
        actions.current_buddy().record.species,
        actions.current_buddy().record.rarity,
    )
    # A different seed is overwhelmingly likely to draw different traits; the
    # identity that must hold is that the record was replaced, not reused.
    assert second.record.hatched_at >= first.record.hatched_at
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/app/features/buddy/test_rehatch.py -n0 -q`
Expected: FAIL — `AttributeError: module ... has no attribute 'rehatch'`.

- [ ] **Step 3: Write the implementation**

Add to `src/chrys/app/features/buddy/actions.py`, immediately after `hatch`:

```python
def rehatch(rng: Random | None = None) -> Buddy | None:
    """Replace the saved buddy with a fresh draw. None when none has hatched.

    Unlike :func:`hatch`, this overwrites an existing record, so it can change
    the species, rarity, shiny flag, traits and name. It is a wholesale
    replacement, not an edit: the current record is read only to decide whether
    there is one to replace.
    """
    if _STORE.load() is None:
        return None
    newborn = hatchling(rng if rng is not None else SystemRandom())
    return _grown(_STORE.update(lambda current: newborn if current is not None else None))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/app/features/buddy/test_rehatch.py -n0 -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Verify + commit**

Run: `uv run python scripts/chrys_test.py --smart --paths src/chrys/app/features/buddy/actions.py tests/app/features/buddy/test_rehatch.py`
Then (only if authorized):
```bash
git add src/chrys/app/features/buddy/actions.py tests/app/features/buddy/test_rehatch.py
git commit --no-verify -m "feat(buddy): add rehatch action"
```

---

## Task 3: Promote the assets-directory accessor

**Files:**
- Modify: `src/chrys/app/features/buddy/pixel_sprites.py`
- Test: `tests/app/features/buddy/test_pixel_sprites_assets.py`
- Possibly modify: any test that names `_get_assets_dir`

- [ ] **Step 1: Find every reference to the private name**

Run: `rg -n "_get_assets_dir" src tests`
Expected: only `pixel_sprites.py` defines it and calls it once (in `load_external_pixel_frame`); record any test hits to update in Step 4.

- [ ] **Step 2: Write the failing test**

```python
# tests/app/features/buddy/test_pixel_sprites_assets.py
# Copyright (c) Huawei Technologies Co., Ltd. 2026. All rights reserved.

"""The public assets accessor backs the external frame loader."""

from __future__ import annotations

from PIL import Image

from chrys.app.features.buddy import assets, pixel_sprites
from chrys.app.features.buddy.model import Species


def test_public_accessor_matches_the_assets_module() -> None:
    assert pixel_sprites.assets_dir() == assets.assets_dir()


def test_loader_reads_a_planted_file() -> None:
    target = assets.frame_path(Species.MUSHROOM, 0)
    target.parent.mkdir(parents=True, exist_ok=True)
    assert target.parent == pixel_sprites.assets_dir()
    Image.new("RGBA", (20, 16), (1, 2, 3, 255)).save(target)

    loaded = pixel_sprites.load_external_pixel_frame(Species.MUSHROOM, 0)
    assert loaded is not None
    assert loaded.size == (20, 16)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/app/features/buddy/test_pixel_sprites_assets.py -n0 -q`
Expected: FAIL — `AttributeError: module 'chrys.app.features.buddy.pixel_sprites' has no attribute 'assets_dir'`.

- [ ] **Step 4: Implement the promotion**

In `src/chrys/app/features/buddy/pixel_sprites.py`:
1. Delete `_get_assets_dir` (near line 1881) and add an import at the top imports: `from chrys.app.features.buddy.assets import assets_dir as assets_dir`.
2. In `load_external_pixel_frame`, change `target_path = _get_assets_dir() / f"{species.value}_{frame_idx}.png"` to `target_path = assets_dir() / f"{species.value}_{frame_idx}.png"`.
3. Remove the now-unused `get_platform` import if nothing else in the file uses it (check with `rg -n "get_platform" src/chrys/app/features/buddy/pixel_sprites.py`).
4. Drop the scratch line `pixel_sprites.load_external_pixel_frame.cache_clear() ...` from the test (it was a reminder; the test needs no cache handling).

Update any test found in Step 1 that referenced `_get_assets_dir` to import `assets.assets_dir` instead.

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/app/features/buddy/test_pixel_sprites_assets.py -n0 -q`
Expected: PASS (2 passed).

- [ ] **Step 6: Verify + commit**

Run: `uv run python scripts/chrys_test.py --smart --paths src/chrys/app/features/buddy/pixel_sprites.py tests/app/features/buddy/test_pixel_sprites_assets.py`
Then (only if authorized):
```bash
git add src/chrys/app/features/buddy/pixel_sprites.py tests/app/features/buddy/test_pixel_sprites_assets.py
git commit --no-verify -m "refactor(buddy): expose assets_dir publicly"
```

---

## Task 4: Dialog ports protocol

**Files:**
- Create: `src/chrys/app/tui/screens/buddy_config/ports.py`
- Create: `src/chrys/app/tui/screens/buddy_config/panes/__init__.py`
- Test: `tests/app/tui/screens/buddy_config/test_coordinator.py` (import check only for now)

- [ ] **Step 1: Write the failing test**

```python
# tests/app/tui/screens/buddy_config/test_coordinator.py
# Copyright (c) Huawei Technologies Co., Ltd. 2026. All rights reserved.

"""Buddy-config ports and their coordinator."""

from __future__ import annotations

from chrys.app.tui.screens.buddy_config import ports


def test_frame_state_members() -> None:
    assert ports.FrameState.BUILTIN.value == "builtin"
    assert ports.FrameState.CUSTOM.value == "custom"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/app/tui/screens/buddy_config/test_coordinator.py -n0 -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'chrys.app.tui.screens.buddy_config'`.

- [ ] **Step 3: Write the implementation**

```python
# src/chrys/app/tui/screens/buddy_config/ports.py
# Copyright (c) Huawei Technologies Co., Ltd. 2026. All rights reserved.

"""Ports the Buddy configuration dialog talks through; the main screen implements them."""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from pathlib import Path

    from chrys.app.features.buddy.model import Buddy, Species
    from chrys.foundation.i18n import MessageRef


class FrameState(StrEnum):
    """Whether one frame renders from custom artwork or the built-in sprite."""

    BUILTIN = "builtin"
    CUSTOM = "custom"


class BuddyConfigPorts(Protocol):
    """Everything the buddy-configuration dialog may ask of the screen."""

    def buddy(self) -> Buddy | None: ...
    def species(self) -> Species | None: ...
    def frame_state(self, frame: int) -> FrameState: ...
    def assets_dir(self) -> Path: ...

    # Edits: each one commits immediately; OSError surfaces as a warning toast.
    async def rename(self, name: str) -> None: ...
    async def set_muted(self, muted: bool) -> None: ...
    async def set_reply_model(self, model_id: str) -> None: ...
    async def rehatch(self) -> None: ...
    async def import_frame(self, frame: int, source: Path) -> None: ...
    async def remove_frame(self, frame: int) -> None: ...

    # Reply-model field.
    def reply_model(self) -> str: ...
    def model_options(self) -> list[tuple[str, str]]: ...

    # Chrome.
    def open_assets_dir(self) -> None: ...
    def notify(self, message: MessageRef | str, *, severity: str, timeout: float) -> None: ...
```

Create `src/chrys/app/tui/screens/buddy_config/panes/__init__.py` with only the copyright header and a one-line docstring:
```python
# Copyright (c) Huawei Technologies Co., Ltd. 2026. All rights reserved.

"""Panes composed inside the Buddy configuration dialog."""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/app/tui/screens/buddy_config/test_coordinator.py -n0 -q`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit** (only if authorized)

```bash
git add src/chrys/app/tui/screens/buddy_config/ports.py src/chrys/app/tui/screens/buddy_config/panes/__init__.py tests/app/tui/screens/buddy_config/test_coordinator.py
git commit --no-verify -m "feat(buddy): add buddy-config ports protocol"
```

---

## Task 5: Profile pane (read-only facts + live portrait)

**Files:**
- Create: `src/chrys/app/tui/screens/buddy_config/panes/profile.py`
- Test: `tests/app/tui/screens/buddy_config/test_dialog.py` (pane render assertions)

**Reuse:** `commands.buddy_card` (`src/chrys/app/features/buddy/commands.py:154`) for the fact sheet; `portrait.render_portrait` + `animation.get_idle_frame` for the portrait (as `widgets/sidebar/buddy.py` does).

- [ ] **Step 1: Write the failing test**

```python
# tests/app/tui/screens/buddy_config/test_dialog.py
# Copyright (c) Huawei Technologies Co., Ltd. 2026. All rights reserved.

"""The Buddy configuration dialog renders and reflects port state."""

from __future__ import annotations

from tests.app.tui.screens.buddy_config.support import StubPorts  # created in Task 8


def test_profile_pane_shows_the_buddy_name() -> None:
    from chrys.app.tui.screens.buddy_config.panes.profile import ProfilePane

    ports = StubPorts()
    pane = ProfilePane(ports, locale_controller=None)
    rendered = pane.render_body()
    assert ports.buddy().name in rendered
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/app/tui/screens/buddy_config/test_dialog.py::test_profile_pane_shows_the_buddy_name -n0 -q`
Expected: FAIL — missing module / missing `support.py`.

- [ ] **Step 3: Write the implementation**

```python
# src/chrys/app/tui/screens/buddy_config/panes/profile.py
# Copyright (c) Huawei Technologies Co., Ltd. 2026. All rights reserved.

"""The dialog's Profile tab: a live portrait beside the buddy's read-only facts."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

from chrys.app.features.buddy.commands import buddy_card
from chrys.app.tui.i18n import render_str
from chrys.foundation.i18n import msg

if TYPE_CHECKING:
    from chrys.app.tui.i18n import LocaleController
    from chrys.app.tui.screens.buddy_config.ports import BuddyConfigPorts

_EMPTY_HINT = msg("tui.buddy_config.empty.hint", fallback="Nothing has hatched yet.\n\n/buddy hatch finds out what is in the egg.")
_HATCH = msg("tui.buddy_config.action.hatch", fallback="Hatch")


class ProfilePane(Widget):
    """Read-only buddy facts, plus a portrait that animates while shown."""

    DEFAULT_CSS = """
    ProfilePane { height: 1fr; }
    ProfilePane #buddy-config-portrait { width: 32; height: auto; }
    ProfilePane #buddy-config-facts { height: auto; }
    """

    def __init__(self, ports: BuddyConfigPorts, *, locale_controller: LocaleController | None = None) -> None:
        super().__init__()
        self._ports = ports
        self._locale_controller = locale_controller

    def compose(self) -> ComposeResult:
        yield _BuddyPortrait(self._ports, id="buddy-config-portrait")
        yield Static("", id="buddy-config-facts")

    def render_body(self) -> str:
        """The fact sheet as plain text (used by tests and the title bar)."""
        buddy = self._ports.buddy()
        if buddy is None:
            return render_str(self._locale_controller, _EMPTY_HINT.bind())
        return buddy_card(buddy, render=lambda ref: render_str(self._locale_controller, ref))

    def on_mount(self) -> None:
        self.query_one("#buddy-config-facts", Static).update(Text(self.render_body()))
        self.set_interval(1 / 8, self._tick)

    def _tick(self) -> None:
        self.query_one(_BuddyPortrait).tick()


class _BuddyPortrait(Static):
    """A 20x16 portrait that repaints itself on a fixed cadence."""

    def __init__(self, ports: BuddyConfigPorts, **kwargs: object) -> None:
        super().__init__("", **kwargs)
        self._ports = ports
        self._tick_count = 0

    def tick(self) -> None:
        from chrys.app.features.buddy.animation import get_idle_frame
        from chrys.app.features.buddy.portrait import PORTRAIT_WIDTH, render_portrait

        buddy = self._ports.buddy()
        if buddy is None:
            self.update(Text(""))
            return
        frame, _blink = get_idle_frame(buddy.species, self._tick_count)
        self._tick_count += 1
        lines = render_portrait(
            buddy.appearance,
            buddy.display_name,
            frame=frame,
            blink=False,
            width=self.content_size.width or PORTRAIT_WIDTH,
            effect_tick=self._tick_count,
        )
        self.update(Text("\n".join(lines)))
```

*(`render_portrait`'s exact keyword arguments mirror `widgets/sidebar/buddy.py::_BuddySprite.render_species` — confirm against that call site and match it, dropping `effect_tick` if the sidebar does not pass it there.)*

- [ ] **Step 4: Add the stub and run the test**

Create `tests/app/tui/screens/buddy_config/support.py`:

```python
# Copyright (c) Huawei Technologies Co., Ltd. 2026. All rights reserved.

"""Shared stub ports for buddy-config dialog tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from chrys.app.features.buddy.model import Buddy, Rarity, Species, Trait
from chrys.app.features.buddy.progression import Progress
from chrys.app.tui.screens.buddy_config.ports import FrameState


def _record() -> Buddy:
    from chrys.app.features.buddy.hatchery import hatchling
    from random import Random

    return Buddy.of(hatchling(Random(7)))


@dataclass
class StubPorts:
    """A minimal BuddyConfigPorts good enough to render every pane."""

    _buddy: Buddy | None = field(default_factory=_record)
    reply_model_value: str = ""
    model_choices: list[tuple[str, str]] = field(default_factory=lambda: [("", "Follow active")])
    custom_frames: set[int] = field(default_factory=set)
    calls: list[tuple[str, object]] = field(default_factory=list)

    def buddy(self) -> Buddy | None:
        return self._buddy

    def species(self) -> Species | None:
        return self._buddy.species if self._buddy else None

    def frame_state(self, frame: int) -> FrameState:
        return FrameState.CUSTOM if frame in self.custom_frames else FrameState.BUILTIN

    def assets_dir(self) -> Path:
        return Path("assets")

    async def rename(self, name: str) -> None:
        self.calls.append(("rename", name))

    async def set_muted(self, muted: bool) -> None:
        self.calls.append(("muted", muted))

    async def set_reply_model(self, model_id: str) -> None:
        self.calls.append(("model", model_id))

    async def rehatch(self) -> None:
        self.calls.append(("rehatch", None))

    async def import_frame(self, frame: int, source: Path) -> None:
        self.calls.append(("import", (frame, source)))

    async def remove_frame(self, frame: int) -> None:
        self.calls.append(("remove", frame))

    def reply_model(self) -> str:
        return self.reply_model_value

    def model_options(self) -> list[tuple[str, str]]:
        return self.model_choices

    def open_assets_dir(self) -> None:
        self.calls.append(("open_dir", None))

    def notify(self, message, *, severity: str = "information", timeout: float = 10) -> None:
        self.calls.append(("notify", message))
```

Run: `uv run pytest tests/app/tui/screens/buddy_config/test_dialog.py::test_profile_pane_shows_the_buddy_name -n0 -q`
Expected: PASS.

- [ ] **Step 5: Commit** (only if authorized) with paths for the pane, the test file, and `support.py`.

---

## Task 6: Settings pane (name, mute, reply model)

**Files:**
- Create: `src/chrys/app/tui/screens/buddy_config/panes/settings.py`
- Test: extend `tests/app/tui/screens/buddy_config/test_dialog.py`

**Reuse:** `app/tui/i18n.py` render helpers; Textual `Input`, `Switch` (fall back to `Checkbox` if `Switch` is unavailable in 8.2.7 — check `python -c "import textual.widgets as w; print(hasattr(w,'Switch'))"`), `Select`.

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/app/tui/screens/buddy_config/test_dialog.py -n0 -q -k settings_pane`
Expected: FAIL — module missing.

- [ ] **Step 3: Write the implementation**

```python
# src/chrys/app/tui/screens/buddy_config/panes/settings.py
# Copyright (c) Huawei Technologies Co., Ltd. 2026. All rights reserved.

"""The dialog's Settings tab: name, mute and reply-model controls."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Button, Input, Select, Static

from chrys.app.features.buddy.model import clean_name
from chrys.app.tui.i18n import render_str
from chrys.foundation.i18n import msg

if TYPE_CHECKING:
    from chrys.app.tui.i18n import LocaleController
    from chrys.app.tui.screens.buddy_config.ports import BuddyConfigPorts

_NAME_LABEL = msg("tui.buddy_config.field.name", fallback="Name")
_MUTED_LABEL = msg("tui.buddy_config.field.muted", fallback="Muted")
_MODEL_LABEL = msg("tui.buddy_config.field.reply_model", fallback="Reply model")
_FOLLOW = msg("tui.buddy_config.reply_model.follow", fallback="Follow the active model")
_APPLY = msg("tui.buddy_config.action.apply", fallback="Apply")
_NAME_EMPTY = msg(
    "tui.buddy_config.toast.name_empty",
    fallback="A name has to be at least one visible character.",
)


class SettingsPane(Widget):
    """Edits that commit the moment they are made."""

    DEFAULT_CSS = """
    SettingsPane { height: 1fr; }
    SettingsPane .field { height: auto; margin: 1 0; }
    """

    def __init__(self, ports: BuddyConfigPorts, *, locale_controller: LocaleController | None = None) -> None:
        super().__init__()
        self._ports = ports
        self._locale_controller = locale_controller

    def _t(self, ref) -> str:
        return render_str(self._locale_controller, ref)

    def compose(self) -> ComposeResult:
        yield Static(self._t(_NAME_LABEL.bind()), classes="field")
        with Horizontal(classes="field"):
            yield Input(value=self._ports.buddy().name if self._ports.buddy() else "", id="buddy-config-name")
            yield Button(self._t(_APPLY.bind()), id="buddy-config-name-apply")
        yield Static(self._t(_MUTED_LABEL.bind()), classes="field")
        yield Input(value="", id="buddy-config-muted-marker")  # replaced by a switch in Step 4 if available
        yield Static(self._t(_MODEL_LABEL.bind()), classes="field")
        yield Select(
            [(label, value) for value, label in self._model_choices()],
            value=self._ports.reply_model(),
            allow_blank=False,
            id="buddy-config-model",
        )

    def _model_choices(self) -> list[tuple[str, str]]:
        options = self._ports.model_options()
        return [(self._t(_FOLLOW.bind()) if value == "" else label, value) for value, label in options]

    async def commit_name(self, value: str) -> None:
        """Apply a typed name. A name that cleans to nothing is refused."""
        if not clean_name(value):
            from chrys.foundation.i18n.formatting import format_message

            self._ports.notify(format_message(_NAME_EMPTY.bind()), severity="warning", timeout=10)
            return
        await self._ports.rename(value)
```

Wire the widgets in the same file with `@on` handlers: `Button.Pressed` on `#buddy-config-name-apply` calls `await self.commit_name(self.query_one("#buddy-config-name", Input).value)`; `Input.Submitted` on `#buddy-config-name` does the same; `Select.Changed` on `#buddy-config-model` awaits `self._ports.set_reply_model(str(event.value))`.

- [ ] **Step 4: Replace the mute marker with a real control + run tests**

Check for `Switch`: `uv run python -c "import textual.widgets as w; print(hasattr(w, 'Switch'))"`.
- If `True`: replace the `Input(id="buddy-config-muted-marker")` line with
  `yield Switch(value=self._ports.buddy().muted if self._ports.buddy() else False, id="buddy-config-muted")`
  and add `@on(Switch.Changed, "#buddy-config-muted")` → `await self._ports.set_muted(event.value)`.
- If `False`: use `yield Checkbox(self._t(_MUTED_LABEL.bind()), value=..., id="buddy-config-muted")` with `@on(Checkbox.Changed, "#buddy-config-muted")`.

Run: `uv run pytest tests/app/tui/screens/buddy_config/test_dialog.py -n0 -q -k settings_pane`
Expected: PASS.

- [ ] **Step 5: Commit** (only if authorized) with the pane and test paths.

---

## Task 7: Appearance pane (frame list + import/remove)

**Files:**
- Create: `src/chrys/app/tui/screens/buddy_config/panes/appearance.py`
- Test: extend `tests/app/tui/screens/buddy_config/test_dialog.py`

**Reuse:** `screens/dialogs/file_picker.py::FilePicker` (`FilePickerMode.FILE`, `extensions=frozenset({".png"})`).

- [ ] **Step 1: Write the failing test**

```python
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
    ports.custom_frames = {4}
    pane = AppearancePane(ports, locale_controller=None)

    await pane.remove(4)

    assert ("remove", 4) in ports.calls


def test_appearance_lists_six_frames() -> None:
    from chrys.app.features.buddy.animation import FRAME_COUNT
    from chrys.app.tui.screens.buddy_config.panes.appearance import AppearancePane

    assert FRAME_COUNT == 6
    pane = AppearancePane(StubPorts(), locale_controller=None)
    assert len(pane.frame_rows()) == 6
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/app/tui/screens/buddy_config/test_dialog.py -n0 -q -k appearance`
Expected: FAIL — module missing.

- [ ] **Step 3: Write the implementation**

```python
# src/chrys/app/tui/screens/buddy_config/panes/appearance.py
# Copyright (c) Huawei Technologies Co., Ltd. 2026. All rights reserved.

"""The dialog's Appearance tab: manage the current species' six custom frames."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Button, Static

from chrys.app.features.buddy.animation import FRAME_COUNT
from chrys.app.tui.i18n import render_str
from chrys.foundation.i18n import msg

if TYPE_CHECKING:
    from pathlib import Path

    from chrys.app.tui.i18n import LocaleController
    from chrys.app.tui.screens.buddy_config.ports import BuddyConfigPorts, FrameState

_HINT = msg(
    "tui.buddy_config.appearance.hint",
    fallback="Files are <species>_<frame>.png; leaving one out uses the built-in art for that frame.",
)
_STATE_BUILTIN = msg("tui.buddy_config.appearance.state.builtin", fallback="Built-in")
_STATE_CUSTOM = msg("tui.buddy_config.appearance.state.custom", fallback="Custom")
_IMPORT = msg("tui.buddy_config.action.import", fallback="Import")
_REMOVE = msg("tui.buddy_config.action.remove", fallback="Remove")
_OPEN = msg("tui.buddy_config.action.open_folder", fallback="Open folder")


@dataclass(frozen=True)
class FrameRow:
    frame: int
    state: FrameState


class AppearancePane(Widget):
    """Import or remove a custom PNG for each of the six frames."""

    DEFAULT_CSS = """
    AppearancePane { height: 1fr; }
    AppearancePane .frame-row { height: auto; }
    """

    def __init__(self, ports: BuddyConfigPorts, *, locale_controller: LocaleController | None = None) -> None:
        super().__init__()
        self._ports = ports
        self._locale_controller = locale_controller

    def frame_rows(self) -> list[FrameRow]:
        return [FrameRow(frame, self._ports.frame_state(frame)) for frame in range(FRAME_COUNT)]

    def _t(self, ref) -> str:
        return render_str(self._locale_controller, ref)

    def compose(self) -> ComposeResult:
        for row in self.frame_rows():
            state = _STATE_CUSTOM if row.state.value == "custom" else _STATE_BUILTIN
            yield Static(f"{row.frame}: {self._t(state.bind())}", classes="frame-row", id=f"frame-state-{row.frame}")
            yield Button(self._t(_IMPORT.bind()), id=f"frame-import-{row.frame}")
            yield Button(self._t(_REMOVE.bind()), id=f"frame-remove-{row.frame}")
        yield Button(self._t(_OPEN.bind()), id="buddy-config-open-folder")
        yield Static(self._t(_HINT.bind()), classes="frame-row")

    async def import_into(self, frame: int, source: Path) -> None:
        await self._ports.import_frame(frame, source)

    async def remove(self, frame: int) -> None:
        await self._ports.remove_frame(frame)
```

Add `@on(Button.Pressed)` handlers: `#frame-import-<n>` pushes a `FilePicker(mode=FilePickerMode.FILE, extensions=frozenset({".png"}), title=...)` whose result callback awaits `self.import_into(n, Path(result))` when `result`; `#frame-remove-<n>` awaits `self.remove(n)`; `#buddy-config-open-folder` calls `self._ports.open_assets_dir()`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/app/tui/screens/buddy_config/test_dialog.py -n0 -q -k appearance`
Expected: PASS.

- [ ] **Step 5: Commit** (only if authorized).

---

## Task 8: The dialog itself

**Files:**
- Create: `src/chrys/app/tui/screens/buddy_config/dialog.py`, `dialog.tcss`, `__init__.py`
- Test: extend `tests/app/tui/screens/buddy_config/test_dialog.py`

- [ ] **Step 1: Write the failing test** (real app, real modal)

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/app/tui/screens/buddy_config/test_dialog.py::test_dialog_opens_on_the_profile_tab -n0 -q`
Expected: FAIL — module missing.

- [ ] **Step 3: Write the implementation**

```python
# src/chrys/app/tui/screens/buddy_config/dialog.py
# Copyright (c) Huawei Technologies Co., Ltd. 2026. All rights reserved.

"""The Buddy configuration dialog: a tabbed modal over the ports."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, TabbedContent, TabPane

from chrys.app.tui.binding_display import CLOSE_BINDING, localized_binding
from chrys.app.tui.i18n import render_str
from chrys.app.tui.screens.buddy_config.panes.appearance import AppearancePane
from chrys.app.tui.screens.buddy_config.panes.profile import ProfilePane
from chrys.app.tui.screens.buddy_config.panes.settings import SettingsPane
from chrys.app.tui.screens.dialogs.base import BaseDialog
from chrys.foundation.i18n import msg

if TYPE_CHECKING:
    from chrys.app.tui.i18n import LocaleController
    from chrys.app.tui.screens.buddy_config.ports import BuddyConfigPorts

PROFILE_TAB_ID = "buddy-config-tab-profile"
APPEARANCE_TAB_ID = "buddy-config-tab-appearance"
SETTINGS_TAB_ID = "buddy-config-tab-settings"

_TITLE = msg("tui.buddy_config.title", fallback="Buddy")
_TAB_PROFILE = msg("tui.buddy_config.tab.profile", fallback="Profile")
_TAB_APPEARANCE = msg("tui.buddy_config.tab.appearance", fallback="Appearance")
_TAB_SETTINGS = msg("tui.buddy_config.tab.settings", fallback="Settings")
_REHATCH = msg("tui.buddy_config.action.rehatch", fallback="Re-hatch")
_CLOSE = msg("tui.buddy_config.action.close", fallback="Close")
_STATUS = msg("tui.buddy_config.status.autosave", fallback="Changes are saved as you make them")


class BuddyConfigDialog(BaseDialog[None]):
    """See a buddy and make the changes the design permits."""

    CSS_PATH = "dialog.tcss"

    BINDINGS: ClassVar[list] = [localized_binding("escape", "close", CLOSE_BINDING, show=False, priority=True)]

    def __init__(self, ports: BuddyConfigPorts, *, locale_controller: LocaleController | None = None) -> None:
        super().__init__()
        self._ports = ports
        self._locale_controller = locale_controller

    @property
    def active_tab(self) -> str:
        return self.query_one(TabbedContent).active

    def _t(self, ref) -> str:
        return render_str(self._locale_controller, ref)

    def compose(self) -> ComposeResult:
        has_buddy = self._ports.buddy() is not None
        with TabbedContent(initial=PROFILE_TAB_ID, id="buddy-config-tabs"):
            with TabPane(self._t(_TAB_PROFILE.bind()), id=PROFILE_TAB_ID):
                yield ProfilePane(self._ports, locale_controller=self._locale_controller)
            if has_buddy:
                with TabPane(self._t(_TAB_APPEARANCE.bind()), id=APPEARANCE_TAB_ID):
                    yield AppearancePane(self._ports, locale_controller=self._locale_controller)
                with TabPane(self._t(_TAB_SETTINGS.bind()), id=SETTINGS_TAB_ID):
                    yield SettingsPane(self._ports, locale_controller=self._locale_controller)
        with Horizontal(id="buddy-config-footer"):
            yield Button(self._t(_REHATCH.bind()), id="buddy-config-rehatch", variant="error", disabled=not has_buddy)
            yield Button(self._t(_CLOSE.bind()), id="buddy-config-close")
            yield Button(self._t(_STATUS.bind()), id="buddy-config-status", disabled=True)

    def action_close(self) -> None:
        self.dismiss(None)
```

Add a `@on(Button.Pressed, "#buddy-config-close")` → `self.dismiss(None)`, and `@on(Button.Pressed, "#buddy-config-rehatch")` that pushes a `ConfirmDialog` (see Task 9 for the port call); on confirm `await self._ports.rehatch()`.

```css
/* src/chrys/app/tui/screens/buddy_config/dialog.tcss */
BuddyConfigDialog { align: center middle; }
#buddy-config-tabs { width: 84; height: 26; }
#buddy-config-footer { height: auto; }
```

```python
# src/chrys/app/tui/screens/buddy_config/__init__.py
# Copyright (c) Huawei Technologies Co., Ltd. 2026. All rights reserved.

"""The Buddy configuration dialog."""

from chrys.app.tui.screens.buddy_config.dialog import BuddyConfigDialog

__all__ = ["BuddyConfigDialog"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/app/tui/screens/buddy_config/test_dialog.py -n0 -q`
Expected: PASS (all dialog tests).

- [ ] **Step 5: Commit** (only if authorized).

---

## Task 9: The coordinator

**Files:**
- Create: `src/chrys/app/tui/screens/main/buddy_config_coordinator.py`
- Test: `tests/app/tui/screens/buddy_config/test_coordinator.py` (extend)

- [ ] **Step 1: Write the failing test**

```python
async def test_coordinator_renames_through_the_action(monkeypatch) -> None:
    from chrys.app.features.buddy import actions
    from chrys.app.tui.screens.main.buddy_config_coordinator import BuddyConfigCallbacks, BuddyConfigCoordinator
    from chrys.foundation.config.settings import Settings
    from tests.app.tui.screens.buddy_config.support import _record

    seen: list[str] = []
    monkeypatch.setattr(actions, "rename", lambda name: seen.append(name))
    monkeypatch.setattr(actions, "current_buddy", lambda: _record())

    coordinator = BuddyConfigCoordinator(
        BuddyConfigCallbacks(
            save_settings=_noop_save_settings,
            notify=lambda *a, **k: None,
            push_screen=lambda *a, **k: None,
            settings=lambda: Settings(),
            model_options=lambda: [("", "Follow active")],
            open_path=lambda path: None,
        )
    )

    await coordinator.rename("Mochi")

    assert seen == ["Mochi"]


async def _noop_save_settings(values, remove) -> None:
    return None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/app/tui/screens/buddy_config/test_coordinator.py -n0 -q -k renames`
Expected: FAIL — module missing.

- [ ] **Step 3: Write the implementation**

```python
# src/chrys/app/tui/screens/main/buddy_config_coordinator.py
# Copyright (c) Huawei Technologies Co., Ltd. 2026. All rights reserved.

"""Implements ``BuddyConfigPorts`` for the main screen."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from chrys.app.features.buddy import actions, assets
from chrys.app.features.buddy.model import Buddy, Species
from chrys.app.tui.screens.buddy_config.ports import FrameState

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping, Sequence

    from chrys.foundation.config.settings import Settings
    from chrys.foundation.i18n import MessageRef

logger = logging.getLogger(__name__)

REPLY_MODEL_KEY = "model.role.buddy_model_id"
_SAVE_FAILED = "Buddy save file could not be updated"
_IMPORT_FAILED = "Buddy artwork could not be installed"


@dataclass(frozen=True, slots=True)
class BuddyConfigCallbacks:
    """Screen-supplied effects the coordinator needs but does not own."""

    save_settings: Callable[[Mapping[str, Any], tuple[str, ...]], Awaitable[None]]
    notify: Callable[..., None]
    push_screen: Callable[..., Any]
    settings: Callable[[], Settings]
    model_options: Callable[[], Sequence[tuple[str, str]]]
    open_path: Callable[[Path], None]


class BuddyConfigCoordinator:
    """Buddy-config ports; buddy writes run on a thread under the save lock."""

    def __init__(self, callbacks: BuddyConfigCallbacks) -> None:
        self._callbacks = callbacks

    # ── reads ─────────────────────────────────────────────────────────
    def buddy(self) -> Buddy | None:
        return actions.current_buddy()

    def species(self) -> Species | None:
        buddy = actions.current_buddy()
        return buddy.species if buddy is not None else None

    def frame_state(self, frame: int) -> FrameState:
        species = self.species()
        if species is not None and assets.is_custom_frame(species, frame):
            return FrameState.CUSTOM
        return FrameState.BUILTIN

    def assets_dir(self) -> Path:
        return assets.assets_dir()

    def reply_model(self) -> str:
        return self._callbacks.settings().buddy_model

    def model_options(self) -> list[tuple[str, str]]:
        return list(self._callbacks.model_options())

    # ── writes ────────────────────────────────────────────────────────
    async def rename(self, name: str) -> None:
        await self._buddy_write(actions.rename, name)

    async def set_muted(self, muted: bool) -> None:
        await self._buddy_write(actions.set_muted, muted)

    async def rehatch(self) -> None:
        await self._buddy_write(actions.rehatch)

    async def import_frame(self, frame: int, source: Path) -> None:
        species = self.species()
        if species is None:
            return
        try:
            await asyncio.to_thread(assets.install_frame, species, frame, source)
        except OSError:
            logger.warning(_IMPORT_FAILED, exc_info=True)
            self._warn(_IMPORT_FAILED)

    async def remove_frame(self, frame: int) -> None:
        species = self.species()
        if species is None:
            return
        with contextlib.suppress(OSError):
            await asyncio.to_thread(assets.remove_frame, species, frame)

    async def set_reply_model(self, model_id: str) -> None:
        if model_id:
            await self._callbacks.save_settings({REPLY_MODEL_KEY: model_id}, ())
        else:
            await self._callbacks.save_settings({}, (REPLY_MODEL_KEY,))

    # ── chrome ────────────────────────────────────────────────────────
    def open_assets_dir(self) -> None:
        directory = self.assets_dir()
        with contextlib.suppress(Exception):
            directory.mkdir(parents=True, exist_ok=True)
            self._callbacks.open_path(directory)

    def notify(self, message: MessageRef | str, *, severity: str = "information", timeout: float = 10) -> None:
        self._callbacks.notify(message, severity=severity, timeout=timeout)

    # ── internals ─────────────────────────────────────────────────────
    async def _buddy_write(self, write: Callable[..., Any], *args: Any) -> None:
        try:
            await asyncio.to_thread(write, *args)
        except OSError:
            logger.warning(_SAVE_FAILED, exc_info=True)
            self._warn(_SAVE_FAILED)

    def _warn(self, text: str) -> None:
        self._callbacks.notify(text, severity="warning", timeout=10)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/app/tui/screens/buddy_config/test_coordinator.py -n0 -q`
Expected: PASS.

- [ ] **Step 5: Commit** (only if authorized).

---

## Task 10: Wiring — MainScreen, `/buddy config`, sidebar button

**Files:**
- Modify: `src/chrys/app/tui/screens/main/config_actions.py`, `screen.py`, `view_adapter.py`, `buddy_command.py`, `ports.py`, `src/chrys/app/tui/widgets/sidebar/buddy.py`
- Test: `tests/app/tui/screens/main/test_buddy_command.py` (extend) + `tests/app/tui/behaviors/` (new sidebar test)

- [ ] **Step 1: Write the failing tests**

```python
# in tests/app/tui/screens/main/test_buddy_command.py
def test_subcommands_include_config_when_a_buddy_exists(...) -> None:
    ...
    assert "config" in [name for name, _ in controller.subcommands()]
```

```python
# new: tests/app/tui/screens/buddy_config/test_entry_points.py
async def test_slash_command_opens_the_dialog(...) -> None: ...
async def test_sidebar_button_opens_the_dialog(...) -> None: ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/app/tui/screens/main/test_buddy_command.py tests/app/tui/screens/buddy_config/test_entry_points.py -n0 -q`
Expected: FAIL — `config` absent / dialog not opened.

- [ ] **Step 3: Implement the wiring**

1. `screens/main/ports.py` — add to `BuddyCommandView`:
   ```python
   def open_buddy_config(self) -> None: ...
   ```
2. `screens/main/buddy_command.py` — add the subcommand and route it:
   ```python
   _SUBCOMMAND_CONFIG = msg("tui.buddy.subcommand.config", fallback="Configure your buddy")
   ```
   In `subcommands()`, append `("config", self._render_message(_SUBCOMMAND_CONFIG.bind()))` to the list returned when a buddy exists. In `handle()`, before the pet branch:
   ```python
   if split_command(arg)[0] == "config":
       self._view.open_buddy_config()
       return
   ```
3. `screens/main/view_adapter.py` — implement it (it already forwards `notify_buddy`/`refresh_buddy_panel`):
   ```python
   def open_buddy_config(self) -> None:
       self._screen.open_buddy_config()
   ```
4. `screens/main/config_actions.py` — add, mirroring `open_settings`:
   ```python
   def open_buddy_config(self) -> None:
       """Open the Buddy configuration dialog."""
       from chrys.app.tui.screens.buddy_config import BuddyConfigDialog

       coordinator = self._callbacks.buddy_config_coordinator()
       dialog = BuddyConfigDialog(coordinator, locale_controller=self._locale_controller)
       self._view.push_screen(dialog)
   ```
   and declare `buddy_config_coordinator: Callable[[], BuddyConfigCoordinator]` on the callbacks dataclass next to `settings_coordinator` (import under `TYPE_CHECKING`).
5. `screens/main/screen.py` — add lazily-created ownership like `_settings_coordinator`:
   ```python
   def _buddy_config_coordinator(self) -> BuddyConfigCoordinator:
       from chrys.app.tui.screens.main.buddy_config_coordinator import (
           BuddyConfigCallbacks,
           BuddyConfigCoordinator,
       )

       instance = getattr(self, "_buddy_config_coordinator_instance", None)
       if instance is None:
           instance = BuddyConfigCoordinator(
               BuddyConfigCallbacks(
                   save_settings=self._settings_persistence().persist_patch,
                   notify=self._notify_buddy_config,
                   push_screen=self.push_screen,
                   settings=lambda: self._loaded_settings_for_panel().settings,
                   model_options=self._buddy_model_options,
                   open_path=self._open_path_in_os,
               )
           )
           self._buddy_config_coordinator_instance = instance
       return instance

   def open_buddy_config(self) -> None:
       self._config_actions.open_buddy_config()
   ```
   Wire `buddy_config_coordinator=self._buddy_config_coordinator` into the `RuntimeConfigController` construction (near `settings_coordinator=...` at `screen.py:394`). Implement the small helpers:
   - `_notify_buddy_config(message, *, severity, timeout)` → `self.notify(...)` with `markup=False`;
   - `_buddy_model_options()` → `[( "", follow_label )] + [(p.model_id, p.model_id) for p in registry.profiles()]` using the same registry the settings dialog uses;
   - `_open_path_in_os(path)` → platform opener, guarded;
   - `_settings_persistence()` / `_loaded_settings_for_panel()` → reuse the existing accessors backing `_settings_coordinator` (`rg -n "_settings_persistence|_loaded_settings" src/chrys/app/tui/screens/main/screen.py`).
   Add the sidebar handler:
   ```python
   @on(BuddyPanel.ConfigRequested)
   def _on_buddy_config_requested(self, _event: BuddyPanel.ConfigRequested) -> None:
       self.open_buddy_config()
   ```
6. `widgets/sidebar/buddy.py` — add the ⚙ button and message:
   ```python
   class ConfigRequested(Message):
       """The user asked to open the Buddy configuration dialog."""
   ```
   In `compose()`, after `#buddy-info`: `yield Button(self._render_message(_BUDDY_CONFIGURE.bind()), id="buddy-configure", classes="buddy-configure")` with a module-level `_BUDDY_CONFIGURE = msg("tui.sidebar.buddy.configure", fallback="Configure")`. Handle it so it does not also pet:
   ```python
   @on(Button.Pressed, "#buddy-configure")
   def _on_configure(self, event: Button.Pressed) -> None:
       event.stop()
       self.post_message(self.ConfigRequested())
   ```
   Ensure `on_click` (the pet handler at `buddy.py:363`) ignores clicks whose control is the button (`if event.widget is not None and event.widget.id == "buddy-configure": return`), or move petting to a specific sprite target.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/app/tui/screens/buddy_config tests/app/tui/screens/main/test_buddy_command.py -n0 -q`
Expected: PASS.

- [ ] **Step 5: Commit** (only if authorized).

---

## Task 11: i18n

**Files:**
- Modify: `locales/chrys.pot`, `locales/zh-Hans/LC_MESSAGES/chrys.po`, `src/chrys/foundation/i18n/_catalogs/zh-Hans/LC_MESSAGES/chrys.mo`
- Modify: `tests/foundation/i18n/_buddy_catalog_oracle_ids.py`, `tests/foundation/i18n/test_catalog_oracle.py`

- [ ] **Step 1: Extract and update**

Run: `uv run python scripts/i18n.py extract`
Run: `uv run python scripts/i18n.py update`
Expected: the new `tui.buddy_config.*`, `tui.buddy.subcommand.config` and `tui.sidebar.buddy.configure` ids appear as new entries in `locales/zh-Hans/LC_MESSAGES/chrys.po`.

- [ ] **Step 2: Translate every new entry**

In `locales/zh-Hans/LC_MESSAGES/chrys.po`, fill `msgstr` for each new id (and drop any `#, fuzzy` flag on the ones you translate). Chinese text for the batch:
`title` Buddy→伙伴, `tab.profile` Profile→档案, `tab.appearance` Appearance→外观, `tab.settings` Settings→设置, `field.name`→名称, `field.muted`→静音, `field.reply_model`→回复模型, `reply_model.follow`→跟随当前模型, `action.rehatch`→重新孵蛋, `action.close`→关闭, `action.import`→导入, `action.remove`→移除, `action.open_folder`→打开文件夹, `action.apply`→应用, `action.hatch`→孵蛋, `status.autosave`→改动即时保存, `appearance.hint`→文件名为 `<species>_<frame>.png`；缺少某帧则用该帧的内置图。, `appearance.state.builtin`→内置, `appearance.state.custom`→自定义, `empty.hint`→还没有伙伴。用 `/buddy hatch` 看看蛋里是什么。, `toast.name_empty`→名字至少要有一个可见字符。, `subcommand.config`→配置你的伙伴, `sidebar.buddy.configure`→配置。

- [ ] **Step 3: Compile and check**

Run: `uv run python scripts/i18n.py compile`
Run: `uv run python scripts/i18n.py check`
Run: `git status --porcelain` (a second `check` must leave it unchanged).

- [ ] **Step 4: Update the catalog oracle**

Add every new id to `tests/foundation/i18n/_buddy_catalog_oracle_ids.py`'s `BUDDY_MESSAGE_IDS` set, and bump the literal in `tests/foundation/i18n/test_catalog_oracle.py`:
```python
assert len(EXPECTED_MESSAGE_IDS) == <old 2176 + number of ids added>
```
Also add the new ids to the oracle's per-area set and confirm the aggregate imports it (the buddy area is already aggregated).

- [ ] **Step 5: Run the oracle**

Run: `uv run pytest tests/foundation/i18n/test_catalog_oracle.py -n0 -q`
Expected: PASS.

- [ ] **Step 6: Commit** (only if authorized).

---

## Task 12: Docs

**Files:**
- Modify: `docs/en/reference/tui-slash-commands.md`, `docs/zh-Hans/reference/tui-slash-commands.md`

- [ ] **Step 1: Update the English `/buddy` row**

In `docs/en/reference/tui-slash-commands.md:55`, add `config` to the sub-command list and the description: "`config`: open the Buddy configuration dialog (rename, mute, reply model, custom artwork, re-hatch)." Update the sentence that lists when options become available so it is accurate.

- [ ] **Step 2: Update the Chinese row**

Mirror the change in `docs/zh-Hans/reference/tui-slash-commands.md:55`: add `config`：打开伙伴配置对话框（改名、静音、回复模型、自定义贴图、重新孵蛋）。

- [ ] **Step 3: Update the settings reference if the reply model's description changes**

If the dialog changes how the reply model is described, mirror `docs/en/reference/settings.md:52` and `docs/zh-Hans/reference/settings.md:52`. Otherwise leave them.

- [ ] **Step 4: Verify the docs load**

Run: `uv run pytest tests/app/tui/screens/guides -n0 -q` (or the docs/index check the repo uses: `rg -n "index.yaml" tests | head`).
Expected: PASS.

- [ ] **Step 5: Commit** (only if authorized).

---

## Task 13: End-to-end and performance tests

**Files:**
- Create: `tests/app/tui/screens/buddy_config/test_overlay_budget.py`
- Extend: `tests/app/tui/screens/buddy_config/test_dialog.py`

- [ ] **Step 1: Write the performance test**

```python
# tests/app/tui/screens/buddy_config/test_overlay_budget.py
# Copyright (c) Huawei Technologies Co., Ltd. 2026. All rights reserved.

"""Opening the Buddy dialog must not restyle or relayout MainScreen."""

from __future__ import annotations

from textual.widgets import Footer

from chrys.app.tui.screens.buddy_config import BuddyConfigDialog
from tests.app.tui.screens.buddy_config.support import StubPorts
from tests.support.pilot_barrier import screen_is_settled
from tests.support.tui_app_harness import make_chrys_app
from tests.support.waiting import wait_for


async def test_opening_the_dialog_does_not_restyle_or_relayout(tmp_path, monkeypatch) -> None:
    app = make_chrys_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        main = app.screen
        await wait_for(
            lambda: screen_is_settled(app, main), pilot=pilot, description="settled main screen", stable_observations=4
        )

        style_updates: list[bool] = []
        layout_refreshes: list[None] = []
        monkeypatch.setattr(main, "update_node_styles", lambda animate=True: style_updates.append(animate))
        monkeypatch.setattr(main, "_refresh_layout", lambda *_a, **_k: layout_refreshes.append(None))

        dialog = BuddyConfigDialog(StubPorts(), locale_controller=None)
        app.push_screen(dialog)
        await wait_for(lambda: app.screen is dialog and dialog.is_mounted, pilot=pilot, description="dialog open")

        assert style_updates == []
        assert layout_refreshes == []
```

- [ ] **Step 2: Run test to verify it fails or passes as expected**

Run: `uv run pytest tests/app/tui/screens/buddy_config/test_overlay_budget.py -n0 -q`
Expected: PASS if the dialog is a plain modal (no MainScreen restyle). If it FAILS, find the restyle/layout trigger (a binding refresh or a class change on MainScreen) and fix the dialog so it stays screen-local.

- [ ] **Step 3: Add the behavior tests**

In `test_dialog.py`, add tests that drive the panes against `StubPorts` for: rename commit, mute toggle, reply-model select, import via picker result, remove, and re-hatch confirmation (push `ConfirmDialog`, press its confirm button, assert `("rehatch", None)` in `ports.calls`). Use `click_when_settled` for button presses and `wait_for` for the asserted effect.

- [ ] **Step 4: Run the whole feature suite**

Run: `uv run pytest tests/app/tui/screens/buddy_config tests/app/features/buddy tests/app/tui/screens/main/test_buddy_command.py -n0 -q`
Expected: PASS.

- [ ] **Step 5: Full verification for the change**

Run: `uv run python scripts/chrys_test.py --smart --paths <every path created/modified in this plan>`
Expected: PASS. This is a Smart Test pass, not the full suite.

- [ ] **Step 6: Commit** (only if authorized).

---

## Self-Review notes (run after writing, fix inline)

**Spec coverage:** goals/non-goals → Tasks 1–3 (data), 4–9 (dialog), 10 (entry), 11 (i18n), 12 (docs);
every "Requirements" row maps to a task. The `assets_dir` promotion (Task 3) and `rehatch` (Task 2) are the two
feature-layer additions the spec names. Error handling appears in Task 9 (`_buddy_write`, `import_frame`).
Performance and guards appear in Tasks 10 and 13. All covered.

**Type consistency:** `FrameState` / `BuddyConfigPorts` (Task 4) are used verbatim by Tasks 5–9;
`BuddyConfigCallbacks` field names (`save_settings`, `notify`, `push_screen`, `settings`, `model_options`,
`open_path`) match between Tasks 9 and 10; `REPLY_MODEL_KEY` matches the setting key in the design.

**Known follow-ups an implementer must confirm against the tree** (they are exact `rg` targets, not open design):
`render_portrait` keyword args (`widgets/sidebar/buddy.py`), the settings-persistence accessor name in
`screen.py`, `Switch` availability in the pinned Textual, and `_open_path_in_os` (may need a small platform helper
in `foundation/platform/`). If any of these differ, adjust the call site — the interfaces above do not change.
