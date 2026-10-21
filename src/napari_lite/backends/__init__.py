# napari-lite: own code
"""The seams between the model, the renderer and the front end (issue 5).

Two contracts, both Protocols, no base classes:

- ``CanvasBackend`` is a renderer: it draws a ``ViewerModel`` and keeps
  itself in step with it (layers, camera, dims, overlays); a front end
  only places its ``native`` widget, asks for screenshots, hands it key
  events and closes it.  The built-in one is ``'vispy'``
  (``napari_lite._vispy.backend.VispyBackend``).
- ``Window`` is what a ``Viewer`` asks of its window, whichever toolkit
  draws it.  The built-in front ends are ``'qt'`` (the window) and
  ``'jupyter'`` (a notebook cell, ``backends.jupyter``).

``get_renderer`` and ``get_gui`` find them by name: a built-in name costs
no lookup; any other is looked for in the entry-point groups
``napari_lite.renderers`` and ``napari_lite.guis``, where another
package registers a ``Renderer(viewer, *, gui=None, parent=None)`` or a
``Window(viewer, *, show=True, renderer=None)``.  ``Viewer(renderer=...,
gui=...)`` takes the names (or the classes themselves), ``gui=None`` for
no window at all (``backends.headless``), and by default whatever
``NAPARI_LITE_RENDERER`` and ``NAPARI_LITE_GUI`` say.
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
    'DEFAULT_RENDERER',
    'ENTRY_POINT_GROUP',
    'GUI_ENVIRONMENT_VARIABLE',
    'NO_GUI_NAMES',
    'RENDERER_ENTRY_POINT_GROUP',
    'RENDERER_ENVIRONMENT_VARIABLE',
    'CanvasBackend',
    'Window',
    'available_guis',
    'available_renderers',
    'get_gui',
    'get_renderer',
    'resolve_gui',
    'resolve_renderer',
]

GUI_ENVIRONMENT_VARIABLE = 'NAPARI_LITE_GUI'
ENTRY_POINT_GROUP = 'napari_lite.guis'
DEFAULT_GUI = 'qt'
# what NAPARI_LITE_GUI (or Viewer(gui=...)) may say for "no window"
NO_GUI_NAMES = ('none', 'headless', 'off')

RENDERER_ENVIRONMENT_VARIABLE = 'NAPARI_LITE_RENDERER'
RENDERER_ENTRY_POINT_GROUP = 'napari_lite.renderers'
DEFAULT_RENDERER = 'vispy'

_BUILTIN_GUIS: dict[str, tuple[str, str]] = {
    'qt': ('napari_lite._qt.qt_main_window', 'Window'),
    'jupyter': ('napari_lite.backends.jupyter', 'JupyterWindow'),
}
_BUILTIN_RENDERERS: dict[str, tuple[str, str]] = {
    'vispy': ('napari_lite._vispy.backend', 'VispyBackend'),
}


@runtime_checkable
class CanvasBackend(Protocol):
    """What a front end uses from a renderer.

    A renderer is made as ``Renderer(viewer, *, gui=None, parent=None)``:
    ``gui`` is the toolkit the front end places the canvas in (``'qt'``,
    ``'jupyter'``, or None for no window), ``parent`` the front end's
    parent widget when it has one.
    From then on the renderer follows the model by itself: layers added
    and removed, the camera, the dims, the overlays, the canvas size.  A
    renderer that cannot draw for a front end raises ``ValueError``.
    """

    native: Any
    """The widget to place, in the front end's toolkit (a QWidget for
    'qt', an ipywidget for 'jupyter'), or None without a window."""

    def screenshot(
        self,
        *,
        size: tuple[int, int] | None = None,
        scale: float = 1.0,
        fit_to_data_extent: bool = False,
        device_pixel_ratio: float | None = None,
    ) -> np.ndarray:
        """The canvas drawn now, as an RGBA uint8 array: at ``size``
        (height, width, in device pixels; ``device_pixel_ratio`` per canvas
        pixel, by default the canvas's own) times ``scale``, or, with
        ``fit_to_data_extent``, sized around the data with one canvas
        pixel per data pixel."""
        ...

    def key_event(self, event: Any, *, release: bool = False) -> None:
        """A key event the front end's widget received outside the
        canvas (the toolkit's event object), for the viewer's key
        bindings."""
        ...

    def close(self) -> None:
        """Let the model go and release the canvas."""
        ...


@runtime_checkable
class Window(Protocol):
    """What a ``Viewer`` uses from its window.

    A front end's window takes ``(viewer, *, show=True, renderer=None)``
    (``renderer``: the renderer class to draw with, None for the
    default) and gives these methods; the Qt one is
    ``napari_lite._qt.qt_main_window.Window``.  The two task-status
    hooks are what thread workers report to.  Two methods are optional:
    ``show_shortcuts()`` and ``open_files()``, the window's own versions
    of the actions behind Ctrl+Alt+/ and Ctrl+O
    (``napari_lite.backends._actions``); without them a bare model in a
    ``QtCanvas`` gets Qt dialogs and a window without Qt a status line.
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
    window.  ``'default'`` reads ``NAPARI_LITE_GUI`` ('qt', 'jupyter',
    'none', or a registered name) and is 'qt' when that is not set or
    empty."""
    if gui == 'default':
        gui = os.environ.get(GUI_ENVIRONMENT_VARIABLE) or DEFAULT_GUI
    if gui is None:
        return None
    name = gui.strip().lower()
    if name in NO_GUI_NAMES:
        return None
    return name


def _registered(group: str) -> dict[str, Any]:
    return {
        entry_point.name.lower(): entry_point
        for entry_point in entry_points(group=group)
    }


def _lookup(
    name: str, builtin: dict[str, tuple[str, str]], group: str, what: str
) -> Any:
    """The class registered as ``name``: built in (no lookup), or among
    the entry points of ``group``."""
    key = name.strip().lower()
    if key in builtin:
        module_name, attribute = builtin[key]
        return getattr(importlib.import_module(module_name), attribute)
    registered = _registered(group)
    if key in registered:
        return registered[key].load()
    known = ', '.join(repr(n) for n in [*builtin, *registered])
    raise ValueError(
        f'no {what} named {name!r}; known: {known} (built in, then '
        f'registered under the entry-point group {group!r})'
    )


def available_guis() -> list[str]:
    """The front ends by name: the built-in ones, then the registered."""
    return [*_BUILTIN_GUIS, *_registered(ENTRY_POINT_GROUP)]


def get_gui(name: str) -> Callable[..., Window]:
    """The window class (or factory) of the front end ``name``."""
    return _lookup(name, _BUILTIN_GUIS, ENTRY_POINT_GROUP, 'front end')


def available_renderers() -> list[str]:
    """The renderers by name: the built-in one, then the registered."""
    return [*_BUILTIN_RENDERERS, *_registered(RENDERER_ENTRY_POINT_GROUP)]


def get_renderer(name: str) -> Callable[..., CanvasBackend]:
    """The renderer class (or factory) called ``name``."""
    return _lookup(
        name, _BUILTIN_RENDERERS, RENDERER_ENTRY_POINT_GROUP, 'renderer'
    )


def resolve_renderer(
    renderer: str | Callable[..., CanvasBackend],
    *,
    gui: str | None = 'qt',
) -> Callable[..., CanvasBackend]:
    """The renderer class ``Viewer(renderer=...)`` means: the class (or
    factory) itself when one is given, else the one named.  ``'default'``
    reads ``NAPARI_LITE_RENDERER`` and is ``'vispy'`` when that is not
    set or empty.  ``gui`` is the toolkit the renderer will draw for: for
    a viewer without a Qt window (None, ``'jupyter'``) vispy may draw with
    its egl application, and PyOpenGL is readied for it before vispy is
    first imported (``utils/_pyopengl.py``)."""
    if callable(renderer):
        return renderer
    name = renderer
    if name == 'default':
        name = (
            os.environ.get(RENDERER_ENVIRONMENT_VARIABLE) or DEFAULT_RENDERER
        )
    if gui in (None, 'jupyter') and name.strip().lower() == 'vispy':
        from napari_lite.utils._pyopengl import prefer_egl

        prefer_egl()
    return get_renderer(name)
