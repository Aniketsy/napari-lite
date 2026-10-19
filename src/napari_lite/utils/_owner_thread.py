# napari-lite: own code
"""Hand work to the thread that made an object (issue 5, docs/backends.md).

A notebook kernel may run widget callbacks on a thread of their own:
ipykernel 7 has "subshells", and JupyterLab sends widget messages to one,
so that sliders keep working while a cell runs.  A viewer, its GL context
and its Qt objects belong to the thread that made them, which runs the
kernel's asyncio loop; Qt even ends the process when a GL context is made
current on another thread.  ``OwnerThread`` remembers that thread and its
loop, and ``call`` runs a function there.

With IPython's Qt event loop on (``%gui qt``, as napari users often start
a notebook) the kernel's main thread waits in Qt's loop between messages
and the asyncio loop only runs when a message reaches the main shell; a
call is then handed over through Qt instead.
"""

from __future__ import annotations

import asyncio
import sys
import threading
from collections.abc import Callable
from typing import Any

__all__ = ['OwnerThread', 'ipython_runs_qt']


def ipython_runs_qt() -> bool:
    """Whether IPython runs Qt's event loop in this process (``%gui qt``)."""
    ipython = sys.modules.get('IPython')
    shell = ipython.get_ipython() if ipython is not None else None
    loop = getattr(shell, 'active_eventloop', None)
    return isinstance(loop, str) and loop.startswith('qt')


def _qt_main_thread_ident() -> int | None:
    """The thread of the running QApplication, if there is one."""
    if 'qtpy' not in sys.modules:
        return None
    from qtpy.QtCore import QCoreApplication, QThread

    app = QCoreApplication.instance()
    if app is None:
        return None
    if app.thread() is QThread.currentThread():
        return threading.get_ident()
    return threading.main_thread().ident


class OwnerThread:
    """The thread that made this (the current one) and its running
    asyncio loop, if it has one (a kernel does; a plain script does not)."""

    def __init__(self) -> None:
        self.ident = threading.get_ident()
        try:
            self.loop: asyncio.AbstractEventLoop | None = (
                asyncio.get_running_loop()
            )
        except RuntimeError:
            self.loop = None

    @property
    def is_current(self) -> bool:
        """Whether the calling thread is the owner."""
        return threading.get_ident() == self.ident

    def call(self, func: Callable[..., Any], *args: Any) -> bool:
        """Run ``func(*args)`` on the owner thread: now when called there,
        else soon, through Qt's loop when IPython runs it on the owner
        thread, else on the owner's asyncio loop.  With neither, it runs
        now, here.  Returns whether it was handed over."""
        if self.is_current:
            func(*args)
            return False
        if ipython_runs_qt() and _qt_main_thread_ident() == self.ident:
            from superqt.utils import ensure_main_thread

            ensure_main_thread(func)(*args)
            return True
        loop = self.loop
        if loop is None or loop.is_closed():
            func(*args)
            return False
        loop.call_soon_threadsafe(func, *args)
        return True
