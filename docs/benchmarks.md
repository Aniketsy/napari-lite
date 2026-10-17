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
