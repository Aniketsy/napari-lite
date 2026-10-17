# Benchmarks

Measured with `bench/bench_imports.py` (best of 3 fresh interpreters) and
`bench/install_size.py`; the table comes from `bench/make_table.py`.
`.github/workflows/bench.yml` repeats this on Linux, macOS and Windows in
fresh environments on request and weekly; those are the numbers to trust.

## Windows, 2026-10-17 (local, Python 3.13.7, PyQt6)

napari-lite in a fresh venv with its `[dev,pyqt6]` extras; napari from a
development environment with napari's testing extras. Both environments
therefore hold test tools the end user would not install, so the install
sizes overstate both packages; the import timings are unaffected.

| | napari_lite | napari |
|---|---|---|
| import package | 0.04 s | 0.26 s |
| import components | 1.71 s | 2.91 s |
| first image (ViewerModel + add_image) | 3.16 s | 4.81 s |
| Viewer(show=False) | 3.33 s | 5.93 s |
| installed size (MB) | 743 | 875 |
| packages installed | 92 | 160 |

Where `import napari_lite.components` spends its time (self time per
package, `python -X importtime`, same machine, cold):

| package | seconds |
|---|---|
| napari_lite's own modules | 0.60 |
| numpy | 0.38 |
| vispy | 0.24 |
| pint (with flexcache, flexparser) | 0.39 |
| pydantic (with pydantic_core) | 0.11 |
| dask (with cachey, toolz, yaml) | 0.19 |
| everything else | about 0.6 |

Issue 18 of the backlog acts on this: dask, scikit-image and pandas move to
first use. pint stays an import-time dependency: the layer and dims models
declare `pint.Unit` fields that pydantic evaluates when the classes are
created, and every layer's transform builds the unit registry, so deferring
`import pint` would gain nothing for the first image.
