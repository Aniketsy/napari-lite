# Backends: what draws and what shows

napari-lite's viewer is three parts that meet at two contracts, both in
[`napari_lite.backends`](../src/napari_lite/backends/__init__.py):

- the **model** (napari's viewer model, layers, dims, camera, events),
  which imports neither vispy nor Qt;
- a **renderer**, which draws the model and keeps itself in step with it:
  the `CanvasBackend` contract, vispy built in;
- a **front end**, which shows the renderer's canvas somewhere: the
  `Window` contract, the Qt window and the notebook window built in, or
  no window at all.

## Picking them

```python
import napari_lite

napari_lite.Viewer()                      # the Qt window, drawn by vispy
napari_lite.Viewer(gui='jupyter')         # widgets in a notebook cell
napari_lite.Viewer(gui=None)              # no window: screenshots only
napari_lite.Viewer(renderer='vispy')      # the renderer by name
napari_lite.Viewer(renderer=MyRenderer)   # or the class itself
```

`gui` and `renderer` take a name or a class. Their defaults come from two
environment variables, `NAPARI_LITE_GUI` (`qt`, `jupyter`, `none`, or a
registered name) and `NAPARI_LITE_RENDERER` (`vispy` or a registered
name), and are `qt` and `vispy` when those are not set. `QtCanvas` takes
`renderer=` too, for a canvas in your own Qt layout.

Without a window the vispy renderer draws off the screen. On Linux with
EGL it draws with no Qt in the process at all (text then needs
freetype-py, the `headless` extra); elsewhere the Qt binding draws into a
widget kept off the screen. For that Qt-free path name the renderer rather
than passing its class: importing the class imports PyOpenGL, which settles
its platform on GLX before napari-lite can ask for EGL (or set
`PYOPENGL_PLATFORM=egl` before importing). The notebook window needs the
`jupyter` extra and streams the frames of such an off-screen canvas through
a jupyter_rfb widget.

## Writing a renderer

A renderer is a class made as `Renderer(viewer, *, gui=None, parent=None)`:
`gui` is the toolkit the front end places the canvas in (`'qt'`,
`'jupyter'`, or None for no window), `parent` the front end's parent widget
when it has one. From then on it follows the model by itself: layers added
and removed, the camera, the dims, the overlays, the canvas size. It gives:

| member | what it is |
|---|---|
| `native` | the widget to place: a QWidget for `'qt'`, an ipywidget for `'jupyter'`, None without a window |
| `screenshot(*, size=None, scale=1.0, fit_to_data_extent=False, device_pixel_ratio=None)` | the canvas drawn now as an RGBA uint8 array, at `size` (height, width, device pixels) times `scale`, or sized around the data |
| `key_event(event, *, release=False)` | a key event the front end's widget received outside the canvas, for the key bindings |
| `close()` | let the model go and release the canvas |

A renderer that cannot draw for the `gui` it is asked for raises
`ValueError`. The smallest one that passes the front ends' tests is in
[`tests/test_backends.py`](../tests/test_backends.py) (`FakeBackend`): it
draws a green square and records what it is asked. The real one is
[`napari_lite/_vispy/backend.py`](../src/napari_lite/_vispy/backend.py).

## Writing a front end

A front end's window is made as `Window(viewer, *, show=True,
renderer=None)` (`renderer`: the renderer class to draw with, None for the
default) and gives what a `Viewer` uses: `show(block=False)`, `close()`,
`activate()`, `resize(width, height)`, `set_geometry(...)`, `geometry()`,
`screenshot(...)`, `export_figure(...)`, `clipboard(...)`,
`add_dock_widget(...)`, `remove_dock_widget(...)`, and the two methods
thread workers report to, `register_task_status(...)` and
`update_task_status(...)` (`napari_lite.utils.task_status.TaskStatusManager`
does the bookkeeping). Two more are optional: `show_shortcuts()` and
`open_files()`, the window's own versions of the actions behind
Ctrl+Alt+/ and Ctrl+O. The Qt one is
[`napari_lite/_qt/qt_main_window.py`](../src/napari_lite/_qt/qt_main_window.py),
the notebook one
[`napari_lite/backends/jupyter.py`](../src/napari_lite/backends/jupyter.py);
the headless viewer has no window and uses the renderer directly
([`backends/headless.py`](../src/napari_lite/backends/headless.py)).

## Registering them

Another package names its classes under two entry-point groups:

```toml
[project.entry-points."napari_lite.renderers"]
green = "mypackage.green:GreenRenderer"

[project.entry-points."napari_lite.guis"]
tk = "mypackage.tk:TkWindow"
```

After `pip install mypackage`, `Viewer(renderer='green')`,
`Viewer(gui='tk')`, `NAPARI_LITE_RENDERER=green` and `NAPARI_LITE_GUI=tk`
find them; `available_renderers()` and `available_guis()` list them after
the built-in names. The entry points are read once per process.

## Not the same thing: the view-only canvas

[`napari_lite.view`](../src/napari_lite/view/__init__.py) shows images and
points without napari's layers. It has renderers of its own, vispy and
pygfx, chosen with `QtView(view, renderer='pygfx')`: a smaller contract for
a smaller model, not registered in the groups above.
