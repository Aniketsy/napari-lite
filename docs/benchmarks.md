# Benchmarks

Measured with `bench/bench_imports.py` (best of several fresh
interpreters) and `bench/install_size.py`; `bench/make_table.py` makes the
tables. `.github/workflows/bench.yml` runs them on Linux, macOS and Windows
in fresh environments, `pip install napari-lite[pyqt6]` against
`pip install napari[pyqt6]`, weekly and on request. Those are the numbers
to trust; a developer machine gives different ones depending on what else
is running.

What `bench_imports.py` measures, each in a fresh interpreter, `--repeat`
times (the best run is the number in the tables; the JSON keeps the median
and the first run too, and `make_table.py --median` prints both; only a
run right after a reboot is a cold one):

- `import`, `import_components`, `import_layers`: the import alone.
- `first_image`: `ViewerModel().add_image(...)`, the imports it triggers
  included.
- `viewer_no_show`, `viewer_shown`: a `Viewer` made and closed, without
  and with its window shown and painted once.
- `first_frame`: from the start of the process to the first paint event
  of a window that holds one 512 x 512 image, what the user of a script
  waits for.
- `first_labels_layer`, `first_points_layer`, `first_shapes_layer`: a
  viewer already shows an image; the time from `add_labels` (`add_points`
  with 1,000 points, `add_shapes` with 50 rectangles) to the canvas draw
  that shows the new layer, so the first layer of that kind with its
  imports, widgets and shaders.
- `slice_step`: the median over 60 slice steps through a 32 x 512 x 512
  float32 image of the wall time from the step to the canvas drawn and
  the window idle again; `paint_stroke`: the same per point of a 60-point
  brush stroke on a 512 x 512 Labels layer. Wall time with vsync off (the
  swap interval of Qt's default surface format), because the clock of
  `time.process_time` ticks every 15.6 ms on Windows and a swap with
  vsync makes wall time a multiple of the frame interval; the CPU mean
  is kept as `cpu_seconds`.
- The window measurements after `first_frame` share one setup, so that
  packages and machines compare: the window is resized until the canvas
  is 640 x 480 (the two packages open windows of different sizes, and
  the Labels shader is paid per pixel), and `viewer.mouse_over_canvas`
  is set, as it is while someone works: it decides whether the brush
  circle is drawn and the status bar updated, and left to the real
  pointer it changed the brush stroke by 30% depending on which window
  the pointer rested over.

The README's table is written by `tools/readme_bench.py` from the Linux
numbers of the latest Benchmarks run (`gh` downloads the artifacts; the
workflow's summary shows the same block); rows the run lacks are left
out. `bench/first_frame.py` prints where the time to the first frame
goes, stage by stage.

## GitHub Actions

[Run 39011278624](https://github.com/Aniketsy/napari-lite/actions/runs/39011278624):
Python 3.13, PyQt6, napari-lite at commit `e16cde5` (napari core
`ebfc4a0a`) against napari 0.9.2 from PyPI. Best of 5 fresh interpreters.

### Linux (ubuntu-latest)

| | napari_lite | napari |
|---|---|---|
| import package | 0.01 s | 0.07 s |
| import components | 0.54 s | 0.67 s |
| first image (ViewerModel + add_image) | 0.95 s | 1.05 s |
| Viewer(show=False) | 1.18 s | 1.39 s |
| installed size (MB) | 698 | 825 |
| packages installed | 39 | 105 |

### macOS (macos-latest, arm64)

| | napari_lite | napari |
|---|---|---|
| import package | 0.03 s | 0.06 s |
| import components | 0.30 s | 0.78 s |
| first image (ViewerModel + add_image) | 0.59 s | 1.99 s |
| Viewer(show=False) | 1.49 s | 2.80 s |
| installed size (MB) | 572 | 703 |
| packages installed | 40 | 106 |

### Windows (windows-latest)

| | napari_lite | napari |
|---|---|---|
| import package | 0.01 s | 0.06 s |
| import components | 0.55 s | 0.66 s |
| first image (ViewerModel + add_image) | 0.86 s | 0.93 s |
| Viewer(show=False) | 1.26 s | 1.25 s |
| installed size (MB) | 608 | 760 |
| packages installed | 41 | 106 |

What the numbers say:

- `import napari_lite` costs nothing measurable: every public name is
  loaded on first use.
- The core (`napari_lite.components`) imports in 0.3 to 0.55 s against
  0.66 to 0.78 s for napari's, and the first image takes 0.6 to 0.95 s
  against 0.9 to 2.0 s.
- A `Viewer(show=False)` costs about the same as in napari on Linux and
  Windows: the time goes into starting Qt and vispy, not into the window
  around the canvas.
- napari-lite installs 65 fewer packages and 130 to 150 MB less.

## Where the import time goes

`python -X importtime -c "import napari_lite.components"`, self time per
top-level package, in the local check environment (Windows, Python 3.13.7,
`[dev,pyqt6]` extras, cold). Total 2.8 s on this machine,
0.55 s on the CI runner above; the shares are what matters.

| package | seconds |
|---|---|
| numpy | 0.45 |
| napari_lite's own modules | 0.33 |
| vispy | 0.26 |
| pint (with flexcache, flexparser) | 0.35 |
| dask and yaml, imported by pint | 0.30 |
| pydantic (with pydantic_core, pydantic_extra_types) | 0.23 |
| everything else | about 0.9 |

pint imports dask (and yaml through it) whenever dask is installed, so
the `dask` extra costs about 0.3 s at import even when no dask array is
ever shown; without the extra those lines disappear.

Decisions on the heavy dependencies:

- dask is imported on first use, when a dask array is given to a layer;
  scikit-image is no longer a dependency at all (own code draws the
  Shapes masks and makes the Labels colours).
- pandas stays a dependency, imported when the first Points, Shapes,
  Labels, Vectors or Tracks layer is created: those layers keep their
  features in a DataFrame.
- pint stays an import-time dependency: the layer and dims models declare
  `pint.Unit` fields that pydantic evaluates when the classes are created,
  and every layer's transform builds the unit registry, so deferring
  `import pint` would gain nothing for the first image.

## napari-lite against napari at the same commit

The table above compares with napari 0.9.2 from PyPI. This one compares
like with like: napari installed from the very commit the copy was taken
from (`ebfc4a0a`, version `0.10.0a1.dev22`), both packages in fresh
environments made with `pip install <package>[pyqt6]` and nothing else,
on the same Windows machine (Python 3.13.7, best of 3 fresh
interpreters). The machine is about four times slower than the CI
runners and had other work running, so read the ratios, not the seconds.
Memory is the resident set at the end of the measured code; "modules" is
`len(sys.modules)`. Measured again after the layer panel went
in (napari's layer list, layer controls and button rows in napari-lite's
window) and once more after the first-image work of the next section;
those are the numbers below. Before the panel, the window took 4.1 s and
236 MB and the package had 286 modules; with the panel and before the
first-image work, the first image took 2.15 s and 1,026 modules, the
window 5.0 s and 248 MB.

| | napari-lite | napari | napari-lite |
|---|---|---|---|
| import the package | 0.01 s | 0.22 s | 16x faster |
| import the components (viewer model) | 1.08 s | 2.64 s | 2.4x faster |
| first image: `ViewerModel` + `add_image` | 1.13 s | 3.29 s | 2.9x faster |
| `Viewer(show=False)`, closed | 2.83 s | 4.61 s | 1.6x faster |
| `Viewer` shown, one image painted, closed | 3.51 s | 5.98 s | 1.7x faster |
| first frame: a window with one image, to its first paint | 3.69 s | 6.19 s | 1.7x faster |
| first Image layer in a shown empty viewer, drawn | 0.16 s | 0.45 s | 2.8x faster |
| first Labels layer on top of an image, drawn | 0.28 s | 0.86 s | 3.1x faster |
| first Points layer (1,000 points) on top of an image, drawn | 0.10 s | 0.60 s | 6x faster |
| first Shapes layer (50 rectangles) on top of an image, drawn | 0.61 s | 1.19 s | 2.0x faster |
| slice step through a 32 x 512 x 512 image, per step | 14.6 ms | 15.2 ms | same |
| Labels brush stroke, per point | 10.3 ms | 11.1 ms | same |
| memory after importing the package | 14 MB | 26 MB | 1.8x less |
| memory after the first image | 61 MB | 112 MB | 46% less |
| memory with a viewer window shown | 217 MB | 276 MB | 21% less |
| modules loaded by importing the package | 77 | 207 | 2.7x fewer |
| modules loaded at the first image | 631 | 1,357 | 2.2x fewer |
| installed size (all packages) | 370 MB | 761 MB | 391 MB less |
| packages installed | 31 | 106 | 75 fewer |
| direct dependencies | 14 | 37 | 23 fewer |
| Python modules in the package | 451 | 524 | 73 fewer |
| lines of Python in the package | 94,267 | 111,648 | 17,400 fewer |

The first-frame, first-layer and per-step rows were added later, in the
same two environments (napari-lite reinstalled from the working
tree), best of 3; the per-step rows with the shared setup described
above, which makes their three runs agree within 0.2 ms. Their first
runs are worth a look: the first frame took 26 s in napari-lite and 84 s
in napari right after the installs, the byte-compilation of a fresh
package on a cold disk, and the first Labels layer 2.5 s against 0.28 s
once warm.

An earlier version of the per-step rows had napari-lite 40% slower on
the brush stroke. Three things were wrong with the measurement, none
with the code: the two windows opened at different sizes (a 597 px wide
canvas against 319 px; the Labels fragment shader is paid per pixel, and
the GL draw took 3.8 against 2.2 ms), the CPU clock ticks every 15.6 ms
on Windows, and the mouse pointer happened to rest over napari-lite's
window, which draws the brush circle (two antialiased ellipses, 1.5 ms a
frame) and updates the status bar on every step. What a brush point
costs with everything equal, in both packages: 1 ms of painting, 2 to
4 ms of GL draw, 1.8 ms to repaint the layer list row twice (the layer
icon is rendered from SVG each time), the rest in Qt's event handling.
The status bar was the one real difference: napari computes it in a
thread, napari-lite computed it on every cursor move on the main thread,
2 ms of label relayout per slice step with the mouse over the canvas; it
now runs at most every 50 ms (`QtCanvas`), which is where the slice
step row comes from.
The times were measured again after pint left the first
image (below); the removals of toolz, pydantic-extra-types and pandas in
between changed module counts and sizes only, and a rerun of the window
on this machine moves by half a second either way. The README repeats the first rows of this table;
`tools/readme_images.py` takes the README's screenshot.

Where the difference comes from:

- **Dependencies.** napari-lite keeps imageio, lazy-loader, numpy,
  packaging, Pillow, pint, psygnal, pydantic, PyOpenGL, qtpy, superqt,
  tqdm, typing-extensions and vispy. It drops app-model, certifi,
  jsonschema, magicgui, napari-console, napari-plugin-engine,
  napari-resources, napari-svg, npe2, platformdirs, pydantic-settings,
  pygments, pywin32, PyYAML, wrapt (one base class, now
  `utils/_object_proxy.py`), scikit-image with networkx and tifffile (four
  drawing functions and two colour conversions, now `utils/_draw.py` and
  `utils/_colorconv.py`), scipy (rotations, QR and RQ, a geometric mean,
  two morphology filters and the Tracks lookups, now `utils/_rotation.py`,
  `_linalg.py`, `_morphology.py` and `_tracks_index.py`; spline-interpolated
  shapes keep it as the `scipy` extra), toolz (two functions, now
  `utils/_toolz.py`), pydantic-extra-types (its `Color` class copied into
  `utils/_color.py` under its MIT licence) and pandas (the `features`
  extra: a layer without features is served by a zero-column stand-in,
  `layers/utils/_lite_features.py`, until pandas is in the process, and
  `layer.features` hands out a real DataFrame whenever pandas can be
  imported), and moves dask, cachey and psutil to the `dask` extra and
  tifffile to the `tiff` extra. Most of the 75 fewer installed packages
  are what those pulled in. Of the 370 MB, 330 MB are Qt, numpy, vispy and
  PyOpenGL, the floor of any Qt viewer in Python. imageio stays: the
  command line reads what it reads.
- **Code.** Of napari's 556 modules at that commit, 398 are copied (the
  viewer model, layers, vispy rendering, the layer list, layer controls
  and button rows, dims widgets, events, colormaps, transforms, icons and
  stylesheet) and 158 are not: the main window, menus and command
  palette, the preferences dialog and settings file, the npe2 plugin
  manager with every reader, writer and sample, the IPython console, the
  welcome screen, notifications and activity dialogs, app-model actions
  and dependency injection, perf tracing, the command line. 44 own files
  (4,900 lines) replace what the copied core needs from that side.
- **Import.** `import napari_lite` resolves names on first use, so it
  costs nothing until a viewer or layer is made; `import napari` runs the
  installation check, the plugin discovery setup and the settings model.
- **Startup.** Opening a window is faster by the menus, console, welcome
  screen, notification widgets and plugin discovery that napari builds;
  the layer list and layer controls are the same widgets in both (adding
  them to napari-lite's window cost 0.9 s and 12 MB by the window
  benchmark at the time; the stage breakdown below puts the
  panel at 0.2 s), and what remains
  (Qt, vispy, the first OpenGL context) is the same too, which is why the
  gap narrows from 17x at import to 1.2x with a window shown.

To repeat it: `pip install ".[pyqt6]"` and
`pip install "<napari checkout>[pyqt6]"` into two fresh venvs, then in
each `python bench/bench_imports.py --package <name> --repeat 3 --json ..`
and `python bench/install_size.py --package <name> --json ..`, and
`python bench/make_table.py *.json`.

## What the first image stopped importing

Profiling (`python -X importtime`, cProfile, and fresh
interpreters with candidate fixes applied by monkeypatch) showed that the
copied code itself was not where the first image spent its time: a
handful of imports fired on the first layer and the first paint. Each is
now a `[[rewrite]]` rule in `tools/vendor.toml` (reapplied at every
resync) with an own module where one was needed, and
`tests/test_startup_imports.py` fails if one comes back.

| what | cost it had | now |
|---|---|---|
| `_check_xarray`, run by every new layer, imported xarray (and pandas with it) whenever xarray is installed | 454 modules, about 1 s on this machine | runs only when xarray is already in `sys.modules`, where any xarray object must come from |
| the thumbnail used `scipy.ndimage.zoom(order=0)` | 195 modules on the first image, and a zoom per slice | `utils/_zoom.py`: the same nearest-neighbour lookup in numpy (`tests/test_thumbnail_zoom.py` compares it with scipy) |
| `canvas_to_world`, run on every draw, imported scipy.spatial first thing, in 2D too | about 100 modules and 0.75 s on the first 2D paint | the import sits in the 3D branch |
| every layer's default units were pint's `pixel` unit, so the first layer imported pint and built its registry | 0.6 s and 340 modules for the import, 0.2 s for the registry, in a fresh environment; half of the first image | `utils/_pixel.py`: a pixel stand-in equal to pint's unit, pint with the first real unit; the registry then from pint's definition cache (0.02 s against 0.2 s). First image 1.51 s to 1.13 s, window 3.85 s to 3.51 s, 71 modules fewer |
| one helper imported from `vispy.visuals.tube` loaded every vispy visual and `vispy.gloo` with the layers | about 100 modules before any canvas | `utils/_tube.py`, a copy of that function (BSD) |
| `progress` imported tqdm with the viewer model and the thread workers | about 50 modules (tqdm reads its own metadata at import) | imported where a progress bar is made; the own `utils/__init__.py` binds the names on first access |
| wrapt, a dependency for one base class, imported asyncio | 46 modules in a window | `utils/_object_proxy.py`, the part of `wrapt.ObjectProxy` that napari uses; wrapt is no longer a dependency |

In the local check environment (dev extras installed, so xarray and dask
are present) the first image went from 3.6 s and 1,570 modules to 1.6 s
and 804, the window from 5.7 s and 2,180 modules to 4.0 s and 1,470. The
first three rows exist in napari itself and are worth upstream pull
requests; after a resync that carries them the rules stop matching and
can be dropped.

What a shown viewer still loads that it does not need: dask, PyYAML,
toolz and psutil (about 70 modules) through pint's import-time probe for
dask, only when dask is installed; pygments through superqt's package
init. PyOpenGL (193 modules) is needed: napari's markers select vispy's
`gl+` backend.

Then scikit-image, scipy, toolz, pydantic-extra-types and pandas left
the dependencies (the install-size work). The own modules that stand
in for them are compared with the libraries element by element in
`tests/test_draw.py`, `test_colorconv.py`, `test_rotation.py`,
`test_linalg.py`, `test_morphology.py`, `test_tracks_index.py`,
`test_toolz.py`, `test_color.py` and `test_lite_features.py`, which run in
the `dev` environment; the `no-extras` CI job installs `napari-lite[pyqt6]`
alone, checks that none of those packages comes with it, and runs the own
tests against that install. The three findings that apply to napari itself
are patches in [docs/upstream.md](upstream.md).

pandas deserves a word, since `layer.features` is a DataFrame by API.
Every Points, Shapes, Labels, Vectors or Surface layer builds a feature
table on creation, which imported pandas (about 530 modules) for layers
that never get a feature. Now: in a process where pandas has been
imported, by the user or by a layer with features, every table is a
DataFrame and the copied code runs unchanged. In a process that has not,
a layer without features holds a zero-column stand-in that answers what
the layer's own code asks of such a table, and the first read of
`layer.features` or `feature_defaults`, or the first feature, turns it
into a real DataFrame, importing pandas then. Without pandas installed the
stand-in is what the layer hands out, and the first feature raises an
ImportError naming the `features` extra; Tracks always has a `track_id`
feature and needs the extra. `tests/test_lite_features.py` checks all of
this in fresh interpreters. Besides the install size, the first 3D view no longer stalls
on `scipy.spatial`, and the first Labels layer no longer imports
`skimage.color`. One known trade: the Tracks layer finds the vertices
nearest to the cursor by distance over all vertices instead of a KD-tree,
a few milliseconds per status update for a million vertices.

## Where the first frame goes

An issue proposed building the layer panel after the first paint ("the
window before its panels"), on the strength of a cProfile run that
charged the two docks 1.2 s of a 3.5 s window. Wall-clock marks
(`bench/first_frame.py`, the local check environment on the
same slow Windows machine, Python 3.13.7) tell a different story. A
script that imports napari-lite, makes a viewer, adds a 512 x 512 image
and shows the window reaches its first paint event after 3.07 s:

| stage | seconds |
|---|---|
| import numpy | 0.22 |
| import the components (viewer model, layers) | 0.95 |
| import qtpy (Qt) | 0.16 |
| import the window and canvas modules (vispy, PyOpenGL, superqt) | 0.79 |
| `QApplication()` | 0.02 |
| `Viewer(show=False)`: vispy canvas 0.19, layer controls 0.17, layer list 0.04, theme stylesheet 0.06 | 0.48 |
| `add_image` | 0.10 |
| `show()` to the first paint: Qt window 0.20, first GL draw with shader compilation 0.13 | 0.34 |

Import self time by package on that path (`python -X importtime`, 1,093
modules, 2.15 s with the profiler's own overhead): napari_lite 0.62
(utils 0.21, layers 0.17, _vispy 0.09, components 0.08), PyOpenGL 0.31,
vispy 0.28, qtpy 0.16, numpy 0.14, superqt 0.11, pydantic 0.10.

What it means:

- The layer panel (controls, list, button rows, docks) is 0.21 s, 7% of
  the first frame, and 0.17 s of that is importing the controls modules,
  which the first layer needs anyway. Building it after the first paint
  would move 0.2 s, and would need the panel's width and height before
  its widgets exist: they depend on the layer types present (the dock
  column is 272 px wide with no layers, 310 with an image, 304 with
  labels, and on a small screen the window grows to fit the controls), so
  a placeholder of the wrong size shifts the canvas when the panel fills.
  Not done.
- Two thirds of the time are imports, and most of those are not
  napari-lite's: PyOpenGL, vispy, qtpy and superqt together are 0.86 s of
  profiler time. The asks are in [upstream.md](upstream.md). napari-lite's
  own 0.6 s is spread over 400 modules, none larger than 0.04 s (the
  colormap table).
- `show()` is native work: Qt creates and polishes the window (0.20 s)
  and vispy draws the first frame, compiling the shaders (0.13 s).
- The order does not matter: `Viewer()` shown first and then `add_image`
  (what `imshow` does) reaches the first paint in the same 3.0 to 3.4 s.
- cProfile inflates Python-heavy widget construction several times over;
  stage marks with `time.perf_counter` decide what is worth doing.
- Not on the list: the theme's SVG icons. `register_theme_icons` writes
  them once under the temp directory behind a stamp file
  (`_qt/qt_event_loop.py`), so after the first run they cost nothing;
  nobody needs to profile them again.
