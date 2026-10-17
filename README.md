# napari-lite

**Experimental.** The viewer core of [napari](https://napari.org) without
the application around it: layers, canvas and dims sliders, importable as
`napari_lite` without napari installed. Derived from napari (BSD-3); see
[docs/development.md](docs/development.md) for how the copy is made.

```python
import numpy as np
import napari_lite as napari   # one-line swap

viewer, layer = napari.imshow(np.random.random((4, 256, 256)), colormap='magma')
viewer.add_points(np.array([[2, 100, 100], [2, 150, 50]]), size=10)
napari.run()
```

## Supported

- **napari's viewing API**: `Viewer()`, `imshow(array)`, `viewer.add_image`,
  `add_labels`, `add_points`, `add_shapes`, `add_vectors`, `add_surface`,
  `add_tracks`, `viewer.layers`, `viewer.dims`, `viewer.camera`,
  `viewer.screenshot()`, `viewer.close()`, `napari_lite.run()`. The same
  script gives the same layers with `napari` and `napari_lite`.
- **All seven layer types** in 2D and 3D with napari's rendering: colormaps,
  contrast limits, blending, multiscale images, grid mode, scale bar, axes
  and layer-name overlays.
- **Mouse and keyboard**: pan, zoom, rotate, dims sliders and playback, and
  napari's default key bindings for the viewer and every layer (paint, fill,
  pick, add points, draw shapes, ...), listed in
  [docs/shortcuts.md](docs/shortcuts.md).
- **`QtCanvas`**: canvas, dims sliders and status line as one Qt widget for
  your own window or application (`examples/canvas_only.py`).
- **A small window**: canvas, sliders and a status bar with cursor
  coordinates, layer value and help text; `viewer.window.add_dock_widget()`
  docks your own Qt or magicgui widgets.
- **Jupyter**: `%gui qt`, `nbscreenshot(viewer)` for inline screenshots
  (`examples/notebook.ipynb`).
- **Settings in code**: `get_settings()` with napari's names and defaults,
  per session, nothing written to disk.
- **Dark and light themes**; **thread workers** (`napari_lite.qt.thread_worker`).
- **Fast import**: `import napari_lite` takes about 0.05 s and loads no numpy,
  Qt, vispy or pydantic; napari, npe2, magicgui, app-model and lxml are never
  imported.

## Planned

- Benchmarks against napari on Linux, macOS and Windows: import time, time
  to first image, install size (first numbers in
  [docs/benchmarks.md](docs/benchmarks.md)).
- Heavy dependencies only on first use (dask, scikit-image, pandas, pint
  where possible) and smaller install extras.
- Visual regression tests: every layer type in 2D and 3D compared with
  napari screenshots.
- Opt-in layer list and layer controls (`viewer.add_layer_list()`,
  `viewer.add_layer_controls()`), loaded only when called, with the editing
  tools and undo/redo through them.
- A decision on data interpretation: keep napari's guessing of RGB and
  channel axis, or require `rgb=` / `channel_axis=`.
- Monthly resync with napari's main branch.

## Not planned

Plugins (readers, writers, sample data, widgets), the IPython console, menus
and the command palette, the preferences dialog and settings file, the
welcome screen. Load data with your own library (tifffile, imageio, zarr,
...) and pass arrays to `add_image`.

Issue list: [docs/backlog.md](docs/backlog.md).
