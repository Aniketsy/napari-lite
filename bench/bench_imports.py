# napari-lite: own code
"""Startup and interaction benchmarks: import time, time to first image and
first frame, first layer of each kind, slice stepping, painting, memory.

    python bench/bench_imports.py                      # napari_lite
    python bench/bench_imports.py --package napari     # same numbers for napari
    python bench/bench_imports.py --json out.json --repeat 5
    python bench/bench_imports.py --only first_frame,slice_step

Every measurement runs in a fresh interpreter ``--repeat`` times.  The
best run is the number reported (a cold-start cost with the least noise);
the median and the first run are kept too, so the spread is visible and
so is the first run, the one that found the OS caches as they were (only a
reboot gives a truly cold one).  Each run also reports the resident memory
and the number of imported modules at the end of the measured code.

Measurements
------------
import             ``import <package>``
import_components  ``import <package>.components``
import_layers      ``import <package>.layers``
first_image        ``ViewerModel().add_image(...)`` in a fresh process (the
                   imports it triggers included)
viewer_no_show     ``Viewer(show=False)`` and close it
viewer_shown       ``Viewer()`` with its window shown and painted once, then
                   closed
first_frame        from the start of the process to the first paint event
                   of a viewer window that holds one 512 x 512 image
first_image_layer  a viewer is shown, empty; the time from ``add_image`` to
                   the canvas draw that shows the image: the first layer
                   of all, its imports, widgets and shaders included
first_labels_layer a viewer shows an image; the time from ``add_labels``
first_points_layer (``add_points``, ``add_shapes``) to the canvas draw that
first_shapes_layer shows the new layer: the first layer of that kind on
                   top of an image, so without the costs of the first
                   layer of all
slice_step         seconds per slice step through a 32 x 512 x 512 float32
                   image: the median over 60 steps of the wall time from
                   the step to the canvas drawn and the window idle again
                   (``cpu_seconds``, the mean CPU time per step, is kept
                   next to it; on Windows that clock ticks every 15.6 ms)
paint_stroke       the same per point of a 60-point brush stroke on a
                   512 x 512 Labels layer

The window snippets after ``first_frame`` share one setup, so that two
packages and two machines compare: vsync off (the swap interval of the
default surface format), the window resized until the canvas is
640 x 480, and ``viewer.mouse_over_canvas`` set, as it is while someone
works (it decides whether the brush circle is drawn and the status
updated; left to the real pointer it differs from run to run).

The window measurements need a display: on Linux without one, Qt's
offscreen platform is used (no OpenGL there, so they fail and are reported
as such; CI gets a virtual display).
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import subprocess
import sys
import textwrap
import time

TIMEOUT = 300  # seconds for one run of one measurement

# Shared by the window snippets: a shown viewer with one image, a ``drawn``
# list that records every canvas draw, and two waits on it.
_SHOWN_VIEWER = """
import time
import numpy as np
import {pkg}
from qtpy.QtGui import QSurfaceFormat
from qtpy.QtWidgets import QApplication

_format = QSurfaceFormat.defaultFormat()
_format.setSwapInterval(0)  # no vsync: wall time per step is work, not waiting
QSurfaceFormat.setDefaultFormat(_format)
app = QApplication.instance() or QApplication([])
v = {pkg}.Viewer()
v.add_image(np.zeros((512, 512), dtype=np.uint8))
drawn = []
scene_canvas = v.window._qt_viewer.canvas._scene_canvas
scene_canvas.events.draw.connect(lambda e: drawn.append(time.perf_counter()))


def wait_draw(timeout=30.0):
    # process events until the canvas has drawn once more
    n = len(drawn)
    deadline = time.perf_counter() + timeout
    while len(drawn) == n:
        if time.perf_counter() > deadline:
            raise SystemExit('the canvas did not draw within %s s' % timeout)
        app.processEvents()


def settle(quiet=0.3):
    # process events until the canvas has been still for ``quiet`` seconds
    last = time.perf_counter()
    n = len(drawn)
    while time.perf_counter() - last < quiet:
        app.processEvents()
        if len(drawn) != n:
            n, last = len(drawn), time.perf_counter()


def drain():
    # process events until two calls in a row find none
    quiet = 0
    while quiet < 2:
        quiet = quiet + 1 if not app.processEvents() else 0


settle()
_native, _window = v.window._qt_viewer.canvas.native, v.window._qt_window
for _ in range(3):  # the same canvas everywhere: 640 x 480
    _dw, _dh = 640 - _native.width(), 480 - _native.height()
    if _dw == 0 and _dh == 0:
        break
    _window.resize(_window.width() + _dw, _window.height() + _dh)
    settle(0.2)
v.mouse_over_canvas = True
settle()
"""

_EMPTY_VIEWER = _SHOWN_VIEWER.replace(
    'v.add_image(np.zeros((512, 512), dtype=np.uint8))' + chr(10), ''
)

_FIRST_LAYER = (
    _SHOWN_VIEWER
    + """
t = time.perf_counter()
@ADD@
wait_draw()
_elapsed = drawn[-1] - t
v.close()
"""
)

_PER_STEP = (
    _SHOWN_VIEWER
    + """
@SETUP@
settle()
for i in range(6):          # warm up: shaders, first slices, first stamps
    step(i)
    wait_draw()
    drain()
settle()
n = 60
walls = []
cpu0 = time.process_time()
for i in range(n):
    t = time.perf_counter()
    step(i + 6)
    wait_draw()
    drain()
    walls.append(time.perf_counter() - t)
walls.sort()
_elapsed = walls[n // 2]
_extra = dict(
    cpu_seconds=(time.process_time() - cpu0) / n, mean_seconds=sum(walls) / n
)
v.close()
"""
)

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
    # the model alone: one layer of every kind, no window, no canvas
    'model_all_layers': textwrap.dedent(
        """
        import numpy as np
        from {pkg}.components import ViewerModel
        v = ViewerModel()
        v.add_image(np.zeros((4, 64, 64), dtype=np.uint8))
        v.add_labels(np.zeros((64, 64), dtype=np.uint8))
        v.add_points(np.zeros((3, 2)), face_color='cyan')
        v.add_shapes(
            [np.array([[1, 1], [1, 5], [5, 5], [5, 1]])], edge_color='yellow'
        )
        v.add_surface((np.zeros((3, 2)), np.array([[0, 1, 2]]), np.zeros(3)))
        v.add_tracks(np.array([[0, 0, 1.0, 1.0], [0, 1, 2.0, 2.0]]))
        v.add_vectors(np.zeros((2, 2, 2)))
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
    'first_frame': textwrap.dedent(
        """
        import time
        import numpy as np
        import {pkg}
        from qtpy.QtCore import QEvent, QObject
        from qtpy.QtWidgets import QApplication

        painted = []

        class FirstPaint(QObject):
            def eventFilter(self, obj, event):
                if event.type() == QEvent.Type.Paint and not painted:
                    painted.append(time.perf_counter())
                return False

        v = {pkg}.Viewer(show=False)
        v.add_image(np.zeros((512, 512), dtype=np.uint8))
        watch = FirstPaint()
        v.window._qt_window.installEventFilter(watch)
        v.show()
        app = QApplication.instance()
        deadline = time.perf_counter() + 30
        while not painted:
            if time.perf_counter() > deadline:
                raise SystemExit('the window did not paint within 30 s')
            app.processEvents()
        _elapsed = painted[0] - _start
        v.close()
        """
    ),
    'first_image_layer': _EMPTY_VIEWER
    + _FIRST_LAYER[len(_SHOWN_VIEWER) :].replace(
        '@ADD@', 'v.add_image(np.zeros((512, 512), dtype=np.uint8))'
    ),
    'first_labels_layer': _FIRST_LAYER.replace(
        '@ADD@', 'v.add_labels(np.zeros((512, 512), dtype=np.uint8))'
    ),
    'first_points_layer': _FIRST_LAYER.replace(
        '@ADD@',
        'v.add_points(np.random.default_rng(0).random((1000, 2)) * 512)',
    ),
    'first_shapes_layer': _FIRST_LAYER.replace(
        '@ADD@',
        textwrap.dedent(
            """
            corners = np.random.default_rng(0).random((50, 1, 2)) * 480
            boxes = corners + np.array([[0, 0], [0, 30], [30, 30], [30, 0]])
            v.add_shapes(list(boxes), shape_type='rectangle')
            """
        ).strip(),
    ),
    'slice_step': _PER_STEP.replace(
        '@SETUP@',
        textwrap.dedent(
            """
            stack = v.add_image(
                np.random.default_rng(0).random((32, 512, 512), dtype=np.float32)
            )
            v.layers[0].visible = False

            def step(i):
                # 7 is coprime with 32: every step lands on a new slice
                v.dims.set_current_step(0, (7 * i + 3) % 32)
            """
        ).strip(),
    ),
    'paint_stroke': _PER_STEP.replace(
        '@SETUP@',
        textwrap.dedent(
            """
            labels = v.add_labels(np.zeros((512, 512), dtype=np.uint8))
            labels.mode = 'paint'
            labels.brush_size = 20
            labels.selected_label = 2

            def step(i):
                # two rows of 36 stamps 12 px apart: never the same pixels
                labels.paint((200 + 80 * (i // 36), 40 + 12 * (i % 36)), 2)
            """
        ).strip(),
    ),
}

RUNNER = textwrap.dedent(
    """
    import json, sys, time
    code = sys.argv[1]
    start = time.perf_counter()
    scope = {'_start': start, '_elapsed': None, '_extra': {}}
    exec(compile(code, '<bench>', 'exec'), scope)
    elapsed = scope['_elapsed']
    if elapsed is None:
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

    result = {'seconds': elapsed, 'rss_mb': rss_mb(), 'modules': len(sys.modules)}
    result.update(scope['_extra'])
    print(json.dumps(result))
    """
)


def run_once(code: str) -> dict | None:
    # the Qt "offscreen" platform has no OpenGL on Windows and macOS; the
    # native platform is used there
    env = dict(os.environ)
    if sys.platform.startswith('linux') and not env.get('DISPLAY'):
        env.setdefault('QT_QPA_PLATFORM', 'offscreen')
    try:
        proc = subprocess.run(
            [sys.executable, '-c', RUNNER, code],
            capture_output=True,
            text=True,
            env=env,
            check=False,
            timeout=TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        print(f'  failed: no result within {TIMEOUT} s', file=sys.stderr)
        return None
    if proc.returncode != 0:
        last = proc.stderr.strip().splitlines()[-1:] or ['(no output)']
        print(f'  failed: {last[0]}', file=sys.stderr)
        return None
    return json.loads(proc.stdout.strip().splitlines()[-1])


def summarize(runs: list[dict]) -> dict | None:
    """The best run, with the median and first-run seconds and all the
    runs' seconds next to it."""
    if not runs:
        return None
    best = dict(min(runs, key=lambda r: r['seconds']))
    seconds = [r['seconds'] for r in runs]
    best['median_seconds'] = statistics.median(seconds)
    best['first_seconds'] = seconds[0]
    best['runs'] = seconds
    for key in ('cpu_seconds', 'mean_seconds'):
        if key in best:
            best[key] = min(r[key] for r in runs)
    return best


def bench(
    package: str, repeat: int, only: list[str] | None = None
) -> dict[str, dict | None]:
    results: dict[str, dict | None] = {}
    for name, template in MEASUREMENTS.items():
        if only and name not in only:
            continue
        code = template.format(pkg=package)
        runs = [r for r in (run_once(code) for _ in range(repeat)) if r]
        results[name] = summarize(runs)
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--package', default='napari_lite')
    parser.add_argument('--repeat', type=int, default=3)
    parser.add_argument('--json', metavar='FILE', help='write results here')
    parser.add_argument(
        '--only',
        metavar='NAMES',
        help='comma-separated measurement names to run (default: all)',
    )
    args = parser.parse_args(argv)
    only = args.only.split(',') if args.only else None
    unknown = set(only or ()) - set(MEASUREMENTS)
    if unknown:
        parser.error(f'unknown measurements: {", ".join(sorted(unknown))}')

    results = bench(args.package, args.repeat, only)

    def column(key: str) -> dict:
        return {k: (v or {}).get(key) for k, v in results.items()}

    record = {
        'package': args.package,
        'python': platform.python_version(),
        'platform': platform.platform(),
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'repeat': args.repeat,
        'seconds': column('seconds'),
        'median_seconds': column('median_seconds'),
        'first_seconds': column('first_seconds'),
        'cpu_seconds': {
            k: v['cpu_seconds']
            for k, v in results.items()
            if v and 'cpu_seconds' in v
        },
        'rss_mb': column('rss_mb'),
        'modules': column('modules'),
    }
    width = max(len(k) for k in results)
    print(f'{args.package} on Python {record["python"]} ({sys.platform})')
    print(f'  {"":<{width}}     best   median    first')
    for name, run in results.items():
        if run is None:
            print(f'  {name:<{width}}     failed')
            continue
        unit = 'ms' if name in ('slice_step', 'paint_stroke') else 's'
        scale = 1000 if unit == 'ms' else 1
        wall = (
            f'  cpu {run["cpu_seconds"] * scale:6.1f} {unit}'
            if 'cpu_seconds' in run
            else ''
        )
        print(
            f'  {name:<{width}}  {run["seconds"] * scale:7.3f}'
            f'  {run["median_seconds"] * scale:7.3f}'
            f'  {run["first_seconds"] * scale:7.3f} {unit}'
            f'  {run["rss_mb"]:6.0f} MB  {run["modules"]:5d} modules{wall}'
        )
    if args.json:
        with open(args.json, 'w', encoding='utf-8') as fh:
            json.dump(record, fh, indent=2)
        print(f'wrote {args.json}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
