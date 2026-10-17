# napari-lite: own code
"""Import-time and time-to-first-image benchmarks.

    python bench/bench_imports.py                      # napari_lite
    python bench/bench_imports.py --package napari    # same numbers for napari
    python bench/bench_imports.py --json out.json --repeat 5

Every measurement runs in a fresh interpreter and the best of ``--repeat``
runs is kept, so the numbers are cold-start costs, not cached ones.
``first_image`` is the whole cost of ``ViewerModel().add_image(...)`` in a
fresh process, including the imports it triggers.  ``viewer_no_show``
constructs ``Viewer(show=False)`` and is skipped if the package has no
``Viewer`` yet.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import textwrap
import time

MEASUREMENTS = {
    'import': 'import {pkg}',
    'import_components': 'import {pkg}.components',
    'import_layers': 'import {pkg}.layers',
    'first_image': textwrap.dedent(
        """
        import numpy as np
        from {pkg}.components import ViewerModel
        ViewerModel().add_image(np.zeros((64, 64), dtype=np.uint8))
        """
    ),
    'viewer_no_show': textwrap.dedent(
        """
        import {pkg}
        v = {pkg}.Viewer(show=False)
        v.close()
        """
    ),
}

RUNNER = textwrap.dedent(
    """
    import sys, time
    code = sys.argv[1]
    start = time.perf_counter()
    exec(compile(code, '<bench>', 'exec'), {})
    print(time.perf_counter() - start)
    """
)


def run_once(code: str) -> float | None:
    # the Qt "offscreen" platform has no OpenGL on Windows and macOS; the
    # native platform is used there (no window is shown by these snippets)
    env = dict(os.environ)
    if sys.platform.startswith('linux') and not env.get('DISPLAY'):
        env.setdefault('QT_QPA_PLATFORM', 'offscreen')
    proc = subprocess.run(
        [sys.executable, '-c', RUNNER, code],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if proc.returncode != 0:
        last = proc.stderr.strip().splitlines()[-1:] or ['(no output)']
        print(f'  failed: {last[0]}', file=sys.stderr)
        return None
    return float(proc.stdout.strip().splitlines()[-1])


def bench(package: str, repeat: int) -> dict[str, float | None]:
    results: dict[str, float | None] = {}
    for name, template in MEASUREMENTS.items():
        code = template.format(pkg=package)
        times = [t for t in (run_once(code) for _ in range(repeat)) if t]
        results[name] = min(times) if times else None
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--package', default='napari_lite')
    parser.add_argument('--repeat', type=int, default=3)
    parser.add_argument('--json', metavar='FILE', help='write results here')
    args = parser.parse_args(argv)

    results = bench(args.package, args.repeat)
    record = {
        'package': args.package,
        'python': platform.python_version(),
        'platform': platform.platform(),
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'repeat': args.repeat,
        'seconds': results,
    }
    width = max(len(k) for k in results)
    print(f'{args.package} on Python {record["python"]} ({sys.platform})')
    for name, seconds in results.items():
        shown = f'{seconds:7.3f} s' if seconds is not None else '   failed'
        print(f'  {name:<{width}}  {shown}')
    if args.json:
        with open(args.json, 'w', encoding='utf-8') as fh:
            json.dump(record, fh, indent=2)
        print(f'wrote {args.json}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
