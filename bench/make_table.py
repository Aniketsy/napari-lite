# napari-lite: own code
"""Combine ``bench_imports.py`` and ``install_size.py`` JSON files into a
Markdown table (napari-lite next to napari, per OS).

    python bench/make_table.py results/*.json
    python bench/make_table.py --median results/*.json   # best (median)
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

# (key, label); keys of the ``seconds`` dict written by bench_imports.py
TIMES = [
    ('import', 'import the package'),
    ('import_components', 'import the components (viewer model)'),
    ('first_image', 'first image: ViewerModel + add_image'),
    (
        'model_all_layers',
        'the model alone: ViewerModel + one layer of every kind',
    ),
    ('viewer_no_show', 'Viewer(show=False), closed'),
    ('viewer_shown', 'Viewer shown, one image painted, closed'),
    (
        'first_frame',
        'first frame: a window with one image, to its first paint',
    ),
    ('first_image_layer', 'first Image layer in a shown empty viewer, drawn'),
    ('first_labels_layer', 'first Labels layer on top of an image, drawn'),
    (
        'first_points_layer',
        'first Points layer (1,000 points) on top of an image, drawn',
    ),
    (
        'first_shapes_layer',
        'first Shapes layer (50 rectangles) on top of an image, drawn',
    ),
]
# per-step measurements, seconds per step, shown in milliseconds
PER_STEP = [
    ('slice_step', 'slice step through a 32 x 512 x 512 image, per step'),
    ('paint_stroke', 'Labels brush stroke, per point'),
]
MEMORY = [
    ('import', 'memory after importing the package'),
    ('first_image', 'memory after the first image'),
    ('viewer_shown', 'memory with a viewer window shown'),
]
MODULES = [
    ('import', 'modules loaded by importing the package'),
    ('first_image', 'modules loaded at the first image'),
    ('model_all_layers', 'modules loaded by the model with every layer kind'),
]
# keys written by install_size.py
INSTALL = [
    ('size_mb', 'installed size, MB (all packages)'),
    ('package_count', 'packages installed'),
    ('direct_dependencies', 'direct dependencies'),
    ('package_modules', 'Python modules in the package'),
    ('package_lines', 'lines of Python in the package'),
]


def _os_name(platform: str) -> str:
    low = platform.lower()
    if low.startswith('windows'):
        return 'Windows'
    if low.startswith('macos') or 'darwin' in low:
        return 'macOS'
    return 'Linux'


def load(paths: list[str]) -> dict[str, dict[str, dict]]:
    """{os: {package: merged record}}"""
    table: dict[str, dict[str, dict]] = defaultdict(lambda: defaultdict(dict))
    for path in paths:
        record = json.loads(Path(path).read_text(encoding='utf-8'))
        os_name = _os_name(record.get('platform', ''))
        table[os_name][record['package']].update(record)
    return table


def _seconds(value: float | None) -> str:
    return f'{value:.2f} s' if value is not None else 'n/a'


def _ms(value: float | None) -> str:
    return f'{value * 1000:.1f} ms' if value is not None else 'n/a'


def _mb(value: float | None) -> str:
    return f'{value:.0f} MB' if value is not None else 'n/a'


def _int(value: int | None) -> str:
    return f'{value:,}' if value is not None else 'n/a'


def _ratio(lite: float | None, nap: float | None) -> str:
    if not lite or not nap:
        return ''
    return f'{nap / lite:.1f}x' if nap >= lite else f'{lite / nap:.1f}x more'


def rows(
    packages: dict[str, dict], names: list[str], median: bool = False
) -> list[str]:
    """The table rows for one OS; rows whose values are all missing are
    left out, except the startup times, which say n/a."""
    out = []
    lite, nap = packages.get('napari_lite', {}), packages.get('napari', {})

    def line(label, fmt, values, lite_v, nap_v, medians=None):
        cells = [fmt(v) for v in values]
        if median and medians:
            cells = [
                f'{c} ({fmt(m)})' if m is not None else c
                for c, m in zip(cells, medians, strict=True)
            ]
        out.append(
            f'| {label} | {" | ".join(cells)} | {_ratio(lite_v, nap_v)} |'
        )

    def timed(entries, fmt, always):
        for key, label in entries:
            values = [packages[n].get('seconds', {}).get(key) for n in names]
            if not always and all(v is None for v in values):
                continue
            medians = [
                packages[n].get('median_seconds', {}).get(key) for n in names
            ]
            line(
                label,
                fmt,
                values,
                lite.get('seconds', {}).get(key),
                nap.get('seconds', {}).get(key),
                medians,
            )

    timed(TIMES[:5], _seconds, always=True)
    timed(TIMES[5:], _seconds, always=False)
    timed(PER_STEP, _ms, always=False)
    for key, label in MEMORY:
        values = [packages[n].get('rss_mb', {}).get(key) for n in names]
        if any(v is not None for v in values):
            line(
                label,
                _mb,
                values,
                lite.get('rss_mb', {}).get(key),
                nap.get('rss_mb', {}).get(key),
            )
    for key, label in MODULES:
        values = [packages[n].get('modules', {}).get(key) for n in names]
        if any(v is not None for v in values):
            line(
                label,
                _int,
                values,
                lite.get('modules', {}).get(key),
                nap.get('modules', {}).get(key),
            )
    for key, label in INSTALL:
        values = [packages[n].get(key) for n in names]
        if any(v is not None for v in values):
            fmt = _mb if key == 'size_mb' else _int
            line(label, fmt, values, lite.get(key), nap.get(key))
    return out


def main(argv: list[str]) -> int:
    median = '--median' in argv
    paths = [a for a in argv if a != '--median']
    if not paths:
        print(__doc__)
        return 1
    table = load(paths)
    for os_name in sorted(table):
        packages = table[os_name]
        names = [p for p in ('napari_lite', 'napari') if p in packages]
        names += sorted(set(packages) - set(names))
        print(f'### {os_name}\n')
        print('| | ' + ' | '.join(names) + ' | napari-lite advantage |')
        print('|---|' + '---|' * (len(names) + 1))
        print('\n'.join(rows(packages, names, median)))
        pythons = {packages[n].get('python') for n in names}
        versions = ', '.join(
            f'{n} {packages[n]["version"]}'
            for n in names
            if packages[n].get('version')
        )
        repeats = {packages[n].get('repeat') for n in names}
        note = 'best' + (' (median)' if median else '')
        print(
            f'\nPython {", ".join(sorted(p for p in pythons if p))}; {versions};'
            f' {note} of {", ".join(str(r) for r in sorted(repeats) if r)}'
            ' fresh interpreters; per-step rows are the median wall time per step,'
            ' vsync off, 640 x 480 canvas.\n'
        )
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
