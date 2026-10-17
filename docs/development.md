# Developing napari-lite

## Derived from napari (BSD-3)

Most of the code in `src/napari_lite` is copied from napari and is copyright
the napari contributors, redistributed under the BSD 3-Clause license (see
[LICENSE](../LICENSE)). It is not hand-copied: `tools/vendor.py` copies the
napari core from a pinned commit on the `vendor` branch, rewrites `napari`
to `napari_lite`, and writes `VENDORED.json` with every module it took and
every import that crosses into napari's application code (settings, theme,
plugins, action manager, ...). Those crossings are the work: napari-lite
provides a small module of its own at each such import path.

- `vendor` branch: napari copy only, written by the tool, never edited by hand.
- `main`: `vendor` plus napari-lite's own code. Upstream updates arrive with
  `git merge vendor`.
- Own files start with `# napari-lite: own code`; the tool never overwrites them.

How to resync is written in [SYNC.md](../SYNC.md). The current copy is listed
in [VENDORED.json](../VENDORED.json): which napari commit, which modules,
and which imports cross into app modules that napari-lite must provide.
`src/napari_lite/utils/_keys` is copied from app-model (BSD-3) by
`tools/copy_app_model_keys.py`.

## Layout

```
src/napari_lite/   the package (copied napari core + own code)
tools/             vendor.py, vendor.toml, create_issues.py, make_shortcuts_doc.py
tests/             napari-lite's own tests (copied napari tests live next to the code)
bench/             import-time, time-to-first-image and install-size benchmarks
spikes/            throwaway experiments that informed the design
docs/              backlog.md (the issue list), shortcuts.md, this file
examples/          canvas_only.py, notebook.ipynb
```

## Tests

```
pip install -e .[dev,pyqt6]
pytest tests src/napari_lite        # own tests, then the copied napari tests
python spikes/spike_core.py         # smoke check with napari blocked
```

On Linux without a display, run the tests under `xvfb-run` or with
`QT_QPA_PLATFORM=offscreen`. On Windows and macOS run them as they are: the
Qt offscreen platform has no OpenGL there and the vispy tests need a GL
context (napari's own tests behave the same).

The copied napari tests run with the fixtures in
`src/napari_lite/conftest.py`. Test modules that need parts napari-lite
does not have are listed there with the reason; fixtures for plugins or
napari's `QtViewer` skip their tests with a reason.

## Vendoring

The napari checkout used for vendoring is separate from this repo:

```
git clone https://github.com/napari/napari ../napari
git -C ../napari checkout <pin from tools/vendor.toml>
python tools/vendor.py --napari ../napari --report   # what would be copied
python tools/vendor.py --napari ../napari --diff     # changes vs VENDORED.json
python tools/vendor.py --napari ../napari --why napari.utils.history
```

## Benchmarks

```
python bench/bench_imports.py --json lite.json           # in a napari-lite env
python bench/bench_imports.py --package napari --json napari.json   # in a napari env
python bench/install_size.py --json size.json
python bench/make_table.py lite.json napari.json size.json
```

`.github/workflows/bench.yml` runs these on the three OSes on request and
weekly.

## Backlog

The milestones and issues are in [backlog.md](backlog.md): M0 repo and copy,
M1 imports without napari, M2 first image on screen, M3 fast and small,
M4 full feature set, M5 sync and share. `tools/create_issues.py` files them
on GitHub.
