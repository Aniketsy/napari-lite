# napari-lite: own code
"""Combine ``bench_imports.py`` and ``install_size.py`` JSON files into a
Markdown table (napari-lite next to napari, per OS).

    python bench/make_table.py results/*.json
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

MEASURES = [
    ('import', 'import package'),
    ('import_components', 'import components'),
    ('first_image', 'first image (ViewerModel + add_image)'),
    ('viewer_no_show', 'Viewer(show=False)'),
]
SIZES = [
    ('size_mb', 'installed size (MB)'),
    ('package_count', 'packages installed'),
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


def fmt_seconds(value: float | None) -> str:
    return f'{value:.2f} s' if value is not None else 'n/a'


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 1
    table = load(argv)
    for os_name in sorted(table):
        packages = table[os_name]
        names = [p for p in ('napari_lite', 'napari') if p in packages]
        names += sorted(set(packages) - set(names))
        print(f'### {os_name}\n')
        print('| | ' + ' | '.join(names) + ' |')
        print('|---|' + '---|' * len(names))
        for key, label in MEASURES:
            cells = [
                fmt_seconds(packages[n].get('seconds', {}).get(key))
                for n in names
            ]
            print(f'| {label} | ' + ' | '.join(cells) + ' |')
        for key, label in SIZES:
            if any(key in packages[n] for n in names):
                cells = [str(packages[n].get(key, 'n/a')) for n in names]
                print(f'| {label} | ' + ' | '.join(cells) + ' |')
        pythons = {packages[n].get('python') for n in names}
        print(f'\nPython {", ".join(sorted(p for p in pythons if p))}\n')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
