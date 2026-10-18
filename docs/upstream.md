# Upstream: what napari-lite found that belongs in napari and its dependencies

Three of the first-image fixes of 2026-10-17 (docs/benchmarks.md, "What
the first image stopped importing") are not napari-lite specific: napari
has the same code, and its users pay the same imports. They are carried
here as `[[rewrite]]` rules in `tools/vendor.toml`; once napari takes
them, the rules stop matching at the next resync and can be dropped. A
fourth rule, from the functionality check of 2026-10-17, fixes a console
encoding error that napari has too (patch 4).

## Patches for napari

The patches in [`docs/upstream/`](upstream/) apply to napari's `main` at
`ebfc4a0a` (the pinned commit; `main` had not moved when they were made).
They were made on branches of the local napari checkout, `lite/xarray-check`,
`lite/canvas-to-world`, `lite/thumbnail-zoom`, `lite/console-notification` and
`lite/controls-prefilled`,
with napari's pre-commit
hooks passing; napari's own test-suite was not run on them here (the copy of
that suite inside napari-lite passes with the identical changes). To open a
pull request: push the branch to the fork and open it against
`napari/napari` `main`, or `git am` the patch file on a fresh branch.

1. **Skip the xarray check in `_check_xarray` until xarray is imported**
   (`utils/_xarray_utils.py`). Every new layer runs the check, which imports
   xarray, and pandas with it, whenever xarray is installed: about 450
   modules and, on a slow disk, a second on the first layer. An xarray
   object can only exist once xarray is in `sys.modules`. Follow-up to the
   xarray metadata work in #9316.
2. **Import scipy's `Rotation` in `canvas_to_world` only on the 3D path**
   (`components/viewer_model.py`). The method runs on every draw and
   imported `scipy.spatial` first thing, in 2D too, where it is unused;
   the first paint of a 2D viewer stalled on it (about 100 modules).
   Follow-up to #9517.
3. **Downsample thumbnails in numpy instead of importing `scipy.ndimage`**
   (`layers/utils/layer_utils.py`, `layers/image/image.py`,
   `layers/labels/labels.py`). The thumbnails used `ndimage.zoom` with
   `order=0`, a nearest-neighbour lookup; the import (about 200 modules)
   was the largest cost of the first image after xarray, and the zoom ran
   on every slice. `zoom_nearest` returns the same pixels; the one
   difference is at the very edge: where floating-point error puts the
   last coordinate a hair past the last pixel, scipy's default mode blanks
   that row or column, and the edge pixel is used instead. Worth saying in
   the pull request, since it is a visible, if better, change.
4. **Print console notifications on consoles with a legacy encoding**
   (`utils/notifications.py`, with a test). `show_console_notification`
   printed with a bare `print()`. When stdout has a legacy encoding, cp1252
   on Windows whenever the output is piped or redirected, a message with a
   character outside it (the shift arrow of a shortcut, for one) raised
   `UnicodeEncodeError` inside `print`; the `except` around it logged "An
   error occurred while trying to format an error ... You can try to
   uninstall IPython" and the message was lost. Encoding with
   `errors='replace'` first shows the message with those characters as
   `?`. Found by napari-lite's functionality check of 2026-10-17.
5. **Give layer controls to the layers that exist before the container**
   (`_qt/layer_controls/qt_layer_controls_container.py`, with a test). The
   container made controls only for layers inserted after it existed, so
   a `ViewerModel` that already held layers, handed to a `QtViewer` for
   embedding, raised `KeyError` in `_populate` on the first selection
   change and showed nothing for them. Existing layers are now added at
   construction. Found on 2026-10-18 while profiling napari-lite, whose
   `QtCanvas(viewer)` takes the same path. The patch file is a plain
   `git diff` with a mail header (made without a commit); `git am` reads it.

Measured in a fresh environment, napari at that commit, after the three
changes together: the first image fell from about 2.2 s and 1,026 loaded
modules to 1.5 s and 729 (napari-lite's numbers; napari's own would move
by the same imports).

## Asks for two dependencies

**superqt**: `superqt/__init__.py` imports every widget eagerly, and
`superqt.combobox._color_combobox` imports `superqt.utils._code_syntax_highlight`,
which imports pygments. A viewer that needs only the thread workers and two
sliders therefore loads 35 superqt modules and pygments (8.7 MB installed,
a dependency pin for every user) at startup. Request: lazy attributes in
`superqt/__init__.py` (PEP 562, as `napari.utils` does) and pygments as an
optional dependency of the syntax highlighter.

**pint**: `pint/compat.py` imports `dask.base` at import time whenever dask
is installed, to support dask arrays in quantities, and `dask` brings
PyYAML, toolz, psutil and cloudpickle: about 70 modules and 0.25 s on a
slow machine for every program that imports pint in an environment with
dask, dask array or not. Request: import `dask.base` lazily, at the first
operation that needs `compute`, `persist` or `visualize`, as `dask.array`
already is through `_LazyDaskArray`.

Neither has been filed yet; the texts above are ready to paste.
