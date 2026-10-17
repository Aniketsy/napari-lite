# napari-lite: own code
"""Installed size and package count of the current environment.

    python bench/install_size.py                 # print
    python bench/install_size.py --json out.json # also write a record that
                                                 # bench/make_table.py merges

The size is the sum of the files of every installed distribution (from
their RECORD files), so it is what ``pip install`` put on disk, not the
whole environment.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from importlib.metadata import distributions


def measure() -> tuple[float, int, str]:
    total = 0
    count = 0
    package = 'napari_lite'
    for dist in distributions():
        count += 1
        if dist.metadata['Name'] and dist.metadata['Name'].lower() == 'napari':
            package = 'napari'
        for file in dist.files or ():
            try:
                total += file.locate().stat().st_size
            except OSError:
                continue
    return total / 1e6, count, package


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--json', metavar='FILE')
    parser.add_argument(
        '--package',
        help="which package this environment is for (default: 'napari' if "
        "napari is installed, else 'napari_lite')",
    )
    args = parser.parse_args(argv)
    size_mb, count, detected = measure()
    record = {
        'package': args.package or detected,
        'python': platform.python_version(),
        'platform': platform.platform(),
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'size_mb': round(size_mb),
        'package_count': count,
    }
    print(f'{record["package"]}: {size_mb:.0f} MB in {count} packages')
    if args.json:
        with open(args.json, 'w', encoding='utf-8') as fh:
            json.dump(record, fh, indent=2)
        print(f'wrote {args.json}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
