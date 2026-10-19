# Architecture

napari-lite in one picture: what is napari's, what is napari-lite's own,
and where the two meet.

```
          your script or notebook                 your terminal
     import napari_lite as napari              napari-lite image.png
     Viewer, imshow, run, current_viewer,      napari-lite --sample stent
     nbscreenshot, QtCanvas (to embed)
                    |                                   |
 +------------------v-----------------------------------v------------------+
 | WINDOW                                                    own code      |
 |  _qt/qt_main_window.py   QMainWindow, status bar, dock widgets          |
 |  qt/canvas.py            QtCanvas: canvas, dims sliders, status line,   |
 |                          hint with links, dropped files, key events     |
 |  qt/_viewer_actions.py   Ctrl+O file dialog, key bindings window        |
 |  backends/               CanvasBackend and Window, the two contracts;   |
 |                          get_renderer, get_gui; headless (gui=None)     |
 |  backends/jupyter.py     the notebook window (gui='jupyter')            |
 |  _vispy/backend.py       VispyBackend, vispy behind the contract        |
 |  _vispy/_jupyter.py      the canvas as a jupyter_rfb widget             |
 | - - - - - - - - - - - - - - - - - - - - - - - - - -  copied from napari |
 |  layer list, layer controls, layer and viewer buttons, QtDims,          |
 |  stylesheet and icons (_qt/)            rendering with vispy (_vispy/)  |
 +-----------------------------------+-------------------------------------+
                                     | events
 +-----------------------------------v-------------------------------------+
 | MODEL                                                copied from napari |
 |  components/   ViewerModel: dims, camera, grid, overlays, layer list    |
 |  layers/       Image  Labels  Points  Shapes  Surface  Tracks  Vectors  |
 |  utils/        events, colormaps, transforms, key bindings, ...         |
 +-------+----------------------------+---------------------------+--------+
         | where napari calls          | where napari imports      | what napari
         | plugins or app-model        | a heavy package           | saves
 +-------v-----------+  +-------------v---------------+  +--------v----------+
 | SHIMS    own code |  | STAND-INS   own code, numpy |  | SETTINGS, THEMES  |
 |  plugins/         |  |  _draw          scikit-image|  |          own code |
 |   built-in reader,|  |  _rotation, _linalg,        |  |  settings/        |
 |   samples,        |  |  _morphology, _zoom,        |  |   napari's model  |
 |   no writers      |  |  _tracks_index        scipy |  |   and defaults,   |
 |  _app_model/,     |  |  _toolz               toolz |  |   in memory       |
 |  _qt/_qapp_model/ |  |  _object_proxy        wrapt |  |  utils/theme      |
 |   no app-model,   |  |  _color  pydantic-extra-    |  |   dark and light  |
 |   context menu    |  |          types              |  |  utils/           |
 |   rebuilt         |  |  _lite_features      pandas |  |   action_manager, |
 |  qt/threading     |  |          (only if installed)|  |   _keys           |
 |                   |  |  _pixel   pint's pixel unit |  |                   |
 +-------------------+  +-----------------------------+  +-------------------+
                                     |
 +-----------------------------------v-------------------------------------+
 | DEPENDENCIES, 14 direct: numpy, vispy, PyOpenGL, Qt (pyqt6 or pyside6), |
 |  qtpy, superqt, psygnal, pydantic, pint, imageio, Pillow, lazy_loader,  |
 |  packaging, tqdm, typing_extensions                                     |
 |  extras: features (pandas), scipy, dask, tiff, fast-shapes              |
 +-------------------------------------------------------------------------+
```

## The pieces

- **Model** (copied, unchanged). napari's viewer model and its seven layer
  types: data, dims, camera, layer state and the events that announce
  every change. napari-lite does not touch this code, so it behaves as
  napari does.
- **Window** (napari's widgets in napari-lite's own frame). The layer
  list, layer controls, buttons, sliders and the vispy rendering are
  napari's. The own parts add what a window without menus needs: the
  hint in the empty canvas with its links, files dropped on the canvas,
  Ctrl+O, the key bindings window, and `QtCanvas` so the same canvas fits
  into any Qt application.
- **Backends** (own). Three layers meet at two contracts
  (`napari_lite.backends`): the model imports neither vispy nor Qt; a
  renderer (`CanvasBackend`; vispy, in `_vispy/backend.py`) draws it; a
  front end (`Window`; Qt) shows it. `Viewer(renderer=..., gui=...)`
  picks them, `gui='jupyter'` shows the viewer in a notebook cell,
  `gui=None` draws without a window, and another package adds its own
  by entry point ([backends.md](backends.md)).
- **Shims** (own). Small modules at napari's import paths, where the
  copied code would call plugins or app-model. A built-in reader and a
  few samples stand in for reader plugins; writers raise a clear error;
  the layer context menu is rebuilt without app-model.
- **Stand-ins** (own). numpy versions of the few functions napari used
  from scikit-image, scipy, toolz, wrapt and pydantic-extra-types, each
  tested against the original; a pixel stand-in for the default unit, so
  pint loads only with the first real unit; pandas only when installed.
- **Settings and themes** (own). napari's settings model with napari's
  defaults, kept in memory; the dark and light themes; the action manager
  and key types the key bindings need.
- **Dependencies**. Qt, vispy and numpy do the heavy lifting; the rest
  are small. 75 files in the package are own code; everything else,
  napari's tests included, is copied.

## How napari's code gets in

```
 napari repository, pinned commit (ebfc4a0a)
        |
        |  tools/vendor.py with tools/vendor.toml:
        |  which modules to copy, napari -> napari_lite,
        |  102 text replacements for the places that must differ
        v
 "vendor" branch: the generated copy, listed in VENDORED.json
        |
        |  git merge
        v
 "main": the copy + the own files (first line: # napari-lite: own code)
        |
        |  pytest: own tests + napari's copied tests; CI on 3 OSes
        v
 pip install napari-lite[pyqt6]
```

Three rules keep this honest. Copied files are never edited by hand: a
change is a replacement rule, and the copy is regenerated. Own files are
marked on their first line. napari's tests travel with the copy, and the
ones for parts napari-lite does not have are skipped by a rule. A resync
is therefore mechanical: move the pin, run the script, merge, fix the
rules that stopped matching.

## Left out on purpose

Plugins (readers, writers, sample data, widgets), the menus and command
palette, the IPython console, the preferences dialog and the settings
file, the welcome screen. The built-in reader and samples cover the
first-run cases; everything else comes in as arrays through `add_image`
and friends.

## Where to look next

[design.md](design.md) for how data is interpreted,
[backends.md](backends.md) for the renderer and front-end contracts,
[development.md](development.md) and [../SYNC.md](../SYNC.md) for the copy
and the resync, [benchmarks.md](benchmarks.md) for the numbers,
[upstream.md](upstream.md) for the patches napari-lite found for napari.
