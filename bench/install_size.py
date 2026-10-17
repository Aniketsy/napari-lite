# napari-lite: own code
"""Installed size, package count, direct dependencies and code size of the
current environment's napari-lite (or napari).

    python bench/install_size.py                 # print
    python bench/install_size.py --json out.json # also write a record that
                                                 # bench/make_table.py merges

The installed size is the sum of the files of every installed distribution
(from their RECORD files), so it is what ``pip install`` put on disk, not
the whole environment.  The code size counts the Python modules and lines
of the package itself (tests and vendored code excluded).
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from importlib.metadata import distribution, distributions
from pathlib import Path

SKIP_DIRS = {'_tests', '_vendor', 'vendored', 'benchmarks', '__pycache__'}


def installed() -> tuple[float, int]:
    """(size in MB, number of distributions) of everything installed."""
    total = 0
    count = 0
    for dist in distributions():
        count += 1
        for file in dist.files or ():
            try:
                total += file.locate().stat().st_size
            except OSError:
                continue
    return total / 1e6, count


def direct_dependencies(dist_name: str) -> int:
    """Requirements of the distribution without an ``extra ==`` marker."""
    dist = distribution(dist_name)
    count = 0
    for req in dist.requires or ():
        if 'extra ==' in req or 'extra==' in req:
            continue
        count += 1
    return count


def code_size(package: str) -> tuple[int, int]:
    """(modules, lines) of the importable package, tests excluded."""
    module = __import__(package)
    root = Path(module.__file__).resolve().parent
    files = [
        p
        for p in root.rglob('*.py')
        if not (set(p.relative_to(root).parts) & SKIP_DIRS)
    ]
    lines = 0
    for path in files:
        with path.open(encoding='utf-8', errors='replace') as fh:
            lines += sum(1 for _ in fh)
    return len(files), lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--json', metavar='FILE')
    parser.add_argument(
        '--package',
        help="'napari_lite' (default) or 'napari'; detected if napari is "
        'installed and napari_lite is not',
    )
    args = parser.parse_args(argv)
    package = args.package
    if package is None:
        names = {(d.metadata['Name'] or '').lower() for d in distributions()}
        package = 'napari_lite' if 'napari-lite' in names else 'napari'
    dist_name = 'napari-lite' if package == 'napari_lite' else 'napari'

    size_mb, count = installed()
    modules, lines = code_size(package)
    record = {
        'package': package,
        'version': distribution(dist_name).version,
        'python': platform.python_version(),
        'platform': platform.platform(),
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'size_mb': round(size_mb),
        'package_count': count,
        'direct_dependencies': direct_dependencies(dist_name),
        'package_modules': modules,
        'package_lines': lines,
    }
    print(
        f'{package} {record["version"]}: {size_mb:.0f} MB in {count} '
        f'packages, {record["direct_dependencies"]} direct dependencies, '
        f'{modules} modules / {lines:,} lines in the package'
    )
    if args.json:
        with open(args.json, 'w', encoding='utf-8') as fh:
            json.dump(record, fh, indent=2)
        print(f'wrote {args.json}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
