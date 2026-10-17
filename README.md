# napari-lite

**Experimental.** The viewer core of [napari](https://napari.org) without
the application around it: layers, canvas and dims sliders, importable as
`napari_lite` without napari installed. Derived from napari (BSD-3); see
[docs/development.md](docs/development.md) for how the copy is made.

napari-lite keeps napari's API and behaviour wherever it has the feature,
so napari's documentation applies: every row of the table below links the
napari pages for that feature.

## Install

Not on PyPI yet. Install from GitHub with one of the two Qt bindings:

```
pip install "napari-lite[pyqt6] @ git+https://github.com/Aniketsy/napari-lite"
```

Extras: `pyqt6` or `pyside6` (one of them is needed), `dask` (dask
arrays), `fast-shapes` (compiled triangulation and label colouring),
`tiff` (tifffile), `all`. Python 3.11 to 3.13 on Linux, macOS and Windows.

```python
import numpy as np
import napari_lite as napari   # one-line swap

viewer, layer = napari.imshow(np.random.random((4, 256, 256)), colormap='magma')
viewer.add_points(np.array([[2, 100, 100], [2, 150, 50]]), size=10)
napari.run()
```

## Supported

Everything in this table works today and is covered by napari's copied
tests and napari-lite's own tests, run on Linux, macOS and Windows without
napari installed.

| Feature | In napari-lite | napari documentation |
|---|---|---|
| Viewer, `imshow`, event loop | `Viewer()`, `imshow(data, ...)` returning `(viewer, layer)`, `current_viewer()`, `run()`; `viewer.show()`, `viewer.close()`, `Viewer.close_all()`. The same script gives the same layers with `napari` and `napari_lite`. | [Viewer](https://napari.org/stable/api/napari.Viewer.html), [imshow](https://napari.org/stable/api/napari.html#napari.imshow), [run](https://napari.org/stable/api/event_loop.html), [current_viewer](https://napari.org/stable/api/napari.html#napari.current_viewer), [Launch from a Python script](https://napari.org/stable/getting_started/launch_napari.html#python-script-usage), [Launch from IPython](https://napari.org/stable/getting_started/launch_napari.html#ipython-console-usage) |
| Adding and managing layers | `viewer.add_image`, `add_labels`, `add_points`, `add_shapes`, `add_surface`, `add_tracks`, `add_vectors`, `add_layer`; `viewer.layers` with selection, ordering and extent; layer `scale`, `translate`, `affine`, `units`, `opacity`, `blending`, `visible`. | [Layers guide](https://napari.org/stable/howtos/layers/index.html), [Layers: bringing data into napari](https://napari.org/stable/getting_started/layers.html), [LayerList](https://napari.org/stable/api/napari.components.LayerList.html), [Layer](https://napari.org/stable/api/napari.layers.Layer.html), [Scale and unit-aware rendering](https://napari.org/stable/guides/units.html), [Transformed image](https://napari.org/stable/gallery/add_image_transformed.html) |
| Image | 2D and 3D, multiscale, RGB, `channel_axis`, colormaps, contrast limits, gamma, interpolation, blending, plane and volume rendering, depiction, custom interpolation kernels. | [Image how-to](https://napari.org/stable/howtos/layers/image.html): [arguments of imshow and add_image](https://napari.org/stable/howtos/layers/image.html#arguments-of-imshow-and-add-image), [multiscale](https://napari.org/stable/howtos/layers/image.html#multiscale-images), [RGB](https://napari.org/stable/howtos/layers/image.html#viewing-rgb-vs-luminance-grayscale-images), [multichannel](https://napari.org/stable/howtos/layers/image.html#loading-multichannel-images), [colormaps](https://napari.org/stable/howtos/layers/image.html#working-with-colormaps), [contrast limits](https://napari.org/stable/howtos/layers/image.html#adjusting-contrast-limits); [Image API](https://napari.org/stable/api/napari.layers.Image.html), [Colormap](https://napari.org/stable/api/napari.utils.Colormap.html), [3D image](https://napari.org/stable/gallery/add_3D_image.html), [3D plane rendering](https://napari.org/stable/gallery/3D_image_plane_rendering.html), [Rendering](https://napari.org/stable/guides/rendering.html) |
| Labels | Display in 2D and 3D, colour modes, contours; editing with the key bindings and the mouse: paint, fill, erase, pick, polygon, brush size, preserve labels, undo and redo. | [Labels how-to](https://napari.org/stable/howtos/layers/labels.html): [editing](https://napari.org/stable/howtos/layers/labels.html#editing-using-the-tools-in-the-gui), [undo and redo](https://napari.org/stable/howtos/layers/labels.html#undo-redo-functionality), [from the console](https://napari.org/stable/howtos/layers/labels.html#controlling-the-labels-layer-from-the-console); [Labels API](https://napari.org/stable/api/napari.layers.Labels.html), [Paint nD](https://napari.org/stable/gallery/paint-nd.html), [Labels in 3D](https://napari.org/stable/gallery/labels3d.html) |
| Points | Display in 2D and 3D; size, symbol, border and face colours, features and text; add, select, move and delete with the key bindings and the mouse. | [Points how-to](https://napari.org/stable/howtos/layers/points.html): [adding, deleting and selecting](https://napari.org/stable/howtos/layers/points.html#adding-deleting-and-selecting-points), [programmatically](https://napari.org/stable/howtos/layers/points.html#controlling-the-points-layer-programmatically); [Points API](https://napari.org/stable/api/napari.layers.Points.html), [Add points](https://napari.org/stable/gallery/add_points.html) |
| Shapes | Rectangles, ellipses, lines, paths, polygons and lasso; edge and face colours, text; draw, select, move, edit vertices, copy and paste with the key bindings and the mouse. | [Shapes how-to](https://napari.org/stable/howtos/layers/shapes.html): [adding shapes](https://napari.org/stable/howtos/layers/shapes.html#adding-new-shapes), [selecting and editing](https://napari.org/stable/howtos/layers/shapes.html#selecting-resizing-moving-editing-and-deleting-shapes), [programmatically](https://napari.org/stable/howtos/layers/shapes.html#controlling-the-shapes-layer-programmatically); [Shapes API](https://napari.org/stable/api/napari.layers.Shapes.html), [Annotate 2D](https://napari.org/stable/gallery/annotate-2d.html), [Triangulation backends](https://napari.org/stable/guides/triangulation.html) (the `fast-shapes` extra) |
| Surface | Vertices, faces and values in 2D and 3D; colormaps, shading, wireframe, normals. | [Surface how-to](https://napari.org/stable/howtos/layers/surface.html), [Surface API](https://napari.org/stable/api/napari.layers.Surface.html), [Add surface](https://napari.org/stable/gallery/add_surface_2D.html) |
| Tracks | Tracks with graph, tail and head length, colour by feature, in 2D and 3D. | [Tracks how-to](https://napari.org/stable/howtos/layers/tracks.html), [Tracks API](https://napari.org/stable/api/napari.layers.Tracks.html), [Tracks 2D](https://napari.org/stable/gallery/tracks_2d.html), [Tracks 3D](https://napari.org/stable/gallery/tracks_3d.html) |
| Vectors | Vectors in 2D and 3D; length, width, colour by feature. | [Vectors how-to](https://napari.org/stable/howtos/layers/vectors.html), [Vectors API](https://napari.org/stable/api/napari.layers.Vectors.html), [Add vectors](https://napari.org/stable/gallery/add_vectors.html) |
| Dims and camera | `viewer.dims` (current step, order, axis labels, `ndisplay`), `viewer.scene.camera` (center, zoom, angles, perspective); dims sliders with playback, 2D/3D toggle, roll and transpose, reset view. | [Dims API](https://napari.org/stable/api/napari.components.Dims.html), [Camera API](https://napari.org/stable/api/napari.components.Camera.html), [Camera guide](https://napari.org/stable/guides/camera.html), [Dimension sliders](https://napari.org/stable/getting_started/viewer.html#dimension-sliders), [Playback](https://napari.org/stable/getting_started/viewer.html#frame-playback-button), [2D/3D toggle](https://napari.org/stable/getting_started/viewer.html#toggle-2d-3d-button), [Roll](https://napari.org/stable/getting_started/viewer.html#roll-dimensions) and [transpose](https://napari.org/stable/getting_started/viewer.html#transpose-dimensions) dimensions, [Axis names](https://napari.org/stable/guides/axis-names.html), [nD image](https://napari.org/stable/gallery/nD_image.html) |
| Mouse and keyboard | Pan, zoom, rotate, zoom box, slice stepping with the wheel; napari's default key bindings for the viewer and every layer, listed in [docs/shortcuts.md](docs/shortcuts.md); `viewer.bind_key`, `layer.bind_key`, mouse drag, move and wheel callbacks. Shortcuts are configured in code, not in a dialog. | [Shortcuts](https://napari.org/stable/guides/preferences.html#shortcuts-settings), [Custom key bindings](https://napari.org/stable/gallery/custom_key_bindings.html), [Custom keybinding](https://napari.org/stable/getting_started/viewer.html#custom-keybinding), [Custom mouse functions](https://napari.org/stable/gallery/custom_mouse_functions.html), [Mouse drag callback](https://napari.org/stable/gallery/mouse_drag_callback.html), [Cursor position](https://napari.org/stable/gallery/cursor_position.html), [3D interactivity](https://napari.org/stable/guides/3D_interactivity.html) |
| Grid mode | `viewer.canvas.grid.enabled`, shape and stride; `Ctrl+G`. | [Grid mode](https://napari.org/stable/gallery/grid_mode.html), [Grid button](https://napari.org/stable/getting_started/viewer.html#grid-button), [Colorbars and overlays in grid mode](https://napari.org/stable/gallery/colorbar_tiling.html) |
| Overlays | Scale bar, canvas and scene axes, text, colorbar and current slice through `viewer.canvas.overlays` and `viewer.scene.overlays`; layer name and bounding box through `layer.name_overlay` and `layer.bounding_box`. | [Viewer overlays](https://napari.org/stable/getting_started/viewer.html#viewer-overlays), [Scale bar](https://napari.org/stable/gallery/scale_bar.html), [Bounding box](https://napari.org/stable/gallery/image_border.html), [Layer text scaling](https://napari.org/stable/gallery/layer_text_scaling.html) |
| Screenshots | `viewer.screenshot(path, canvas_only=...)`, `viewer.export_figure()`, `viewer.window.clipboard()`. | [screenshot](https://napari.org/stable/api/napari.Viewer.html#napari.Viewer.screenshot), [export_figure](https://napari.org/stable/api/napari.Viewer.html#napari.Viewer.export_figure), [To screenshot](https://napari.org/stable/gallery/to_screenshot.html), [Export figure](https://napari.org/stable/gallery/export_figure.html) |
| `QtCanvas` | Canvas, dims sliders and status line as one Qt widget for your own window or application (`examples/canvas_only.py`): the part of napari's `QtViewer` without layer list, controls and console. | [QtViewer](https://napari.org/stable/api/napari.qt.QtViewer.html), [Multiple viewer widget](https://napari.org/stable/gallery/multiple_viewer_widget.html) |
| Window and dock widgets | A small window: canvas, sliders and a status bar with cursor coordinates, layer value and help text; `viewer.window.add_dock_widget()` and `remove_dock_widget()` for Qt or magicgui widgets, `resize`, `set_geometry`, `screenshot`. | [Window](https://napari.org/stable/api/napari.window.Window.html), [add_dock_widget](https://napari.org/stable/api/napari.window.Window.html#napari.window.Window.add_dock_widget), [Creating widgets with magicgui](https://napari.org/stable/howtos/extending/magicgui.html), [Status bar](https://napari.org/stable/getting_started/viewer.html#status-bar) |
| Jupyter | `%gui qt` (optional: `imshow` enables it), `nbscreenshot(viewer)` for inline screenshots (`examples/notebook.ipynb`), without lxml. | [Jupyter notebook usage](https://napari.org/stable/getting_started/launch_napari.html#jupyter-notebook-usage), [nbscreenshot](https://napari.org/stable/api/napari.utils.html#napari.utils.nbscreenshot), [NotebookScreenshot](https://napari.org/stable/api/napari.utils.NotebookScreenshot.html) |
| Settings | `get_settings()` with napari's section and field names and defaults (`application`, `appearance`, `shortcuts`, `advanced`, `experimental`), evented, per session; nothing is read from or written to disk. | [Programmatic access to the settings](https://napari.org/stable/guides/preferences.html#programmatic-access-to-the-settings), [Application](https://napari.org/stable/guides/preferences.html#application-settings), [Appearance](https://napari.org/stable/guides/preferences.html#appearance-settings), [Advanced](https://napari.org/stable/guides/preferences.html#advanced-settings) and [Experimental](https://napari.org/stable/guides/preferences.html#experimental-settings) settings |
| Themes | Dark and light, `viewer.theme`, `Ctrl+Shift+T`; the window follows with a small stylesheet. | [Changing the viewer theme](https://napari.org/stable/getting_started/viewer.html#changing-the-viewer-theme), [Creating and testing themes](https://napari.org/stable/howtos/themes.html), [Set theme](https://napari.org/stable/gallery/set_theme.html) |
| Threads | `napari_lite.qt.thread_worker`, `create_worker`, `FunctionWorker`, `GeneratorWorker`; `progress` and `cancelable_progress`. | [Multithreading in napari](https://napari.org/stable/guides/threading.html), [napari.qt.threading](https://napari.org/stable/api/napari.qt.threading.html), [progress](https://napari.org/stable/api/napari.utils.progress.html) |
| Events | The same evented models and `events` attributes as napari on the viewer, dims, camera, layer list and every layer; notifications go to the console. | [Hooking up your own events](https://napari.org/stable/howtos/extending/connecting_events.html), [Events reference](https://napari.org/stable/guides/events_reference.html), [napari.utils.events](https://napari.org/stable/api/napari.utils.events.html), [notifications](https://napari.org/stable/api/napari.utils.notifications.html) |
| Dask, zarr, xarray | Any array with `shape`, `dtype` and `__getitem__`; dask arrays with the `dask` extra (opportunistic cache, task fusion off while slicing); asynchronous slicing. | [Image data and numpy-like arrays](https://napari.org/stable/howtos/layers/image.html#image-data-and-numpy-like-arrays), [Using Dask and napari](https://napari.org/stable/tutorials/dask.html), [Dask nD image](https://napari.org/stable/gallery/dask_nD_image.html), [Performance](https://napari.org/stable/guides/performance.html) |
| Fast import, small install | `import napari_lite` takes about 0.05 s and loads no numpy, Qt, vispy or pydantic; napari, npe2, magicgui, app-model and lxml are never imported; dask and scikit-image are imported on first use. Numbers in [docs/benchmarks.md](docs/benchmarks.md). | [napari performance](https://napari.org/stable/guides/performance.html) |

Data is interpreted exactly as napari interprets it (RGB and multiscale
are guessed, the channel axis never): [docs/design.md](docs/design.md).
Where napari is installed, `tests/test_visual_napari.py` renders every
layer type in 2D and 3D with both packages and compares the images.

## Planned

- Opt-in [layer list](https://napari.org/stable/getting_started/viewer.html#layer-list)
  and [layer controls](https://napari.org/stable/getting_started/viewer.html#layer-controls)
  (`viewer.add_layer_list()`, `viewer.add_layer_controls()`), loaded only
  when called; the editing tools and undo/redo through them.
- Monthly resync with napari's main branch ([SYNC.md](SYNC.md)); the
  weekly upstream report opens an issue when napari's core changes.
- A PyPI release ([docs/release.md](docs/release.md)), after asking the
  napari maintainers about the name; TestPyPI until then.

## Not planned

[Plugins](https://napari.org/stable/plugins/index.html) (readers, writers,
sample data, widgets: `viewer.open()` and `layer.save()` raise
`NotImplementedError`), the
[IPython console](https://napari.org/stable/getting_started/viewer.html#console-button),
[menus and the command palette](https://napari.org/stable/getting_started/viewer.html#main-menu-or-top-bar-menu),
the [preferences dialog](https://napari.org/stable/guides/preferences.html#the-preferences-dialog)
and [settings file](https://napari.org/stable/guides/preferences.html#where-settings-are-stored),
the welcome screen. Load data with your own library (tifffile, imageio,
zarr, ...) and pass arrays to `add_image`.

Issue list: [docs/backlog.md](docs/backlog.md). Shortcuts:
[docs/shortcuts.md](docs/shortcuts.md). How the copy is made and kept in
sync: [docs/development.md](docs/development.md), [SYNC.md](SYNC.md).
