# Buddy configuration dialog

Status: design approved 2026-10-04; implemented on `feat/buddy-config`.

A single modal, opened by `/buddy config` or from the footer's **Buddy** binding
(F7), that lets the user see their buddy and make the few changes the design
permits:
rename it, mute it, pick the model that writes its replies, and install or
remove custom pixel artwork for their species. It never changes what the buddy
*is* — species, rarity, shiny, traits and progress stay whatever the hatch
draw and the turns made them. Only a full re-hatch (a fresh random draw) can
change those; the feature-layer action `actions.rehatch()` still exists, but the
dialog no longer exposes it.

## Goals

- One place to see a buddy's identity and progress, with a live portrait.
- Edit the mild, non-identity fields: name, mute, reply model.
- Manage the custom PNG overrides for the current species, with preview.

## Non-goals

- Editing species, rarity, shiny, traits, level or XP. Those remain the hatch
  draw's and the turn counters' to decide.
- New global settings (enable/disable, animation toggle, XP toggle were
  considered and dropped). The only setting touched is the existing
  `model.role.buddy_model_id`.
- Text-command equivalents in headless/ACP. `/buddy` is a TUI slash command
  (`screens/main/buddy_command.py`); there is nothing to add for headless.
- A general asset library: only the current species' six frames are managed.
- Committing to git (project rule: commit only when asked).

## Requirements (from brainstorming)

| Decision | Choice |
| --- | --- |
| Scope | One unified panel |
| Carrier | Dedicated modal dialog, `/buddy config` + footer F7 binding |
| Editable | Mild: name, mute, reply model, custom PNG; identity read-only |
| Behavior toggles | Reply model + mute only |
| Appearance | Current species only, with import/remove/open-folder |
| Reset | Dropped: the dialog never re-rolls (a fresh draw destroys progress); the feature-layer `actions.rehatch()` stays, unreached |
| Frontends | TUI-only dialog |
| Save model | Edit commits immediately (Approach A) |

## Architecture

A new dialog package, mirroring `screens/settings/`:

```
app/tui/screens/buddy_config/
├── __init__.py          # exports BuddyConfigDialog and FrameState
├── dialog.py            # BuddyConfigDialog(BaseDialog[None]): the tabbed modal
├── dialog.tcss          # layout and styling
├── ports.py             # BuddyConfigPorts protocol + FrameState
└── panes/
    ├── __init__.py
    ├── profile.py       # read-only facts + live portrait
    ├── appearance.py    # 6-frame asset manager + preview
    └── settings.py      # name input, mute checkbox, reply-model select
```

The adapter lives beside the other MainScreen ports:

- `app/tui/screens/main/buddy_config_coordinator.py` implements
  `BuddyConfigPorts`, is owned by `MainScreen`, and is injected into the dialog
  the same way `SettingsCoordinator` is injected into `SettingsDialog`.

The dialog holds no file or settings knowledge: it reads state through the
ports and calls port methods for every change. The adapter owns all blocking
work (buddy writes wait on the save-file lock) on `asyncio.to_thread`, and turns
failures into toasts.

### Entry points

- `/buddy config`: a new `_SUBCOMMAND_CONFIG` in `screens/main/buddy_command.py`
  that pushes the dialog instead of going through `handle_buddy_command`. Always
  available; the dialog shows its empty (egg) state when no buddy exists. The
  existing subcommand hint list still leads with `hatch` when there is no buddy.
- Footer: a **Buddy** binding (F7) on the footer key row, alongside the
  Sessions/Agents/Models/Logs bindings. `MainScreen` declares it as a
  `localized_binding("f7", "buddy_config", _BUDDY_CONFIG_BINDING)`, whose
  `action_buddy_config` calls the same open path as `/buddy config`. Always
  available. The earlier in-panel **Configure** button at the bottom of
  `BuddyPanel` — with its `ConfigRequested` message and pet-guard click
  handler — was removed when the entry point moved to the footer.

## Interfaces

```python
class FrameState(StrEnum):
    BUILTIN = "builtin"      # no custom file; the built-in artwork draws
    CUSTOM = "custom"        # a valid <species>_<frame>.png is installed

class BuddyConfigPorts(Protocol):
    def buddy(self) -> Buddy | None: ...          # None before one has hatched
    # Read-only identity/progress come from buddy(). The Appearance pane's only
    # read is frame_state(); species() and assets_dir() serve the adapter's own
    # writes and are never called by the dialog.
    def species(self) -> Species | None: ...      # the saved buddy's species, None when there is none
    def frame_state(self, frame: int) -> FrameState: ...
    def assets_dir(self) -> Path: ...
    # Edits — each one commits immediately; OSError surfaces as a warning toast.
    async def rename(self, name: str) -> None: ...
    async def set_muted(self, muted: bool) -> None: ...
    async def set_reply_model(self, model_id: str) -> None: ...
    async def hatch(self) -> None: ...            # draw the first buddy (the empty-state button)
    async def import_frame(self, frame: int, source: Path) -> None: ...
    async def remove_frame(self, frame: int) -> None: ...
    # Reply-model field
    def reply_model(self) -> str: ...                    # the stored settings.buddy_model; "" means "follow active"
    def model_options(self) -> list[tuple[str, str]]: ...  # (value, label); the pane labels the ("", …) entry "follow"
    # Chrome
    def open_assets_dir(self) -> None: ...               # opens assets_dir() in the OS file manager
    def notify(self, message: MessageRef | str, *, severity: str, timeout: float) -> None: ...
```

`FrameState.frame_state` is decided by whether `assets_dir()/<species>_<frame>.png`
exists and decodes as an image.

## Data and persistence

All writes reuse the buddy feature's existing "lock + atomic replace" path
(`features/buddy/store.py::BuddyStore.update`), run off the event loop:

- **name** → `actions.rename()`; **mute** → `actions.set_muted()`.
- **reply model** → the settings store, key `model.role.buddy_model_id` (the
  same persistence path the settings panel uses).
- **import a frame** → validate the source decodes as an image (PIL), then
  atomically copy it to `assets_dir()/<species>_<frame>.png`. A file that fails
  validation writes nothing (no half-installed frame).
- **remove a frame** → delete that file.

The feature-layer action `actions.rehatch()` — which replaces the saved buddy
with a fresh draw — is kept (and unit-tested), but the dialog no longer reaches
it.

`pixel_sprites._get_assets_dir()` is promoted to a public `assets_dir()` so
`buddy_config` does not depend on a private name; `load_external_pixel_frame`
is updated to call it.

Reads happen when the dialog opens; the Profile portrait then re-reads the saved
buddy on every animation tick, so a rename made in another instance shows up
there while the dialog is open. The other panes keep what they read at mount: a
change made elsewhere reaches them only when the dialog is reopened. This is
accepted (the sidebar panel already polls the same file).

## UI / UX

`BuddyConfigDialog` is a `BaseDialog[None]` (modal, dismissed with Esc — a
priority binding — or a click outside the dialog) framed and centered like the
other dialogs: one bordered `#buddy-config-container` (`VerticalGroup`),
responsive at `width: 92%; max-width: 92; height: 85%; max-height: 48`, whose
only child is the `TabbedContent` — there is no button row. The
title is the container's border title and the autosave status ("Changes are
saved as you make them") is its border subtitle in a muted
(`border-subtitle-color: $text-muted`) ink — not a footer widget. Each tab pane
body is a `VerticalScroll` (`.buddy-config-pane-scroll`) with the Settings
dialog's padding, so an overflowing tab scrolls its own body. Content is grouped
in bordered `.buddy-config-section` boxes with `$secondary` titles, and each
setting is a Settings-style row: a fixed-width label plus the compact, frameless
`EnhancedInput`/`Select`/`Checkbox`. In-row actions (`Apply`, `Import`,
`Remove`, `Open folder`) are link-style `.buddy-config-link` buttons.

- **Profile** — a live animated portrait stacked above the read-only fields,
  each block centred on its own width with a blank line between them. The
  fields: name, species, rarity (with evolution stage), shiny, the four traits
  with their growth, level/XP, hatched date, turns/pets, persona. Values are
  formatted like `commands.buddy_card`.
- **Appearance** — a **Preview** section (a portrait preview, default frame 0,
  switchable by clicking a frame row) over a **Frames** section: six rows
  (frame 0–5) each showing state (built-in/custom) and link-style `[Import]` /
  `[Remove]`; an `[Open folder]` line and a hint naming
  `<species>_<frame>.png`. Import uses the existing
  `screens/dialogs/file_picker.py::FilePicker` in `FilePickerMode.FILE` filtered
  to `.png`.
- **Settings** — an **Identity** section (name: a fixed-width label + a compact
  frameless `EnhancedInput` with a link-style `[Apply]`) above a **Behaviour**
  section (a `Muted` `Checkbox` that carries its own label, then a reply-model
  `Select` whose first option is "follow the active model", value `""`). Unlike
  the rest of the chrome, the `Select`'s option labels deliberately do not
  retranslate on a live locale switch: resetting its options would re-post
  `Changed` and write the value back through the ports. A documented residual,
  not an API limit.
- **Empty state** — with no buddy, the Profile tab shows a pixel-art egg
  (`portrait.py::render_egg`: the same half-block pipeline as the portraits,
  inside the same corner frame but with neutral corners, since a rarity is only
  known after hatching) and a hint with an inline hatch button (calling
  `actions.hatch()`). Both the Appearance and the Settings tabs are hidden and
  not selectable until a buddy exists; an in-dialog hatch mounts both
  (`TabbedContent.add_pane`, without recomposing the dialog) and leaves the
  Profile tab active.

Details worth knowing: the portrait repaints on a 1/8 s timer that pauses while
the pane is hidden, and it and the frame preview pin their repaints to cached
geometry, so a tick never re-lays out; clicking a frame row marks it `-selected`
and points the preview at it. `chrys.tcss` gives the container its modal
background in both the plain and the `App:ansi` flavour, as the other dialogs
do.

The dialog is a modal, so opening it must not restyle, recompose or relayout
`MainScreen` (AGENTS performance rule); the portrait repaints only itself.

## i18n

Every user-facing string is a module-level `msg(...)` rendered through
`app/tui/i18n.py` — `render_str` for text sinks, and `Content.from_text` with
`markup=False` for widget captions. No raw English at notify/label/placeholder
sinks. New ids → run
`scripts/i18n.py extract → update`, translate every new/`#, fuzzy` entry in
`locales/zh-Hans/LC_MESSAGES/chrys.po`, `compile`, `check`, and add the ids to
`tests/foundation/i18n/_buddy_catalog_oracle_ids.py` with the bumped
`len(EXPECTED_MESSAGE_IDS)` in the same change.

## Documentation

User-visible change: update the buddy / `/buddy` section in both `docs/en/` and
`docs/zh-Hans/`, and register any new page in `docs/index.yaml`.

## Error handling

- Buddy save file unwritable or another instance wedged on the lock
  (`OSError`, including `TimeoutError`) → a warning toast in the style of
  `commands._SAVE_FAILED`; nothing in the dialog's in-memory state is faked.
- Import source not a decodable image → warning; nothing is written.
- Removing a frame whose file cannot be deleted (`OSError`) → warning; the row
  keeps showing the state the disk has.
- A typed name that cleans to nothing → warning from the pane; the saved name is
  left alone.
- No desktop file manager to reveal the assets folder → a warning toast from the
  MainScreen side; a genuine open failure is logged. Neither fails the dialog.
- Empty model list / no buddy → placeholder and empty state, no crash.
- Concurrent edits by another instance → each action is a locked
  read-modify-write; nothing is staged, so nothing is clobbered.

## Testing

Reusing the existing buddy test scaffolding
(`tests/orchestration/engine/test_buddy.py`, `tests/app/tui/behaviors/`,
`tests/app/tui/screens/main/test_buddy_command.py`):

- Dialog behavior under a real `run_test()`/`make_chrys_app`: `/buddy config`
  opens; tabs switch; rename commits; mute toggles; reply-model select
  persists to a temp config dir; import copies the file and updates the
  preview; remove falls back to built-in; Esc (or a click outside) dismisses
  the dialog.
- `BuddyConfigPorts` adapter unit tests: threaded save, `OSError` path.
- `actions.rehatch` unit test paired with `hatch`: with a record present the
  record is replaced (not reused); with none it is a no-op.
- `assets_dir()` promotion: `load_external_pixel_frame` still loads a planted
  file.
- i18n catalog oracle count.
- Performance: a populated MainScreen with the dialog open does not call
  `update_node_styles`/`_refresh_layout` or recompose the footer (spy test per
  AGENTS).
- Architecture guards stay green: no raw English at TUI sinks; files under
  2,000 lines; `widgets/` does not runtime-import `screens.*`.

## Risks and accepted trade-offs

- Immediate save means no undo; the user re-edits. Accepted.
- Re-hatch (the feature-layer `actions.rehatch()`) is irreversible and destroys
  progress; the dialog no longer offers it.
- Imported art is stored as supplied and normalized by the renderer at load
  (nearest-neighbor to 20×16), so the dialog does not resize on import.
- Only the Profile portrait live-refreshes on another instance's change (it
  re-reads the record on each animation tick); the other panes show it after a
  reopen.
- Opening the OS file manager (`[Open folder]`) is best-effort: with no file
  manager the MainScreen warns, a genuine failure is logged, and neither ever
  fails the dialog.
