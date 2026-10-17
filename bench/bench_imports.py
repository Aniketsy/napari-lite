# napari-lite: own code
"""Startup benchmarks: import time, time to first image, memory, modules.

    python bench/bench_imports.py                      # napari_lite
    python bench/bench_imports.py --package napari     # same numbers for napari
    python bench/bench_imports.py --json out.json --repeat 5

Every measurement runs in a fresh interpreter; the best of ``--repeat``
runs is kept, so the numbers are cold-start costs.  Each run also reports
the resident memory and the number of imported modules at the end of the
measured code.

Measurements
------------
import            ``import <package>``
import_components ``import <package>.components``
import_layers     ``import <package>.layers``
first_image       ``ViewerModel().add_image(...)`` in a fresh process (the
                  imports it triggers included)
viewer_no_show    ``Viewer(show=False)`` and close it
viewer_shown      ``Viewer()`` with its window shown and painted once, then
                  closed (skipped if the package has no ``Viewer`` yet)
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
    'viewer_shown': textwrap.dedent(
        """
        import numpy as np
        import {pkg}
        from qtpy.QtWidgets import QApplication
        v = {pkg}.Viewer(show=True)
        v.add_image(np.zeros((256, 256), dtype=np.uint8))
        app = QApplication.instance()
        for _ in range(20):          # let the window show and paint once
            app.processEvents()
        v.screenshot(canvas_only=True)
        v.close()
        """
    ),
}

RUNNER = textwrap.dedent(
    """
    import json, sys, time
    code = sys.argv[1]
    start = time.perf_counter()
    exec(compile(code, '<bench>', 'exec'), {})
    elapsed = time.perf_counter() - start

    def rss_mb():
        if sys.platform == 'win32':
            import ctypes, ctypes.wintypes as wt
            class C(ctypes.Structure):
                _fields_ = [('cb', wt.DWORD), ('PageFaultCount', wt.DWORD),
                            ('PeakWorkingSetSize', ctypes.c_size_t),
                            ('WorkingSetSize', ctypes.c_size_t),
                            ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
                            ('QuotaPagedPoolUsage', ctypes.c_size_t),
                            ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                            ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                            ('PagefileUsage', ctypes.c_size_t),
                            ('PeakPagefileUsage', ctypes.c_size_t)]
            info = ctypes.windll.psapi.GetProcessMemoryInfo
            info.argtypes = [wt.HANDLE, ctypes.POINTER(C), wt.DWORD]
            info.restype = wt.BOOL
            ctypes.windll.kernel32.GetCurrentProcess.restype = wt.HANDLE
            c = C(); c.cb = ctypes.sizeof(C)
            info(ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(c), c.cb)
            return c.WorkingSetSize / 1e6
        import resource
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return peak / 1e6 if sys.platform == 'darwin' else peak / 1e3

    print(json.dumps({'seconds': elapsed, 'rss_mb': rss_mb(),
                      'modules': len(sys.modules)}))
    """
)


def run_once(code: str) -> dict | None:
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
    return json.loads(proc.stdout.strip().splitlines()[-1])


def bench(package: str, repeat: int) -> dict[str, dict | None]:
    results: dict[str, dict | None] = {}
    for name, template in MEASUREMENTS.items():
        code = template.format(pkg=package)
        runs = [r for r in (run_once(code) for _ in range(repeat)) if r]
        results[name] = min(runs, key=lambda r: r['seconds']) if runs else None
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
        'seconds': {k: (v or {}).get('seconds') for k, v in results.items()},
        'rss_mb': {k: (v or {}).get('rss_mb') for k, v in results.items()},
        'modules': {k: (v or {}).get('modules') for k, v in results.items()},
    }
    width = max(len(k) for k in results)
    print(f'{args.package} on Python {record["python"]} ({sys.platform})')
    for name, run in results.items():
        if run is None:
            print(f'  {name:<{width}}     failed')
            continue
        print(
            f'  {name:<{width}}  {run["seconds"]:7.3f} s'
            f'  {run["rss_mb"]:6.0f} MB  {run["modules"]:5d} modules'
        )
    if args.json:
        with open(args.json, 'w', encoding='utf-8') as fh:
            json.dump(record, fh, indent=2)
        print(f'wrote {args.json}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
