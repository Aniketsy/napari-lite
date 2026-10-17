# napari-lite: own code
"""Qt widgets and helpers of napari-lite.

``QtCanvas`` is the canvas with dims sliders and status line;
``get_qapp`` and ``run`` manage the Qt application; ``thread_worker``
and ``create_worker`` come from ``napari_lite.qt.threading``.
"""

from napari_lite._qt.qt_event_loop import get_qapp, run
from napari_lite.qt.canvas import QtCanvas, QtStatusLine
from napari_lite.qt.threading import create_worker, thread_worker

__all__ = (
    'QtCanvas',
    'QtStatusLine',
    'create_worker',
    'get_qapp',
    'run',
    'thread_worker',
)
