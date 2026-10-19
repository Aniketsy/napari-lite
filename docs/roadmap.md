# napari-lite: where it stands and where it goes

Status for version 0.1.0.

napari-lite is the napari viewer without the napari application: the
layers, the canvas, the dims sliders, the layer list and layer controls,
napari's key bindings and mouse tools, in a package that imports in 0.01 s
and needs 41 packages instead of 106. The code is napari's own, copied from
napari's `main` branch at commit `ebfc4a0a` by
[`tools/vendor.py`](../tools/vendor.py), with 44 small files of our own
(4,900 lines) where the copied core expects the application. Code written
for napari runs on it with `import napari_lite as napari` as long as it
stays inside what is listed below.

## What works

Everything here is covered by napari-lite's own tests and by the 4,300
napari tests that come with the copied code, on Linux, macOS and Windows
with Python 3.11 to 3.13 (PyQt6 or PySide6).

- **Viewer and window.** `Viewer()`, `imshow()`, `run()`,
  `current_viewer()`, the `napari-lite` command (`napari-lite image.png
  stack.npy`, `--labels`, `--ndisplay 3`). The window has napari's left
  column: layer controls, layer list with thumbnails and visibility, the
  layer and viewer buttons, the layer context menu (duplicate, convert,
  split and merge, projections, link, copy and paste of scale and
  transforms, visualization toggles), napari's stylesheet and icons, a
  status bar, `add_dock_widget` for your own widgets. An empty canvas says
  how to load data.
- **All seven layer types** in 2D and 3D with napari's rendering: Image
  (multiscale, RGB, colormaps, contrast limits, gamma, interpolation,
  blending, plane and volume rendering), Labels, Points, Shapes, Surface,
  Tracks, Vectors.
- **Editing tools.** Labels paint, fill, erase, pick, polygon; Points add,
  select, move, delete; Shapes draw, select, edit vertices, copy and paste;
  through the mode buttons of the controls, the key bindings and the mouse;
  undo and redo.
- **Navigation.** Dims sliders with playback, 2D/3D, roll and transpose,
  grid mode, reset view, camera and dims models, zoom box, every default
  key binding of napari ([docs/shortcuts.md](shortcuts.md)).
- **Overlays and output.** Scale bar, axes, text, colorbar, layer names and
  bounding boxes; `screenshot`, `export_figure`, clipboard, `nbscreenshot`
  in Jupyter.
- **View-only canvas.** `napari_lite.view` draws images and points with
  contrast limits, colormap, opacity, zoom and a slider per extra axis,
  with nothing to edit and none of napari's layer code: a small model,
  a vispy or a pygfx renderer behind it, a Qt widget with a readout of
  the value under the pointer; `show(image, points)` or `napari-lite
  --view` opens a window (issues #4 and #6).
- **Embedding.** `QtCanvas`: canvas, sliders and status line as one Qt
  widget for your own window; the layer list, controls and button rows
  come on first access (`examples/canvas_only.py`).
- **Data.** Any array with `shape`, `dtype` and `__getitem__`; dask arrays
  with the `dask` extra (the opportunistic cache included), zarr and xarray
  through their array interfaces, napari's rules for RGB and channel axes
  ([docs/design.md](design.md)).
- **Plumbing.** The same evented models and `events` as napari; settings
  with napari's names and defaults, in memory; dark and light themes;
  `thread_worker`, `create_worker`, `progress`.

Numbers measured against napari from the same commit, on one machine
([docs/benchmarks.md](benchmarks.md) has the details and the CI numbers):

| | napari-lite | napari |
|---|---|---|
| `import` the package | 0.01 s | 0.22 s |
| first image | 1.5 s | 3.3 s |
| viewer window shown with an image | 3.7 s | 6.0 s |
| memory with a window shown | 222 MB | 276 MB |
| installed size | 370 MB | 761 MB |
| packages installed | 31 | 106 |
| direct dependencies | 14 | 37 |

## Left out on purpose

Plugins (`viewer.open()`, `layer.save()`, sample data, plugin widgets raise
`NotImplementedError`: load data with your own library and pass arrays),
the IPython console, menus and the command palette, the preferences dialog
and the settings file, the welcome screen, notification pop-ups
(notifications go to the console), app-model. These are the application;
without them the package has no plugin engine, no app-model, no magicgui,
no lxml and no reason to start slowly.

## Is 0.1.0 ready to release?

What is in place:

- Version `0.1.0` in `pyproject.toml`, the 0.1.0 section of
  [`CHANGELOG.md`](../CHANGELOG.md), the license with napari's copyright
  and ours, the README with install instructions and the feature table.
- `python -m build` makes the sdist and the wheel; the wheel carries the
  icons, the stylesheet and the template the copied code reads.
- The complete test suite passes locally; CI runs it on three operating
  systems; the [release workflow](release.md) builds, checks, installs
  without napari, publishes to TestPyPI and makes the GitHub release on a
  `v*` tag.

CI is green on `main` at commit `b9cdeda`, the one with the layer panel.
What is left before the tag, in order:

1. The one-time setup in [docs/release.md](release.md): the `testpypi` and
   `pypi` environments on GitHub and a trusted publisher on test.pypi.org
   (and later pypi.org). The name `napari-lite` is free on both.
2. Tag `v0.1.0` and push it: the workflow publishes to TestPyPI. Install
   from there on a clean machine and open the examples.
3. PyPI only after the napari maintainers have been asked about the name
   (`Actions > Release > Run workflow` with target `pypi`).

Worth saying in the release notes: alpha; settings are not saved; the
themed icons are regenerated under the temp directory on first use;
the command line reads what imageio, tifffile and numpy read, nothing
else; the layer context menu has napari's layer entries and no plugin
entries.

## Roadmap

**0.1.x, right after the release**

- TestPyPI release, then PyPI once the name is settled.
- The first real resync with napari's `main` following
  [`SYNC.md`](../SYNC.md), when the weekly upstream report opens its first
  issue; record how long it takes and what conflicts.
- Fix what the first users report.

**0.2, a lighter start**

Done ([docs/benchmarks.md](benchmarks.md), "What the first
image stopped importing"): the first image and the first paint import
only what they use (no xarray probe, no scipy for a thumbnail or a 2D
draw, no vispy scene graph with the layers, tqdm on first use, no wrapt),
which took the first image from 2.2 s to 1.5 s and the window from 5.0 s
to 3.9 s in the fresh environment. The window gap to napari is now 1.5x;
what remains is shared: Qt, vispy, the first OpenGL context and the layer
widgets. The import-time and install-size gaps can still grow:

- The same three fixes offered to napari (the xarray check, the thumbnail
  zoom, `canvas_to_world`), so a resync brings them back for free.
- pint's import-time probe for dask (dask, PyYAML, toolz and psutil, about
  70 modules whenever dask is installed) made lazy in pint; superqt's
  package init made lazy (pygments and every widget come with the thread
  workers).
- The colormap table built on first access (about 100 Colormap models at
  import), scipy-free rotation helpers for the 3D camera (scipy.spatial
  is 0.75 s on this machine the first time 3D is used).
- scikit-image and scipy are out (done, 177 MB together:
  own line, polygon, points-in-polygon, flood fill, Luv/Lab conversions,
  rotations, QR/RQ, morphology filters and Tracks lookups in numpy, each
  compared with the library it replaces in the tests; scipy stays the
  `scipy` extra for spline-interpolated shapes), and so are toolz,
  pydantic-extra-types (imageio stays, the command line reads
  with it) and pandas (the `features` extra: layers without
  features use a zero-column stand-in, `layer.features` is a DataFrame
  whenever pandas is importable). The three findings that apply to napari
  itself are ready as patches, with the asks to superqt and pint, in
  [docs/upstream.md](upstream.md).
- The install is at 370 MB, of which 330 MB are Qt, numpy, vispy and
  PyOpenGL, the floor of any Qt viewer in Python; the size work is done.
  What remains for a faster start is on the first-image and first-paint
  paths: the colormap table built on first access, and the upstream
  patches once napari takes them. Target for the first image: under 1 s
  measured by the benchmark workflow.

**0.2, easier to work with**

- Open files by drag and drop and from a `--demo` option of the command
  line, with the readers the package already has (imageio, tifffile,
  numpy).
- A short guide for embedding `QtCanvas` and the layer panel in other Qt
  applications, and for Jupyter.
- napari's dynamic layer controls (several layers selected) switched on
  by its setting, as in napari.

**Ongoing**

- Monthly resync with napari (`SYNC.md`); the weekly upstream report tells
  when napari's core changed.
- The visual comparison tests (every layer type in 2D and 3D rendered by
  both packages) keep the rendering identical to napari's.
- Benchmarks on every push, on three operating systems.

**Not planned**

Plugins, console, menus, settings on disk, welcome screen: the application
side stays in napari. Someone who needs those needs napari.
