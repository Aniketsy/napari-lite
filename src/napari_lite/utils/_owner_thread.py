# napari-lite: own code
"""Keep a viewer's work on the thread that made it (issue 5,
docs/backends.md).

A viewer, its GL context and its Qt objects belong to the thread that
made them, which in a notebook kernel runs the kernel's asyncio loop; Qt
even ends the process when a GL context is made current on another
thread.  ipykernel 7 can run widget callbacks elsewhere: it has
"subshells", threads of their own, and JupyterLab sends widget messages to
one so that sliders keep working while a cell runs.

- ``on_main_shell`` asks the kernel to handle a widget's messages on its
  main shell, the viewer's thread, as before subshells; the viewer's own
  widgets and the ones docked next to it use it.
- ``OwnerThread`` remembers the thread that made it and its loop: ``call``
  runs a function there, ``run`` also waits for the result.  It is the
  safety net for what still arrives on another thread.  With IPython's Qt
  event loop on (``%gui qt``, as napari users often start a notebook) the
  kernel's main thread waits in Qt's loop between messages and the asyncio
  loop only runs when a message reaches the main shell; a call is then
  handed over through Qt instead.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import sys
import threading
from collections.abc import Callable
from typing import Any

__all__ = ['OwnerThread', 'ipython_runs_qt', 'on_main_shell']


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


def _main_shell(data: Any, default: Any) -> None:
    return None  # the main shell, whichever subshell the message came from


def on_main_shell(*widgets: Any) -> None:
    """Have the kernel handle the messages of these ipywidgets, and of the
    widgets inside them, on its main shell: their callbacks then run on the
    thread that runs the cells.  ipykernel 7 routes a widget's messages by
    its comm's ``_reply_subshell_for``; without it there are no subshells
    and nothing to do."""
    for widget in widgets:
        comm = getattr(widget, 'comm', None)
        if comm is not None:
            comm._reply_subshell_for = _main_shell
        on_main_shell(*(getattr(widget, 'children', None) or ()))


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

    def _through_qt(self) -> bool:
        return ipython_runs_qt() and _qt_main_thread_ident() == self.ident

    @property
    def can_hand_over(self) -> bool:
        """Whether a call from another thread can reach the owner: through
        Qt's loop when IPython runs it there, or the owner's asyncio loop."""
        if self._through_qt():
            return True
        return self.loop is not None and not self.loop.is_closed()

    def call(self, func: Callable[..., Any], *args: Any) -> bool:
        """Run ``func(*args)`` on the owner thread: now when called there,
        else soon, through Qt's loop when IPython runs it on the owner
        thread, else on the owner's asyncio loop.  With neither, it runs
        now, here.  Returns whether it was handed over."""
        if self.is_current or not self.can_hand_over:
            func(*args)
            return False
        if self._through_qt():
            from superqt.utils import ensure_main_thread

            ensure_main_thread(func)(*args)
        else:
            self.loop.call_soon_threadsafe(func, *args)  # type: ignore[union-attr]
        return True

    def run(
        self,
        func: Callable[..., Any],
        *args: Any,
        timeout: float = 60.0,
        **kwargs: Any,
    ) -> Any:
        """``func(*args, **kwargs)`` on the owner thread, waiting for its
        result (or its exception): now when called there, or when nothing
        can hand it over."""
        if self.is_current or not self.can_hand_over:
            return func(*args, **kwargs)
        result: concurrent.futures.Future[Any] = concurrent.futures.Future()

        def run_there() -> None:
            try:
                result.set_result(func(*args, **kwargs))
            except BaseException as exc:
                result.set_exception(exc)

        self.call(run_there)
        try:
            return result.result(timeout)
        except concurrent.futures.TimeoutError as e:
            raise TimeoutError(
                f"the viewer's thread did not get to this in {timeout:g} s: "
                'is a cell still running?'
            ) from e
