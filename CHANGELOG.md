# Changelog

## 0.1.0 (unreleased)

First release. The napari viewer core (layers, canvas, dims sliders),
copied from napari commit `ebfc4a0a` (0.9.0.dev) by `tools/vendor.py`,
importable as `napari_lite` without napari installed.

### Added

- `Viewer(gui='jupyter')`: the viewer as widgets in a notebook cell
  (issue #5; the `jupyter` extra). The canvas is a jupyter_rfb widget
  that streams frames the kernel draws off the screen, so it works on a
  remote server too; drag, wheel and napari's keys work on it. Around
  it: a slider and a play button per extra dimension, a layer list
  (visibility, selection), 2D/3D and reset-view buttons, the status
  line, and `add_dock_widget` for ipywidgets. The messages of these
  widgets, docked ones included, are handled on the kernel's main shell:
  JupyterLab would deliver them on a subshell's thread, where the canvas
  cannot be used. Ctrl+O docks an upload box and Ctrl+Alt+/ the key
  bindings as a table; the Qt dialogs behind those keys are the Qt
  window's. `examples/jupyter.ipynb` shows it.
  `nbscreenshot` no longer creates a Qt application (which turned on
  IPython's Qt event loop) for viewers that have none.
- `Viewer(gui=None)`: a viewer without a window (issue #5). The
  renderer draws off screen; `screenshot` and `export_figure` work,
  `window` and `show` say there is none. On Linux with EGL vispy's
  `egl` application draws with no Qt in the process (text then needs
  freetype-py: the `headless` extra). napari's GL calls go through
  PyOpenGL, so napari-lite sets `PYOPENGL_PLATFORM=egl` for that, unless
  the variable is set or PyOpenGL is imported already (name the renderer
  rather than passing its class: importing the class imports PyOpenGL
  first). Elsewhere the Qt
  binding draws into a widget kept off the screen. `NAPARI_LITE_GUI=none`
  makes it the default, and `napari_lite.run()` returns at once when no
  viewer has a window.
- `napari_lite.backends`: the two contracts between the model, the
  renderer and the front end (issue #5). `CanvasBackend` is what a
  front end uses from a renderer (`native`, `screenshot`, `key_event`,
  `close`; the renderer follows the model by itself); `Window` is what
  a `Viewer` uses from its window. `get_renderer` and `get_gui` find
  them by name: the built-in `'vispy'` and `'qt'`, or names other
  packages register under the entry-point groups
  `napari_lite.renderers` and `napari_lite.guis`.
  `Viewer(renderer=..., gui=...)` and `QtCanvas(renderer=...)` take a
  name or the class itself; `NAPARI_LITE_RENDERER` and
  `NAPARI_LITE_GUI` set the defaults. The vispy renderer is
  `VispyBackend` (`_vispy/backend.py`), the wiring to the model that
  `QtCanvas` held; `QtCanvas` and the headless viewer only use the
  contract, so a test runs both on a renderer that is not vispy. The
  copied vispy canvas imports without Qt: the throttle, the fonts, the
  text metrics and the cursor are Qt's only when vispy runs on Qt
  (`_vispy/_qt_optional.py`).
- The model (viewer model, layers, dims, camera, events) imports and
  runs without vispy and without Qt (issue #5): the colour names and
  parsing, the key names, a rotation matrix and an exception helper that
  the copied code took from vispy are own modules now; vispy's
  colormaps by name and its triangulation are imported when first used.
  A test runs the model with every layer type and vispy blocked, and CI
  runs it with vispy uninstalled.
- `napari_lite.view`, a view-only canvas for images and points without
  napari's layers (issue #4): `View` with `ImageItem` and `PointsItem`
  (contrast limits, colormap, opacity, visibility, the slice shown, a
  camera), drawn by `VispyRenderer`, in a `QtView` widget with a slider
  per non-displayed axis; `show(image, points)` opens a window. The model
  imports numpy and psygnal only; Qt and vispy come with the widget.
  Integer images are uploaded as they are with the contrast limits
  applied on the GPU; lazy arrays (dask, zarr) are sliced in a worker
  thread so the window stays responsive; arrow keys and Home/End step
  the axes. A readout under the sliders gives the position under the
  pointer and the value there. `napari-lite --view` opens files in it,
  `--points` adds points (`.npy`, `.csv`), in the viewer too. A second
  renderer, `PygfxRenderer` (the `pygfx` extra, `QtView(view,
  renderer='pygfx')`), draws the same model with pygfx and matches the
  vispy one pixel for pixel at every data pixel centre.
- `napari_lite.Viewer`, `imshow`, `run`, `current_viewer`; a window with a
  status bar and `add_dock_widget`; `QtCanvas` for use in other Qt layouts.
- The `napari-lite` command (`python -m napari_lite` too): one layer per
  file, images through imageio, `.npy`/`.npz` through numpy, TIFF with the
  `tiff` extra; `--labels`, `--ndisplay`, `--title`. A file that is missing
  or that no reader can open is reported with exit status 2 before any
  window opens; closing the window ends the command with status 0.
- A built-in reader and built-in samples where napari has plugins:
  `viewer.open(path)`, files dropped on the canvas and `Ctrl+O` read png,
  jpg, bmp, gif, webp, tif, npy and npz (imageio, numpy, tifffile when
  installed), one image layer per file, `stack=True`, `layer_type`;
  `viewer.open_sample('napari-lite', name)` and `napari-lite --sample`
  give imageio's standard images (downloaded once), the `stent` CT volume
  and a computed `blobs` volume, and the empty canvas links to both.
  napari's names (`plugin='napari'`, `open_sample('napari', 'astronaut')`)
  are accepted for the one-line swap.
- The empty canvas shows what napari's welcome screen shows, in
  napari-lite's terms: drop files or Ctrl+O, the key-bindings
  shortcut, the samples as links, the command line and Python one-liners,
  in aligned rows; `QtCanvas(hint=...)` for a plain message,
  `QtCanvas.set_hint` for rows.
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
- Benchmarks (`bench/`) and a benchmark workflow on three OSes: import
  time, first image, first frame, the first layer of each kind, slice
  stepping and a brush stroke (vsync off, the same 640 x 480 canvas, the
  mouse over it), with the median and the first run next to the best;
  `bench/first_frame.py` shows where the first frame's time
  goes; `tools/readme_bench.py` writes the README's table from the
  workflow's Linux numbers.
- Tests: napari-lite's own tests and napari's copied tests, run on Linux,
  macOS and Windows with Python 3.11 to 3.13 and without napari.

### Different from napari

- The status bar text (the value under the cursor, its coordinates, the
  layer's help) is computed on the main thread at most 20 times a second,
  the last cursor position always shown; napari computes it in a thread.
  A slice step or a mouse move no longer pays for it every time.
- No plugins: `viewer.open()` and `open_sample()` serve only the built-in
  formats and samples (see Added) and raise `NotImplementedError` for the
  rest, `layer.save()` always; load or save other data with your own
  library.
- No console, menus, command palette, preferences dialog, settings file
  or welcome screen; the layer list's context menu has napari's layer
  entries and no plugin entries.
- Console notifications print on a console with a legacy encoding (cp1252
  when Windows pipes the output): the characters it lacks become `?`,
  where napari's `print` raised and a misleading error was logged in place
  of the message (`docs/upstream.md`, patch 4).
- dask is imported on first use; pint, and its unit registry, only when a
  layer gets a real unit. Until then `layer.units` and `dims.units` hold a
  pixel stand-in (`utils/_pixel.py`): equal to pint's `pixel` unit in both
  directions, printed the same, converting on demand, but not a
  `pint.Unit` instance. That keeps pint's import (0.6 s, 340 modules) and
  its registry (0.2 s) off the first image, which they made up half of.
  When pint does load, its registry comes from pint's definition cache.
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
  same colours as before.
- pandas is the `features` extra. A layer without features is served by a
  zero-column stand-in (`layers/utils/_lite_features.py`) in a process
  that has not imported pandas; `layer.features` and `feature_defaults`
  still hand out a real DataFrame whenever pandas can be imported, and
  once pandas is in the process, by the user or by a feature, every table
  is a DataFrame as in napari. Without pandas installed the first feature
  raises an ImportError naming the extra; Tracks needs it. Points, Shapes
  and Labels without features no longer import pandas's 530 modules.
  `pip install napari-lite[pyqt6]` is 370 MB in 31 packages with 14 direct
  dependencies, against napari's 761 MB in 106 with 37. The three findings
  that apply to napari itself are patches in `docs/upstream.md`.
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
