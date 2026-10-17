# napari-lite — issue backlog (standalone project)

> Progress 2026-10-17: issues 00–20 and 23 are done on `main`, with two
> deviations recorded in the commits: pint stays an import-time dependency
> and pandas a core dependency (docs/benchmarks.md, pyproject). Issue 24:
> napari's `main` is still the pinned commit, so there was nothing to
> resync; a dry run of the routine is recorded in SYNC.md. Issue 25: README
> and release workflow done (docs/release.md); asking the napari
> maintainers about the name is open. Open: 21, 22 (layer list and
> controls), the first real resync, the name question.

Each `## NN · Title` section is one GitHub issue; `tools/create_issues.py` files them in order and
turns `{{NN}}` into real issue numbers. Facts below were measured on napari ebfc4a0
(2026-10-16), Linux, Python 3.13, PyQt6.

**The shape of the project**
- napari-lite is its own repo and package (`napari_lite`). It does not depend on napari.
- napari code arrives only through `tools/vendor.py`, on a `vendor` branch that nobody edits by hand.
  It copies 267 of napari's 538 modules (~77.6k lines) and rewrites `napari` → `napari_lite`.
- `main` = vendor + your work. Upstream updates come in with `git merge vendor`.
- **Shim at the same path.** Where copied code imports an app module (settings, theme, plugins...),
  write a small lite module at that same import path instead of editing every caller.
  Copied files stay close to napari, so merges stay easy. Mark own files with `# napari-lite: own code`
  in the first line; vendor.py never overwrites them.
- Spike result: with the 22 app modules replaced by throwaway stand-ins, the copied core imported in
  0.50 s (napari.components: 1.21 s) and all 7 layer types worked. Milestone M1 replaces the stand-ins
  with real shims.

---

## 00 · Create the repo skeleton
milestone: M0 Repo and copy · labels: tooling · depends:

### Tasks
- [ ] On GitHub, create an **empty** repo `napari-lite` (no README, no license: they come from the kit).
- [ ] Add `LICENSE` from `templates/LICENSE`: napari's BSD-3 text and copyright line kept, your line added.
      Required by BSD-3 because the repo contains napari code.
- [ ] Add `README.md`: what napari-lite is, "derived from napari (BSD-3)", link to napari, status: experimental.
- [ ] Add `pyproject.toml` from `templates/pyproject.toml`, `tools/`, `spikes/`, `bench/`, `tests/` from the kit.
- [ ] Layout: `src/napari_lite/` (package), `tests/` (own tests), `examples/`, `docs/`.
- [ ] Add `.github/workflows/ci.yml`: Python 3.11–3.13 on ubuntu/macos/windows, `pip install -e .[dev]`,
      `QT_QPA_PLATFORM=offscreen pytest tests` (napari's copied tests join in issue 11).

### Done when
- [ ] Repo exists with LICENSE, README, pyproject; CI runs (it may fail until issue 01).

---

## 01 · Copy napari with the vendoring tool (first run)
milestone: M0 Repo and copy · labels: tooling · depends: {{00}}

### Why
The copy must be reproducible: re-runnable against any napari commit, with every crossing into
napari's app code listed, so nothing is hand-copied and nothing is forgotten.

### Tasks
- [ ] `git switch -c vendor` (from the skeleton commit).
- [ ] `git clone https://github.com/napari/napari ../napari && git -C ../napari checkout <pin from vendor.toml>`.
- [ ] `python tools/vendor.py --napari ../napari` → `src/napari_lite/` + `VENDORED.json`.
- [ ] Check: 267 modules copied, no file still contains `from napari.` / `import napari`
      (`grep -rnE '^\s*(from|import)\s+napari(\s|\.)' src/napari_lite` is empty).
- [ ] Commit on `vendor`: `vendor: napari <sha>`. Then `git switch main && git merge vendor`.

### Done when
- [ ] `VENDORED.json` lists 55 crossings into 22 app modules (top ones: `settings` 17, `utils.theme` 7,
      `utils.action_manager` 5).

---

## 02 · Document and automate the resync routine
milestone: M0 Repo and copy · labels: tooling · depends: {{01}}

### Tasks
- [ ] `SYNC.md`: bump `pin` in `tools/vendor.toml` → on `vendor`: run vendor.py, commit → on `main`:
      `git merge vendor`, fix conflicts, run tests → log new/removed crossings in the PR.
- [ ] Rule: **never edit files on `vendor` by hand**; never run vendor.py on `main`.
- [ ] Rule: when a copied file needs a change, prefer a shim (new own-code module) over editing it;
      if you must edit it, keep the diff small and add a `# napari-lite:` comment explaining why.
- [ ] Weekly CI job: run `vendor.py --report` against napari `main`, and open an issue if the crossing list changed.

### Done when
- [ ] A dry-run resync to a newer napari commit merges cleanly into `main`.

---

## 03 · Own package entry point
milestone: M1 Imports without napari · labels: new-code · depends: {{01}}

### Tasks
- [ ] Replace `src/napari_lite/__init__.py` with `templates/__init__.py` (own-code marker; lazy exports
      `Viewer`, `imshow`, `run`, `components`, `layers`, `utils`).
- [ ] Remove napari-specific startup from it: install-path check, `_check_numpy_version` side effects stay only if needed.

### Done when
- [ ] `python -c "import napari_lite"` < 0.15 s and imports no Qt, vispy or pydantic.

---

## 04 · Replace napari settings with an in-memory defaults model
milestone: M1 Imports without napari · labels: new-code · depends: {{03}}

### Why
`napari.settings` is the biggest crossing: 17 importers, including `components/viewer_model.py`,
`components/canvas.py`, `_vispy/canvas.py`, `_vispy/layers/points.py`, `_qt/widgets/qt_dims_slider.py`.
The spike showed two requirements: values must be real napari defaults (e.g. camera orientation enums),
and they must be **evented** — `components/canvas.py` subscribes to
`settings.application.events.grid_stride`.

### Tasks
- [ ] Generate the field list: `python spikes/make_defaults.py` (needs napari once) → `spikes/defaults.json`.
- [ ] Write `src/napari_lite/settings/__init__.py` (own code): small `EventedModel` sections
      (`application`, `appearance`, `experimental`, `shortcuts`, `advanced`) with only the fields copied code
      reads, same names and defaults; `get_settings()` returns a singleton. No files, no YAML, no pydantic-settings.
- [ ] Also provide `settings/_constants.py` and `settings/_application.py` names that are imported
      (`LoopMode`, `GridWidth`/`GridHeight`-style constants: check `VENDORED.json` crossings).
- [ ] Optional API: `napari_lite.settings.get_settings().application.new_labels_dtype = 'uint16'` works per session.

### Done when
- [ ] `ViewerModel()` constructs with the real shim; test asserts each default equals napari's (from defaults.json).

---

## 05 · Theme shim: dark and light only
milestone: M1 Imports without napari · labels: new-code · depends: {{03}}

### Why
7 importers of `napari.utils.theme` (canvas background, axes overlays, dims slider, event loop).
napari's theme module also registers plugin themes through npe2 at import time.

### Tasks
- [ ] `src/napari_lite/utils/theme.py` (own code): copy the `Theme` model and the built-in dark/light
      definitions; keep `get_theme`, `available_themes`, `is_theme_available`, `register_theme`; no npe2, no pygments.

### Done when
- [ ] Canvas background follows `viewer.theme = 'light'`.

---

## 06 · Key bindings without the action manager
milestone: M1 Imports without napari · labels: new-code · depends: {{03}}

### Why
5 importers of `napari.utils.action_manager` (`components/viewer_model.py`, `_viewer_key_bindings.py`,
`layers/image/_image_key_bindings.py`, `layers/utils/layer_utils.py`, `utils/key_bindings.py`).
The action manager exists to feed menus and the shortcuts editor, which lite does not have.

### Tasks
- [ ] `src/napari_lite/utils/action_manager.py` (own code): same names (`action_manager.register`,
      `bind_shortcut`, `trigger`), backed by a plain dict; default shortcuts from `defaults.json` `shortcuts`.

### Done when
- [ ] Viewer and layer key bindings fire in a test (e.g. toggling ndisplay, Labels brush keys).

---

## 07 · No plugins: explicit errors instead of readers
milestone: M1 Imports without napari · labels: new-code · depends: {{03}}

### Why
`components/viewer_model.py` imports `napari.plugins`, `plugins._npe2`, `plugins.utils`; `plugins.io` is
used locally by `viewer_model`, `layerlist` and `layers/base/base.py` (`open`, `save`). `layers/base/base.py`
and `types.py` import npe2 directly. #5940's agreed position: no plugin manager; users load data themselves.

### Tasks
- [ ] Shim `napari_lite/plugins/` (own code): `open`/`open_sample`/`save_layers` raise a clear
      `NotImplementedError('napari-lite has no file readers: load data with your own library and use add_image')`.
- [ ] Remove the npe2 plugin lookup in `layers/base/base.py` (layer source plugin name → `None`).
- [ ] `types.py`: `LayerName` as a local alias.

### Done when
- [ ] `npe2` added to `FORBIDDEN` in `tests/test_lite_imports.py`.

---

## 08 · No magicgui
milestone: M1 Imports without napari · labels: new-code · depends: {{03}}

### Tasks
- [ ] Shim `napari_lite/utils/_magicgui.py` (own code) with no-op `add_layer_to_viewer`,
      `add_layers_to_viewer`, `get_layers`.
- [ ] `layers/base/base.py`: the two `mgui.register_type(...)` calls at import → guarded by
      `if 'magicgui' in sys.modules` or moved to an optional `napari_lite.magicgui` module.
- [ ] `layers/_source.py`: `FunctionGui` only under `TYPE_CHECKING`.

### Done when
- [ ] `magicgui` in `FORBIDDEN`.

---

## 09 · Lean `utils` package
milestone: M1 Imports without napari · labels: vendored-fix · depends: {{03}}

### Why
napari's `utils/__init__.py` eagerly imports dask, colormaps (vispy), `info` and `notebook_display` (lxml).
Making it lazy cut `import napari.settings` from 0.91 to 0.70 s in napari itself.

### Tasks
- [ ] Own-code `utils/__init__.py` with `lazy_loader.attach`, same public names minus `sys_info`/`citation_text`.
- [ ] `nbscreenshot` comes back in issue 15 as an own-code notebook helper.

### Done when
- [ ] `lxml` in `FORBIDDEN`.

---

## 10 · Qt plumbing without the main window
milestone: M1 Imports without napari · labels: new-code · depends: {{03}}

### Why
Copied `_qt/__init__.py` imports `qt_main_window`; `_qt/qt_event_loop.py` imports app-model providers,
notification dialogs, perf tracing and the theme; `_qt/qthreading.py` imports `napari.viewer` and app-model.

### Tasks
- [ ] Own-code `_qt/__init__.py`: nothing eager.
- [ ] Own-code `_qt/qt_event_loop.py`: `get_qapp()` (app name, icon, high-DPI) and `run()` only.
- [ ] `_qt/qthreading.py`: drop the viewer/app-model hooks (thread workers still work).

### Done when
- [ ] `from napari_lite._qt.widgets.qt_dims import QtDims` works without any stand-in.

---

## 11 · napari-free import test and copied tests green
milestone: M1 Imports without napari · labels: tooling · depends: {{04}}, {{05}}, {{06}}, {{07}}, {{08}}, {{09}}, {{10}}

### Tasks
- [ ] Set `STUBS = False` in `spikes/spike_core.py`; it must pass with real napari blocked.
- [ ] Add `tests/test_lite_imports.py` (from the kit) to CI.
- [ ] Run the copied napari tests (`src/napari_lite/**/_tests`). Fix, or mark `xfail` with a reason
      ("needs plugins", "needs settings file"). Keep a count in the README.

### Done when
- [ ] CI green on 3 OSes in an environment where `pip show napari` finds nothing.

---

## 12 · `QtCanvas`: canvas + dims sliders + cursor readout
milestone: M2 First image on screen · labels: new-code · depends: {{11}}

### Why
jni's idea in #5940: a canvas object with the viewport and dims sliders that can live by itself.
`spikes/spike_canvas.py` already wires `VispyCanvas` + `QtDims` in a plain `QWidget`.

### Tasks
- [ ] `napari_lite/qt/canvas.py` (own code): `QtCanvas(viewer_model)`; maps layers to visuals on
      insert/remove/move; status label with cursor position and value; keymap handler.
- [ ] `examples/canvas_only.py`: 10 lines, numpy image in a `QtCanvas`.

### Done when
- [ ] Example shows the image on macOS, Windows and Linux; screenshot saved by CI (needs a GL runner or xvfb + mesa).

---

## 13 · `napari_lite.Viewer` and `imshow`
milestone: M2 First image on screen · labels: new-code · depends: {{12}}

### Tasks
- [ ] `napari_lite/viewer.py` (own code): `Viewer(ViewerModel)` with `title`, `ndisplay`, `show`;
      a window holding `QtCanvas`; `screenshot()`, `close()`, `show()`.
- [ ] `napari_lite/view_layers.py` (own code): `imshow(data, ...) -> (viewer, layer)` like napari's.
- [ ] One-line-swap test: the same script with `import napari` and `import napari_lite as napari`
      produces the same layer list (run where napari is installed, as a compatibility check).

### Done when
- [ ] `napari_lite.imshow(np.random.random((512, 512)))` opens a window.

---

## 14 · Default navigation and shortcuts
milestone: M2 First image on screen · labels: new-code · depends: {{13}}

### Tasks
- [ ] Pan, zoom, 3D rotate, dims stepping with arrow keys, reset view, toggle 2D/3D, grid on/off.
- [ ] Shortcuts documented in `docs/shortcuts.md`; configurable only in code.

---

## 15 · Jupyter support
milestone: M2 First image on screen · labels: new-code · depends: {{13}}

### Tasks
- [ ] Works with `%gui qt`; viewer has `_repr_png_` (or an `nbscreenshot` helper) for inline images.
- [ ] `examples/notebook.ipynb` with timings printed in-cell.

---

## 16 · Benchmarks against napari, on three OSes
milestone: M3 Fast and small · labels: tooling, perf · depends: {{11}}

### Tasks
- [ ] `bench/bench_imports.py` (from the kit) in CI: run for `napari_lite`, and for `napari` in a separate
      env for comparison; upload JSON results; table in README.
- [ ] Track time to first image (`ViewerModel().add_image`) as well as import, since lazy imports move cost.

### Done when
- [ ] README shows napari vs napari-lite for import, first image, `Viewer(show=False)` on 3 OSes.

---

## 17 · Key types without app-model
milestone: M3 Fast and small · labels: vendored-fix, perf · depends: {{16}}

### Why
app-model is still imported by 6 copied modules for key enums only (`components/_viewer_key_bindings.py`,
`layers/{shapes,labels,points}/_*_key_bindings.py`, `utils/events/evented_model.py`, `utils/key_bindings.py`),
~300 ms cumulative in napari.

### Tasks
- [ ] Own-code `napari_lite/utils/_keys.py` with `KeyCode`, `KeyMod`, `KeyBinding` (subset used).
- [ ] Add `literal_rewrites` in `vendor.toml` mapping `from app_model.types import` to the local module,
      so the change survives every resync without hand edits.

### Done when
- [ ] `app_model` in `FORBIDDEN`; removed from `pyproject.toml`.

---

## 18 · Heavy dependencies on first use
milestone: M3 Fast and small · labels: vendored-fix, perf · depends: {{16}}

### Tasks
- [ ] dask: import only when data is a dask array (`utils/_dask_utils.py`, `layers/utils/layer_utils.py`);
      move to the `[dask]` extra.
- [ ] pint: import on first non-default unit (9 copied modules); measure and decide.
- [ ] scikit-image: local imports in `layers/shapes/_shapes_utils.py`.
- [ ] pandas: confirm only needed for `layer.features` DataFrames; `[features]` extra.
- [ ] Prefer `literal_rewrites` or shims over hand edits, so resyncs stay clean.

### Done when
- [ ] `import napari_lite.components` ≤ 0.4 s on Linux (target; record actual).

---

## 19 · Dependency diet and install size
milestone: M3 Fast and small · labels: tooling, perf · depends: {{17}}, {{18}}

### Tasks
- [ ] Remove every `TEMP` line from `pyproject.toml`; extras `[dask]`, `[features]`, `[fast-shapes]`, `[all]`.
- [ ] CI job: fresh venv, `pip install .[pyqt6]`, record installed size and package count; same for
      `pip install napari[pyqt6]`.

### Done when
- [ ] README shows install size and package count, napari vs napari-lite.

---

## 20 · All layer types render correctly
milestone: M4 Full feature set · labels: new-code · depends: {{13}}

### Tasks
- [ ] Visual test per layer type (Image incl. RGB and multiscale, Labels, Points, Shapes, Vectors, Surface,
      Tracks) in 2D and 3D: render with napari-lite and with napari, compare screenshots within a tolerance.
- [ ] Run on a GL-capable CI runner (or locally) and keep reference images in `tests/visual/`.

---

## 21 · Opt-in layer list and layer controls
milestone: M4 Full feature set · labels: new-code · depends: {{20}}

### Why
#5940 open question; brisvag's view: lite core knows nothing of these GUIs, but users can add them.

### Tasks
- [ ] Add `napari._qt.containers` and `napari._qt.layer_controls` to `extra_modules` in `vendor.toml`;
      re-vendor; list new crossings.
- [ ] `viewer.add_layer_list()`, `viewer.add_layer_controls()`: created lazily, docked beside the canvas.
- [ ] Thumbnails off by default (JoOkuma, #5940; napari #6657).

### Done when
- [ ] Importing `napari_lite` still loads no container or control modules until those calls.

---

## 22 · Painting and editing tools
milestone: M4 Full feature set · labels: new-code · depends: {{21}}

### Tasks
- [ ] Labels paint/fill/erase, Shapes and Points add/select/move through the opt-in controls and key bindings.
- [ ] Undo/redo works (copied `utils/history.py` behaviour, without settings file).

---

## 23 · Less magic: explicit data interpretation
milestone: M4 Full feature set · labels: needs-decision · depends: {{13}}

### Why
#5940 summary: lite should avoid guessing RGB, channel axis and readers.

### Tasks
- [ ] Decide: keep napari's guessing for one-line-swap compatibility, or require `rgb=`/`channel_axis=`
      with a clear error. Write the decision in `docs/design.md`.
- [ ] Implement and test the chosen behaviour.

---

## 24 · Monthly resync to napari main
milestone: M5 Sync and share · labels: tooling · depends: {{02}}

### Tasks
- [ ] First real resync to the newest napari release following `SYNC.md`; time how long it takes.
- [ ] Record merge conflicts per shim/edited file; if one file conflicts every time, replace the edit
      with a shim or a `literal_rewrites` rule.

---

## 25 · Docs, demo and sharing
milestone: M5 Sync and share · labels: needs-decision · depends: {{15}}, {{19}}

### Tasks
- [ ] README: install, 5-line example, comparison table (import, first image, install size), credits to napari.
- [ ] Before any PyPI release: ask napari maintainers (Zulip) about the name "napari-lite". Use TestPyPI until then.
- [ ] Share results on the napari Zulip and on the upstream napari issue 5940; findings can feed napari's own lite work.
