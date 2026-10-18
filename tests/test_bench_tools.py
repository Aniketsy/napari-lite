# napari-lite: own code
"""The benchmark tooling: every snippet of bench/bench_imports.py compiles,
the table script renders the new rows, and tools/readme_bench.py builds
the README block and replaces only what lies between its markers.  No
interpreter is started and no window shown here."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _load(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope='module')
def bench_imports():
    return _load(ROOT / 'bench' / 'bench_imports.py')


@pytest.fixture(scope='module')
def make_table():
    return _load(ROOT / 'bench' / 'make_table.py')


@pytest.fixture(scope='module')
def readme_bench():
    module = _load(ROOT / 'tools' / 'readme_bench.py')
    sys.path[:] = [p for p in sys.path if not p.endswith('bench')]
    return module


def _record(package: str, scale: float, **extra) -> dict:
    """A bench_imports + install_size record; napari's numbers are the
    napari-lite ones times ``scale``."""
    seconds = {
        'import': 0.01,
        'import_components': 0.5,
        'first_image': 1.0,
        'viewer_no_show': 2.0,
        'viewer_shown': 3.0,
        'first_frame': 3.2,
        'first_image_layer': 0.4,
        'first_labels_layer': 0.3,
        'slice_step': 0.012,
        'paint_stroke': 0.008,
    }
    record = {
        'package': package,
        'python': '3.13.7',
        'platform': 'Linux-6.17.0-azure-x86_64-with-glibc2.39',
        'repeat': 5,
        'seconds': {k: v * scale for k, v in seconds.items()},
        'median_seconds': {k: v * scale * 1.1 for k, v in seconds.items()},
        'first_seconds': {k: v * scale * 2 for k, v in seconds.items()},
        'rss_mb': {'import': 14 * scale, 'viewer_shown': 200 * scale},
        'modules': {'import': 77, 'first_image': 631},
        'size_mb': 370 * scale,
        'package_count': int(31 * scale),
        'direct_dependencies': int(14 * scale),
    }
    record.update(extra)
    return record


def test_every_snippet_compiles(bench_imports) -> None:
    for package in ('napari_lite', 'napari'):
        for name, template in bench_imports.MEASUREMENTS.items():
            code = template.format(pkg=package)
            compile(code, name, 'exec')
            assert '{' not in code or name in ('first_frame',), name
            assert '@' not in code, name
    assert 'first_frame' in bench_imports.MEASUREMENTS
    assert 'slice_step' in bench_imports.MEASUREMENTS
    # the first image layer is added to a viewer without one
    code = bench_imports.MEASUREMENTS['first_image_layer']
    assert code.count('add_image') == 1


def test_summarize_keeps_best_median_and_first(bench_imports) -> None:
    runs = [
        {'seconds': 2.0, 'rss_mb': 10, 'modules': 5, 'cpu_seconds': 0.02},
        {'seconds': 1.0, 'rss_mb': 11, 'modules': 5, 'cpu_seconds': 0.03},
        {'seconds': 1.5, 'rss_mb': 12, 'modules': 5, 'cpu_seconds': 0.01},
    ]
    best = bench_imports.summarize(runs)
    assert best['seconds'] == 1.0
    assert best['rss_mb'] == 11  # the best run's memory
    assert best['median_seconds'] == 1.5
    assert best['first_seconds'] == 2.0
    assert best['runs'] == [2.0, 1.0, 1.5]
    assert best['cpu_seconds'] == 0.01
    assert bench_imports.summarize([]) is None


def test_table_rows(make_table) -> None:
    packages = {
        'napari_lite': _record('napari_lite', 1.0),
        'napari': _record('napari', 2.0),
    }
    names = ['napari_lite', 'napari']
    lines = make_table.rows(packages, names)
    labels = [line.split('|')[1].strip() for line in lines]
    assert 'first frame: a window with one image, to its first paint' in labels
    assert 'first Image layer in a shown empty viewer, drawn' in labels
    assert 'slice step through a 32 x 512 x 512 image, per step' in labels
    # rows whose measurement is missing everywhere are left out
    assert not any('Points' in label for label in labels)
    by_label = dict(zip(labels, lines, strict=True))
    assert (
        '| 12.0 ms | 24.0 ms | 2.0x |'
        in by_label['slice step through a 32 x 512 x 512 image, per step']
    )
    assert (
        '| 3.20 s | 6.40 s | 2.0x |'
        in by_label['first frame: a window with one image, to its first paint']
    )
    with_median = make_table.rows(packages, names, median=True)
    assert '| 3.20 s (3.52 s) | 6.40 s (7.04 s) | 2.0x |' in '\n'.join(
        with_median
    )


def test_readme_block(readme_bench) -> None:
    lite, nap = _record('napari_lite', 1.0), _record('napari', 2.0)
    table = readme_bench.table(lite, nap)
    assert table[0] == '| | napari-lite | napari | |'
    body = table[2:]
    assert len(body) == 9
    # a row whose measurement the run lacks is left out
    without = dict(
        nap,
        seconds={k: v for k, v in nap['seconds'].items() if k != 'slice_step'},
    )
    assert len(readme_bench.table(lite, without)) == 10
    assert '| `import` the package | 0.01 s | 0.02 s | 2.0x faster |' in body
    assert (
        '| slice step through a 3D image, per step | 12.0 ms | 24.0 ms |'
        ' 2.0x faster |' in body
    )
    assert '| installed size | 370 MB | 740 MB | 50% less |' in body
    assert '| packages installed | 31 | 62 | 50% fewer |' in body
    # honest wording when napari-lite is not ahead
    assert readme_bench._advantage('seconds', 1.0, 1.02) == 'same'
    assert readme_bench._advantage('seconds', 2.0, 1.0) == '2.0x slower'
    assert readme_bench._advantage('count', 40, 30) == '33% more'

    run = {
        'databaseId': 123,
        'headSha': 'abcdef0123456789',
        'url': 'https://github.com/x/y/actions/runs/123',
    }
    text = readme_bench.caption(lite, {**nap, 'version': '0.9.2'}, run)
    assert 'commit `abcdef0`' in text
    assert 'napari 0.9.2 from PyPI' in text
    assert '[Run 123](https://github.com/x/y/actions/runs/123).' in text
    assert 'best of 5 fresh interpreters' in text
    offline = readme_bench.caption(lite, nap, None)
    assert 'Run' not in offline and 'napari from PyPI' in offline


def test_readme_block_replaces_only_the_marked_part(readme_bench) -> None:
    start, end = readme_bench.START, readme_bench.END
    readme = f'# Title\n\nintro\n\n{start}\nold caption\n\n| old |\n{end}\n\nafter\n'
    new = readme_bench.replace_block(readme, f'{start}\nnew\n{end}')
    assert new == f'# Title\n\nintro\n\n{start}\nnew\n{end}\n\nafter\n'
    with pytest.raises(SystemExit, match='no'):
        readme_bench.replace_block('no markers here', 'x')
    # the real README carries the markers, once each
    text = (ROOT / 'README.md').read_text(encoding='utf-8')
    assert text.count(start) == 1 and text.count(end) == 1
