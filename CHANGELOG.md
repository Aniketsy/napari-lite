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
- dask and scikit-image are imported on first use; pandas stays a
  dependency (the layer features tables), pint is imported with the layers.
