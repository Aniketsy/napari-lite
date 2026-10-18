# napari-lite: own code
"""Where the time to the first frame of a viewer window goes.

    python bench/first_frame.py            # layers first, then show (b)
    python bench/first_frame.py a          # show first, then add_image (a)
    python bench/first_frame.py b --no-internals

Prints the wall-clock stages of a script that opens a window with one
image, from the first import to the first paint event of the window, and
(unless ``--no-internals``) inclusive timers wrapped around the window's
own steps, nested by time.  Run it alone on a quiet machine; the first run
after a reboot is a cold-cache run and slower than the next ones.
"""

from __future__ import annotations

import sys
import time

T0 = time.perf_counter()
FLOW = next((a for a in sys.argv[1:] if not a.startswith('-')), 'b')
INTERNALS = '--no-internals' not in sys.argv

stages: list[tuple[str, float]] = []
spans: list[tuple[str, float, float]] = []


def stage(name: str) -> None:
    stages.append((name, time.perf_counter()))


def timed(owner, attr: str, label: str) -> None:
    """Wrap a method or a property getter with an inclusive timer."""
    original = getattr(owner, attr, None)
    if original is None:
        return
    if isinstance(original, property):
        fget = original.fget

        def getter(self):
            t = time.perf_counter()
            try:
                return fget(self)
            finally:
                spans.append((label, t, time.perf_counter()))

        setattr(owner, attr, property(getter, original.fset, original.fdel))
        return

    def wrapper(*args, **kwargs):
        t = time.perf_counter()
        try:
            return original(*args, **kwargs)
        finally:
            spans.append((label, t, time.perf_counter()))

    setattr(owner, attr, wrapper)


import numpy as np  # noqa: E402

stage('import numpy')
import napari_lite  # noqa: E402

stage('import napari_lite')
from napari_lite.components import ViewerModel  # noqa: E402

stage('import the components (viewer model, layers)')
from qtpy.QtCore import QEvent, QObject, QTimer  # noqa: E402
from qtpy.QtWidgets import QApplication  # noqa: E402

stage('import qtpy (Qt)')
import napari_lite._qt.qt_main_window as window_module  # noqa: E402
import napari_lite.qt.canvas as canvas_module  # noqa: E402

stage('import the window and canvas modules (vispy, PyOpenGL, superqt)')

if INTERNALS:
    import napari_lite._qt.widgets.qt_dims as dims_module
    import napari_lite._vispy.canvas as vispy_module

    timed(window_module.Window, '__init__', 'Window.__init__')
    timed(window_module.Window, 'show', 'Window.show')
    timed(window_module.Window, '_update_theme', 'theme stylesheet')
    timed(window_module._QtMainWindow, '__init__', '_QtMainWindow.__init__')
    timed(window_module._QtMainWindow, 'show', '_QtMainWindow.show (Qt)')
    timed(canvas_module.QtCanvas, '__init__', 'QtCanvas.__init__')
    timed(canvas_module.QtCanvas, 'dockLayerControls', 'layer controls dock')
    timed(
        canvas_module.QtCanvas, 'controls', 'layer controls (import + build)'
    )
    timed(canvas_module.QtCanvas, 'dockLayerList', 'layer list dock')
    timed(vispy_module.VispyCanvas, '__init__', 'VispyCanvas.__init__')
    timed(dims_module.QtDims, '__init__', 'QtDims.__init__')
    timed(ViewerModel, '__init__', 'ViewerModel.__init__')
    timed(ViewerModel, 'add_image', 'ViewerModel.add_image')

app = QApplication.instance() or QApplication([])
stage('QApplication()')

first_paint: list[float] = []


class _FirstPaint(QObject):
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Paint and not first_paint:
            first_paint.append(time.perf_counter())
        return False


data = np.zeros((512, 512), dtype=np.uint8)
watch = _FirstPaint()
if FLOW == 'a':
    viewer = napari_lite.Viewer()
    stage('Viewer() shown')
    viewer.window._qt_window.installEventFilter(watch)
    viewer.add_image(data)
    stage('add_image')
else:
    viewer = napari_lite.Viewer(show=False)
    stage('Viewer(show=False)')
    viewer.window._qt_window.installEventFilter(watch)
    viewer.add_image(data)
    stage('add_image')
    viewer.show()
    stage('show()')


def report() -> None:
    if first_paint:
        stages.append(('first paint of the window', first_paint[0]))
    flow = 'show first, then add_image' if FLOW == 'a' else 'layers, then show'
    print(
        f'flow {FLOW} ({flow}), Python {sys.version.split()[0]}, {sys.platform}'
    )
    print('stages (seconds, wall clock):')
    previous = T0
    for name, t in stages:
        print(f'  {t - previous:6.3f}  at {t - T0:6.3f}  {name}')
        previous = t
    if spans:
        print('inside the window (inclusive seconds, nested by time):')
        stack: list[float] = []
        for name, start, end in sorted(spans, key=lambda s: (s[1], -s[2])):
            while stack and start >= stack[-1]:
                stack.pop()
            print(f'  {"  " * len(stack)}{end - start:6.3f}  {name}')
            stack.append(end)
    viewer.close()
    app.quit()


QTimer.singleShot(1500, report)
app.exec()
