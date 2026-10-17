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

## Features

### Working now

- **One-line swap**: `import napari_lite as napari`, then `napari.Viewer()`,
  `napari.imshow(array)`, `viewer.add_image`, `add_labels`, `add_points`,
  `add_shapes`, `add_vectors`, `add_surface`, `add_tracks`, `viewer.layers`,
  `viewer.dims`, `viewer.camera`, `viewer.screenshot()`, `viewer.close()`,
  `napari_lite.run()`. A test runs the same script with napari and
  napari-lite and compares the result.
- **All seven layer types** in 2D and 3D, with napari's rendering (vispy
  canvas, colormaps, contrast limits, blending, multiscale, grid mode, scale
  bar and axes overlays, layer name overlay).
- **Navigation and editing with the mouse and keyboard**: pan, zoom,
  rotate, dims sliders, playback, napari's default key bindings for the
  viewer and every layer (paint, fill, pick, add points, draw shapes, ...),
  listed in [docs/shortcuts.md](docs/shortcuts.md).
- **`QtCanvas`**: the canvas with dims sliders and a status line as a
  single Qt widget you can put in your own window or application
  (`examples/canvas_only.py`).
- **A small window**: `Viewer` opens a window with the canvas, dims
  sliders and a status bar (cursor coordinates, layer value, help text);
  `viewer.window.add_dock_widget(widget)` docks your own Qt or magicgui
  widgets next to the canvas.
- **Jupyter**: works with `%gui qt`; `nbscreenshot(viewer)` shows the
  viewer inline (`examples/notebook.ipynb`).
- **Settings in code**: `get_settings()` has napari's settings names and
  defaults, changed per session, nothing written to disk.
- **Dark and light themes**, following `viewer.theme`.
- **Thread workers** (`napari_lite.qt.thread_worker`, `create_worker`).
- **Fast import**: `import napari_lite` takes about 0.05 s and loads no
  numpy, Qt, vispy or pydantic; no napari, npe2, magicgui, app-model or
  lxml is ever imported.

### Planned (issue numbers in [docs/backlog.md](docs/backlog.md))

- Benchmarks against napari on Linux, macOS and Windows: import time, time
  to first image, `Viewer(show=False)`, install size (16, 19).
- Heavy dependencies only on first use: dask, scikit-image, pandas, pint
  where possible; `[dask]`, `[features]`, `[fast-shapes]` extras (18, 19).
- Visual regression tests: every layer type in 2D and 3D compared with
  napari screenshots (20).
- **Opt-in layer list and layer controls**: `viewer.add_layer_list()`,
  `viewer.add_layer_controls()`, loaded only when called (21), and the
  editing tools through them, with undo/redo (22).
- A decision on data interpretation: keep napari's guessing of RGB and
  channel axis, or require `rgb=` / `channel_axis=` (23).
- Monthly resync with napari's main branch (24); docs, demo, sharing with
  the napari community (25).

### Not planned

Plugins (readers, writers, sample data, widgets), the IPython console,
menus and the command palette, the preferences dialog and settings file,
the welcome screen and the activity dialog. Load data with your own library
(tifffile, imageio, zarr, ...) and pass arrays to `add_image`.

The copied napari tests run as part of the test suite (3977 passed, 179
skipped on the last full run; details in `src/napari_lite/conftest.py`).

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
