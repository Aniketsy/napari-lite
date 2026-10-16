# napari-lite

**Status: experimental. Nothing here is released or supported yet.**

napari-lite is the viewer core of [napari](https://napari.org) without the
application around it: the layer models, the vispy canvas and the dims
sliders, importable as `napari_lite` without napari installed. There is no
plugin manager, no settings file, no menus, no layer list or layer controls
(those come back as opt-ins later). You load data with your own library and
call `add_image`.

The idea comes from napari issue
[#5940](https://github.com/napari/napari/issues/5940) ("napari-lite"). The
aim is a package that imports fast, installs small, and swaps in for napari
with one line (`import napari_lite as napari`) in scripts that only view
arrays.

## Derived from napari (BSD-3)

Most of the code in `src/napari_lite` is copied from napari and is
copyright the napari contributors, redistributed under the BSD 3-Clause
license (see [LICENSE](LICENSE)). It is not hand-copied: `tools/vendor.py`
copies the napari core from a pinned commit on the `vendor` branch, rewrites
`napari` to `napari_lite`, and writes `VENDORED.json` with every module it
took and every import that crosses into napari's application code
(settings, theme, plugins, action manager, ...). Those crossings are the
work: napari-lite provides a small module of its own at each such import
path.

- `vendor` branch: napari copy only, written by the tool, never edited by hand.
- `main`: `vendor` plus napari-lite's own code. Upstream updates arrive with
  `git merge vendor`.
- Own files start with `# napari-lite: own code`; the tool never overwrites them.

How to resync is written in [SYNC.md](SYNC.md). The current copy is listed
in [VENDORED.json](VENDORED.json): which napari commit, which modules, and
which imports cross into app modules that napari-lite must provide.

## Status (2026-10-17)

Milestones M0 (repo and copy) and M1 (imports without napari) of the
[backlog](docs/backlog.md) are done:

- `import napari_lite` takes about 0.05 s and loads no numpy, Qt, vispy or
  pydantic; `napari_lite.components` imports with napari blocked and all seven
  layer types (Image, Labels, Points, Shapes, Vectors, Surface, Tracks) work
  in a `ViewerModel`.
- napari's settings, theme, action manager, plugins, magicgui hooks and
  app-model are replaced by small own modules at the same import paths
  (`src/napari_lite/settings/`, `utils/theme.py`, `utils/action_manager.py`,
  `plugins/`, `utils/_magicgui.py`, `_app_model/`).
- The copied napari tests run from `src/napari_lite/**/_tests` with the
  fixtures in `src/napari_lite/conftest.py`. Of napari's test files for the
  copied modules, 169 are copied (37 are not, because they import
  application modules; the list is in `VENDORED.json`) and 6 of those are
  not collected (they import the `Viewer`, app-model actions or
  `utils.info`; see `collect_ignore` in the conftest). Last full run,
  own tests included: 3977 passed, 179 skipped, 0 failed; 47 skips wait for
  the `Viewer` (issue 13), 5 for plugins, the rest are napari's own
  optional-dependency and platform skips.

There is no `Viewer`, no window and no canvas widget yet: that is
milestone M2 (`QtCanvas`, `napari_lite.Viewer`, `imshow`).

## Layout

```
src/napari_lite/   the package (copied napari core + own shims)
tools/             vendor.py, vendor.toml, create_issues.py
tests/             napari-lite's own tests (copied napari tests live next to the code)
bench/             import-time and time-to-first-image benchmarks
spikes/            throwaway experiments that informed the design
docs/              backlog.md (the issue list), design notes
examples/
```

## Roadmap

The milestones and issues are in [docs/backlog.md](docs/backlog.md):
M0 repo and copy, M1 imports without napari, M2 first image on screen,
M3 fast and small, M4 full feature set, M5 sync and share.

## Development

```
pip install -e .[dev,pyqt6]
pytest tests src/napari_lite        # own tests, then the copied napari tests
python spikes/spike_core.py         # smoke check with napari blocked
```

On Linux without a display, run the tests under `xvfb-run` or with
`QT_QPA_PLATFORM=offscreen`. On Windows and macOS run them as they are: the
Qt offscreen platform has no OpenGL there and the vispy tests need a GL
context (napari's own tests behave the same).

The napari checkout used for vendoring is separate from this repo:

```
git clone https://github.com/napari/napari ../napari
git -C ../napari checkout <pin from tools/vendor.toml>
python tools/vendor.py --napari ../napari --report
```
