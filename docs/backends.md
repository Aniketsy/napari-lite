# Other rendering and widget backends (issue #5)

A plan, written before any code, revised after a review of its
downsides. The goal, in the words of the issue: the core works
without vispy or Qt imported; vispy and Qt are one option; existing
scripts keep working the same way by default.

## Where we stand

Measured on the current `main`:

- **Qt** is already out of the core. `import napari_lite.components`,
  `import napari_lite.layers`, a `ViewerModel` with an image and points:
  none of it loads qtpy, PyQt6 or PySide6. Qt arrives with the first
  `Viewer()`, through `napari_lite.window` (an import inside
  `Viewer.__init__`).
- **vispy** is not. The same import loads vispy, through eight
  module-level imports in copied napari code, none of them about drawing:

  | copied file | what it takes from vispy | replacement |
  |---|---|---|
  | `utils/events/event.py` | `_handle_exception`, one call that logs an exception raised in a callback | one function |
  | `utils/key_bindings.py` | `vispy.util.keys`: 18 key constants (`SHIFT`, `CONTROL`, `UP`, ...) that compare with strings | one small module |
  | `utils/colormaps/standardize_color.py` | the CSS colour names, hex parsing, `ColorArray` for nested colours | the CSS table (148 names, a fixed standard) and 40 lines of parsing |
  | `layers/shapes/shapes.py` | the colour names, for validation | the same table |
  | `utils/colormaps/colormap_utils.py` | vispy's colormaps by name (`hot`, `ice`, ...) and the `Colormap` type for conversion | lazy: used when vispy is installed, otherwise those names are unknown |
  | `layers/shapes/_shapes_utils.py` | `Triangulation`, the pure-python triangulation backend | lazy import inside the function; vispy stays one of the backends |
  | `utils/_tube.py` | `rotate`, a 4x4 rotation matrix | five lines of numpy |

- The drawing side is already one package, `napari_lite._vispy` (napari's
  `VispyCanvas` and one visual per layer), used from one place:
  `QtCanvas` (`qt/canvas.py`) builds it and hands it layers.
- `napari_lite.view`, the view-only canvas, already has the shape we want
  for the whole viewer: a model with signals, a `Renderer` contract, one
  adapter per item, two renderers (vispy, pygfx) and a widget that takes
  either. It is the working proof that the split holds, at small scale.
- vispy itself runs on many "app backends": every Qt binding, glfw,
  sdl2, wx, tkinter, pyglet, `jupyter_rfb` (an ipywidget in the browser),
  and `egl`/`osmesa` for headless rendering on Linux. The vispy renderer
  is not tied to Qt; only our `QtCanvas` is.

## The design

Three layers with two contracts between them, no base classes:

```
model        ViewerModel, layers, dims, camera, overlays, events, settings
             numpy, pydantic, psygnal; nothing else imported
                │
                │  CanvasBackend contract (a Protocol)
                ▼
renderer     napari_lite._vispy (the one there is), another one (later)
             makes a canvas for a ViewerModel, draws its layers, answers
             screenshots, maps canvas pixels to data coordinates
                │
                │  Window contract (a Protocol)
                ▼
front end    Qt (the one there is): QtCanvas, Window, the layer panel, the CLI
             headless (no window, screenshots only), Jupyter (later)
```

**CanvasBackend contract.** Written from the model's side, not from
vispy's: `native` (a widget for the front end, or None), `size`,
`screenshot()`, `add_layer(layer)`, `remove_layer(layer)`,
`set_camera_from_model()`, `data_position(canvas_xy)`,
`deliver_key_event(event)`, `close()`. The vispy-specific things
`QtCanvas` does as it stands (the grid cameras, the font manager, the 3D depth
workaround, the scene canvas for key events) move into the vispy adapter
and out of the contract, so that a second backend is not asked to imitate
vispy. The adapter is one own module over `VispyCanvas` as it is; the
canvas class is napari's and stays untouched.

**Window contract.** What `Viewer` uses from `Window`: `show`, `close`,
`activate`, `resize`, `set_geometry`, `screenshot`, `export_figure`,
`clipboard`, `add_dock_widget`, `remove_dock_widget`, the task status
hooks.

**Choosing.** `Viewer(renderer='vispy', gui='qt')`, with those defaults
so that every existing script keeps doing what it does. `gui=None` is
headless: a renderer but no window; `screenshot()` and `export_figure()`
work. The environment variables `NAPARI_LITE_RENDERER` and
`NAPARI_LITE_GUI` override the defaults, for notebooks and servers. The
two built-in backends are a static table (no lookup cost on the default
path); a name that is not in the table is looked up in the entry-point
groups `napari_lite.renderers` and `napari_lite.guis`, so another package
can add a backend without touching this one.

**Front ends own their widgets.** The layer list, the layer controls and
the button rows are napari's Qt widgets; they stay Qt. A Jupyter front
end would give the canvas, sliders and a small layer list in its own
toolkit. We do not build a toolkit-neutral widget layer: that is the
rebuild the issue warns about, in another form.

## Downsides, and what we do about them

- **We copy two small tables out of vispy** (the CSS colour names, the
  key constants). They are standards, not vispy inventions, and they do
  not change; the copied napari tests exercise them. Making the imports
  merely lazy instead would not do: a Points layer needs colour parsing
  the moment it is created, so the core would still need vispy in
  practice.
- **The rewrites are string matches.** If napari changes one of those
  import lines, the rewrite silently stops applying and vispy leaks back
  in. The rewrites replace whole import lines with imports from own
  modules that expose the same names, so the copied code's own lines
  never change; a subprocess test fails loudly when vispy comes back,
  and the weekly upstream report shows the changed line.
- **A contract shaped by vispy would be no contract.** The first draft
  listed what `QtCanvas` uses as it stands, which includes vispy's grid cameras
  and a depth workaround; that is handled by writing the contract from
  the model's needs and keeping vispy's oddities in the vispy adapter.
- **Entry points cost startup time** if scanned on every `Viewer()`.
  They are consulted only for a backend name that is not built in.
- **Headless without any window is platform-dependent.** vispy's `egl`
  and `osmesa` backends exist on Linux, which is where servers and CI
  are; on Windows and macOS, `gui=None` falls back to a hidden window of
  the default toolkit, which still means Qt is imported there. The
  documentation says so.
- **A Jupyter front end still needs a GL context on the server** (EGL
  or a virtual display), because `jupyter_rfb` streams frames rendered
  on the server. That is fine for the server case it serves.
- **`gui=None` has no `viewer.window`.** Scripts that call
  `viewer.window.add_dock_widget` are Qt scripts and keep working with
  the default; headless mode raises a clear error for them.
- **Two renderer contracts.** `napari_lite.view` keeps its small
  `Renderer` (items); the viewer's one is `CanvasBackend` (layers). Both
  live in `napari_lite.backends` and the docs say which is which.
- **A second full renderer is not made cheaper by any of this.** It is a
  port of every napari layer visual, a project of its own. What this plan
  secures is that it needs no change in the core, which is the point the
  issue makes.

## Progress

- Step 1 done (branch `fix-5`): the model imports and runs with vispy
  and Qt blocked, every layer type included; `tests/
  test_model_without_vispy.py` guards it, the plain-install CI job runs
  it with vispy uninstalled, the benchmark has a `model_all_layers`
  line. Measured on the benchmark machine (best of 3, Python 3.13,
  Windows): importing the model 1.19 s and 627 modules before, 0.80 s
  and 559 modules after; the model with one layer of every kind
  1.80 s and 967 modules before, 1.68 s and 907 after.

## The plan, step by step

**Step 1, the model without vispy** (the one step before the release).
Own modules: `utils/_colors.py` (the CSS table, hex parsing, the few
names vispy exposes), `utils/_key_names.py` (the 18 constants),
`utils/_tube_rotate.py` or a function in `utils/transforms`, a
`_handle_exception`, and a lazy wrapper for `Triangulation`. Seven
`literal_rewrites` lines in `tools/vendor.toml` turn the copied imports
into imports from these modules. Colormaps by vispy name keep working
when vispy is installed. Acceptance: in an environment without vispy,
`ViewerModel()` with every layer type works, and `import
napari_lite.components` loads no `vispy`; a subprocess test guards it,
the plain-install CI job uninstalls vispy and runs it, the benchmark
gains a "model only" line.

**Step 2, headless and the window seam.** `Viewer(gui=None)` on vispy's
offscreen backend where it exists; `screenshot()` and `export_figure()`
with no window; the Qt `Window` behind the Window contract;
`get_gui('qt')` as the default. Acceptance: a screenshot test that runs
on the Linux CI job with Qt not imported. This comes second because it
delivers something users ask for (servers, notebooks, CI figures) and
costs about a day.

**Step 3, the renderer seam.** `napari_lite/backends/__init__.py` with
the two Protocols and the lookup; `napari_lite/_vispy/backend.py` (own)
adapts `VispyCanvas`; `QtCanvas(viewer, renderer=...)` and
`Viewer(renderer=...)` pass it through. A fake backend in
`tests/test_backends.py` records the calls a `Viewer` makes and proves
the viewer runs against something that is not vispy. No visual changes.

**Step 4, a second front end.** Jupyter through `jupyter_rfb`: the vispy
canvas as an ipywidget, ipywidgets sliders for the dims, a minimal layer
list; `Viewer(gui='jupyter')` in a notebook cell. Smoke-tested where
`jupyter_rfb` is installed. Only if there is interest.

**Step 5, documentation.** `docs/architecture.md` gets the three layers
and the two contracts; the README's feature table a "Backends" row;
"existing scripts keep working" stays a test (`examples/` run
unchanged).

## Effort

Step 1 about a day, all in own modules and `vendor.toml`; it is what
makes the claim "the core imports without vispy or Qt" true, and it is
the only step with a risk, which the copied napari tests cover (colour
and colormap names must match what napari accepts). Steps 2 and 3
a day each, after the release; they add parameters with defaults, so
nothing breaks. Step 4 depends on demand.
