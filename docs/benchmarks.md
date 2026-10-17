# Benchmarks

Measured with `bench/bench_imports.py` (best of several fresh
interpreters) and `bench/install_size.py`; `bench/make_table.py` makes the
tables. `.github/workflows/bench.yml` runs them on Linux, macOS and Windows
in fresh environments, `pip install napari-lite[pyqt6]` against
`pip install napari[pyqt6]`, weekly and on request. Those are the numbers
to trust; a developer machine gives different ones depending on what else
is running.

## GitHub Actions, 2026-10-17

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
`[dev,pyqt6]` extras, cold, 2026-10-17). Total 2.8 s on this machine,
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

Decisions from backlog issue 18:

- dask and scikit-image are imported on first use: when a dask array is
  given to a layer, and for Labels colours and Shapes masks.
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
on the same Windows machine (Python 3.13.7, 2026-10-17, best of 3 fresh
interpreters). The machine is about four times slower than the CI
runners and had other work running, so read the ratios, not the seconds.
Memory is the resident set at the end of the measured code; "modules" is
`len(sys.modules)`. Measured again the same day after the layer panel went
in (napari's layer list, layer controls and button rows in napari-lite's
window): those are the numbers below. Before the panel, the window took
4.1 s and 236 MB and the package had 286 modules.

| | napari-lite | napari | napari-lite |
|---|---|---|---|
| import the package | 0.01 s | 0.22 s | 17x faster |
| import the components (viewer model) | 1.48 s | 2.66 s | 1.8x faster |
| first image: `ViewerModel` + `add_image` | 2.15 s | 3.18 s | 1.5x faster |
| `Viewer(show=False)`, closed | 3.29 s | 4.73 s | 1.4x faster |
| `Viewer` shown, one image painted, closed | 5.01 s | 6.14 s | 1.2x faster |
| memory after importing the package | 14 MB | 26 MB | 1.8x less |
| memory after the first image | 91 MB | 112 MB | 19% less |
| memory with a viewer window shown | 248 MB | 273 MB | 9% less |
| modules loaded by importing the package | 77 | 207 | 2.7x fewer |
| modules loaded at the first image | 1,026 | 1,357 | 1.3x fewer |
| installed size (all packages) | 611 MB | 761 MB | 150 MB less |
| packages installed | 41 | 106 | 65 fewer |
| direct dependencies | 20 | 37 | 17 fewer |
| Python modules in the package | 439 | 524 | 85 fewer |
| lines of Python in the package | 92,106 | 111,648 | 19,500 fewer |

Where the difference comes from:

- **Dependencies.** napari-lite keeps imageio, lazy-loader, numpy,
  packaging, pandas, Pillow, pint, psygnal, pydantic, pydantic-extra-types,
  PyOpenGL, qtpy, scikit-image, scipy, superqt, toolz, tqdm,
  typing-extensions, vispy and wrapt. It drops app-model, certifi,
  jsonschema, magicgui, napari-console, napari-plugin-engine,
  napari-resources, napari-svg, npe2, platformdirs, pydantic-settings,
  pygments, pywin32 and PyYAML, and moves dask, cachey and psutil to the
  `dask` extra and tifffile to the `tiff` extra. Most of the 65 fewer
  installed packages are what those pulled in.
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
  them to napari-lite's window cost 0.9 s and 12 MB), and what remains
  (Qt, vispy, the first OpenGL context) is the same too, which is why the
  gap narrows from 17x at import to 1.2x with a window shown.

To repeat it: `pip install ".[pyqt6]"` and
`pip install "<napari checkout>[pyqt6]"` into two fresh venvs, then in
each `python bench/bench_imports.py --package <name> --repeat 3 --json ..`
and `python bench/install_size.py --package <name> --json ..`, and
`python bench/make_table.py *.json`.
