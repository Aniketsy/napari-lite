# napari-lite

**Status: experimental. Nothing here is released or supported yet.**

napari-lite is the viewer core of [napari](https://napari.org) without the
application around it: the layer models, the vispy canvas and the dims
sliders, importable as `napari_lite` without napari installed. There is no
plugin manager, no settings file, no menus, no layer list or layer controls
(those come back as opt-ins later). You load data with your own library and
call `add_image`.

The idea comes from napari issue
[#5940](https://github.com/napari/napari/issues/5940) ("napari-lite"). The
aim is a package that imports fast, installs small, and swaps in for napari
with one line (`import napari_lite as napari`) in scripts that only view
arrays.

## Derived from napari (BSD-3)

Most of the code in `src/napari_lite` is copied from napari and is
copyright the napari contributors, redistributed under the BSD 3-Clause
license (see [LICENSE](LICENSE)). It is not hand-copied: `tools/vendor.py`
copies the napari core from a pinned commit on the `vendor` branch, rewrites
`napari` to `napari_lite`, and writes `VENDORED.json` with every module it
took and every import that crosses into napari's application code
(settings, theme, plugins, action manager, ...). Those crossings are the
work: napari-lite provides a small module of its own at each such import
path.

- `vendor` branch: napari copy only, written by the tool, never edited by hand.
- `main`: `vendor` plus napari-lite's own code. Upstream updates arrive with
  `git merge vendor`.
- Own files start with `# napari-lite: own code`; the tool never overwrites them.

How to resync is written in `SYNC.md`.

## Layout

```
src/napari_lite/   the package (copied napari core + own shims)
tools/             vendor.py, vendor.toml, create_issues.py
tests/             napari-lite's own tests (copied napari tests live next to the code)
bench/             import-time and time-to-first-image benchmarks
spikes/            throwaway experiments that informed the design
docs/              backlog.md (the issue list), design notes
examples/
```

## Roadmap

The milestones and issues are in [docs/backlog.md](docs/backlog.md):
M0 repo and copy, M1 imports without napari, M2 first image on screen,
M3 fast and small, M4 full feature set, M5 sync and share.

## Development

```
pip install -e .[dev,pyqt6]
QT_QPA_PLATFORM=offscreen pytest tests
```

The napari checkout used for vendoring is separate from this repo:

```
git clone https://github.com/napari/napari ../napari
git -C ../napari checkout <pin from tools/vendor.toml>
python tools/vendor.py --napari ../napari --report
```
