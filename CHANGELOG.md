# Changelog

## 0.1.0 (unreleased)

First release. The napari viewer core (layers, canvas, dims sliders),
copied from napari commit `ebfc4a0a` (0.9.0.dev) by `tools/vendor.py`,
importable as `napari_lite` without napari installed.

### Added

- `napari_lite.Viewer`, `imshow`, `run`, `current_viewer`; a window with a
  status bar and `add_dock_widget`; `QtCanvas` for use in other Qt layouts.
- A hint in the empty canvas with the ways to load data (the command
  line, `add_image`) and the key-bindings shortcut; `QtCanvas(hint=...)`.
- napari's layer list, layer controls and the layer and viewer button
  rows in the window, as napari's own widgets: thumbnails, visibility,
  the layer list's context menu (layer operations, copy and paste of
  scale and transforms), the mode buttons of every layer type. `QtCanvas`
  builds them on first access (`layers`, `controls`, `layerButtons`,
  `viewerButtons`, `dockLayerList`, `dockLayerControls`). The window uses
  napari's stylesheet; the themed icons are written under the temp
  directory on first use.
- All seven layer types in 2D and 3D with napari's rendering, overlays,
  grid mode, screenshots and `export_figure`.
- napari's default key bindings for the viewer and every layer
  (`docs/shortcuts.md`), configurable in code.
- Own modules at napari's import paths for settings (in memory, napari's
  defaults), themes (dark and light), the action manager, key types
  (copied from app-model), `nbscreenshot` without lxml, thread workers.
- `tools/vendor.py` and the `vendor` branch: a reproducible copy of napari
  with every crossing into napari's application code listed in
  `VENDORED.json`; `SYNC.md` for resyncs; a weekly upstream report.
- Benchmarks (`bench/`) and a benchmark workflow on three OSes.
- Tests: napari-lite's own tests and napari's copied tests, run on Linux,
  macOS and Windows with Python 3.11 to 3.13 and without napari.

### Different from napari

- No plugins: `viewer.open()`, `open_sample()`, `layer.save()` raise
  `NotImplementedError`; load data with your own library.
- No console, menus, command palette, preferences dialog, settings file
  or welcome screen; the layer list's context menu has napari's layer
  entries and no plugin entries.
- dask is imported on first use; pandas stays a dependency (the layer
  features tables), pint is imported with the layers.
- scikit-image is not a dependency: `utils/_draw.py` (a line, a polygon,
  points in a polygon, a flood fill) and `utils/_colorconv.py` (Luv and
  Lab to RGB) stand in for the six functions napari used, pixel for pixel
  and colour for colour; networkx and tifffile leave with it, 43 MB in
  all.
- scipy is the `scipy` extra, needed only for spline-interpolated shapes
  (`interpolation_order > 1`, with an error naming the extra otherwise).
  The camera's rotations (`utils/_rotation.py`, scipy's own algorithms,
  gimbal lock included), the affine decomposition's QR and RQ and the
  geometric mean in points masks (`utils/_linalg.py`), the dilation and
  erosion behind label contours (`utils/_morphology.py`) and the Tracks
  layer's nearest-vertex and id lookups (`utils/_tracks_index.py`) are
  numpy, compared with scipy in the tests; 134 MB less. The first 3D view
  no longer stalls on importing `scipy.spatial`.
- toolz and pydantic-extra-types are not dependencies either: the two
  toolz functions the transforms use are in `utils/_toolz.py`, and the
  `Color` class of pydantic-extra-types is copied unchanged into
  `utils/_color.py` under its MIT licence, so themes accept exactly the
  same colours as before. `pip install napari-lite[pyqt6]` is 434 MB in
  34 packages with 15 direct dependencies, against napari's 761 MB in 106
  with 37. The three findings that apply to napari itself are patches in
  `docs/upstream.md`.
- The first image and the first paint import only what they use: the
  check for xarray data runs only when xarray is already imported (napari
  imports it, and pandas with it, whenever it is installed); thumbnails
  are downsampled in numpy, not with scipy.ndimage; scipy.spatial is
  imported for 3D only; the layers do not import vispy's scene graph;
  progress bars, and tqdm with them, are imported when one is made. In a
  fresh environment the first image went from 2.2 s and 1,026 modules to
  1.5 s and 729 (`docs/benchmarks.md`).
- wrapt is not a dependency: `utils/_object_proxy.py` provides the one
  class napari used from it.
