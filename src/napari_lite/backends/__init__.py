# napari-lite: own code
"""The seams between the model, the renderer and the front end (issue 5,
docs/backends.md).

``Window`` is what a ``Viewer`` asks of its window, whichever toolkit
draws it.  ``get_gui`` finds a front end by name: the built-in ``'qt'``,
or one that another package registers under the entry-point group
``napari_lite.guis`` as a callable ``Window(viewer, *, show=True)``
returning an object with the ``Window`` methods.  ``Viewer(gui=...)``
takes the name, ``None`` for no window at all (``backends.headless``),
or by default whatever ``NAPARI_LITE_GUI`` says.

The renderer side, the ``CanvasBackend`` contract, follows in step 3.
"""

from __future__ import annotations

import importlib
import os
from collections.abc import Callable, Sequence
from importlib.metadata import entry_points
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    import uuid

    import numpy as np

    from napari_lite.utils.task_status import Status

__all__ = [
    'DEFAULT_GUI',
    'ENTRY_POINT_GROUP',
    'GUI_ENVIRONMENT_VARIABLE',
    'NO_GUI_NAMES',
    'Window',
    'available_guis',
    'get_gui',
    'resolve_gui',
]

GUI_ENVIRONMENT_VARIABLE = 'NAPARI_LITE_GUI'
ENTRY_POINT_GROUP = 'napari_lite.guis'
DEFAULT_GUI = 'qt'
# what NAPARI_LITE_GUI (or Viewer(gui=...)) may say for "no window"
NO_GUI_NAMES = ('none', 'headless', 'off')

_BUILTIN_GUIS: dict[str, tuple[str, str]] = {
    'qt': ('napari_lite._qt.qt_main_window', 'Window'),
}


@runtime_checkable
class Window(Protocol):
    """What a ``Viewer`` uses from its window.

    A front end's window takes ``(viewer, *, show=True)`` and gives these
    methods; the Qt one is ``napari_lite._qt.qt_main_window.Window``.
    The two task-status hooks are what thread workers report to.
    """

    def show(self, *, block: bool = False) -> None: ...

    def close(self) -> None: ...

    def activate(self) -> None: ...

    def resize(self, width: int, height: int) -> None: ...

    def set_geometry(
        self, left: int, top: int, width: int, height: int
    ) -> None: ...

    def geometry(self) -> tuple[int, int, int, int]: ...

    def screenshot(
        self,
        path: str | None = None,
        size: tuple[int, int] | None = None,
        scale: float | None = None,
        flash: bool = False,
        canvas_only: bool = False,
    ) -> np.ndarray: ...

    def export_figure(
        self, path: str | None = None, *, scale: float = 1, flash: bool = False
    ) -> np.ndarray: ...

    def clipboard(
        self, flash: bool = False, canvas_only: bool = False
    ) -> None: ...

    def add_dock_widget(
        self,
        widget: Any,
        *,
        name: str = '',
        area: str | None = None,
        allowed_areas: Sequence[str] | None = None,
        add_vertical_stretch: bool = True,
        tabify: bool = False,
        menu: Any = None,
    ) -> Any: ...

    def remove_dock_widget(self, widget: Any, menu: Any = None) -> None: ...

    def _register_task_status(
        self,
        provider: str,
        task_status: Status,
        description: str = '',
        cancel_callback: Callable[[], None] | None = None,
    ) -> uuid.UUID: ...

    def _update_task_status(
        self,
        task_status_id: uuid.UUID,
        status: Status,
        description: str = '',
    ) -> bool: ...


def resolve_gui(gui: str | None) -> str | None:
    """The front end ``Viewer(gui=...)`` means: its name, or None for no
    window.  ``'default'`` reads ``NAPARI_LITE_GUI`` ('qt', 'none', or a
    registered name) and is 'qt' when that is not set."""
    if gui == 'default':
        gui = os.environ.get(GUI_ENVIRONMENT_VARIABLE, DEFAULT_GUI)
    if gui is None:
        return None
    name = gui.strip().lower()
    if name in NO_GUI_NAMES or not name:
        return None
    return name


def _registered_guis() -> dict[str, Any]:
    return {
        entry_point.name.lower(): entry_point
        for entry_point in entry_points(group=ENTRY_POINT_GROUP)
    }


def available_guis() -> list[str]:
    """The front ends by name: the built-in ones, then the registered."""
    return [*_BUILTIN_GUIS, *_registered_guis()]


def get_gui(name: str) -> Callable[..., Window]:
    """The window class (or factory) of the front end ``name``.  Built-in
    names cost no lookup; others are found among the entry points."""
    key = name.strip().lower()
    if key in _BUILTIN_GUIS:
        module_name, attribute = _BUILTIN_GUIS[key]
        return getattr(importlib.import_module(module_name), attribute)
    registered = _registered_guis()
    if key in registered:
        return registered[key].load()
    known = ', '.join(repr(n) for n in [*_BUILTIN_GUIS, *registered])
    raise ValueError(
        f'no front end named {name!r}; known: {known} (built in, then '
        f'registered under the entry-point group {ENTRY_POINT_GROUP!r})'
    )
