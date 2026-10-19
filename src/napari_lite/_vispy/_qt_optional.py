# napari-lite: own code
"""What the vispy renderer takes from Qt, made optional (issue 5,
docs/backends.md).

napari's vispy canvas assumes Qt: it selects vispy's Qt application when
imported, throttles mouse moves with superqt, renders text through Qt's
fonts and measures it with Qt's font metrics.  The vendor tool points the
copied imports here (``tools/vendor.toml``).  When vispy runs on Qt (a
window, or an off-screen widget) everything is Qt's as before; when it
runs on an offscreen application (``egl`` or ``osmesa``: the headless
viewer on Linux, with no Qt in the process) the plain version is used.

- ``use_vispy_app``: picks vispy's application once per process, the Qt
  binding qtpy uses or an offscreen one.
- ``qthrottled``, ``qdebounced``: superqt's for a canvas in a Qt window,
  whose event loop fires their timers; the function itself for a canvas
  drawn off the screen (no window, or a notebook), where nothing may run
  Qt's event loop and a call waiting for a timer would never happen
  (``qt_timers`` says which, around the making of a canvas).
- ``FontInfo``, ``QtFontManager``, ``default_font_manager``,
  ``default_font_family``: the font behind every text visual; Qt's font
  manager on Qt, vispy's own (freetype) otherwise.
- ``font_metrics``: the measurements overlays take; Qt's on Qt, an
  estimate from the font size otherwise.
"""

from __future__ import annotations

import contextlib
import sys
from collections.abc import Callable, Iterator
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from vispy.app.application import Application

__all__ = [
    'OFFSCREEN_APPS',
    'SDF_FONT_SIZE',
    'FontInfo',
    'QtFontManager',
    'available_offscreen_app',
    'default_font_family',
    'default_font_manager',
    'font_metrics',
    'qdebounced',
    'qt_timers',
    'qthrottled',
    'use_vispy_app',
    'vispy_app_is_qt',
]

# the size Qt's glyphs are rendered at before scaling (utils/qt_font.py)
SDF_FONT_SIZE = 256

# vispy applications that draw without any window; Linux only
OFFSCREEN_APPS = ('egl', 'osmesa')

_QT_PREFIXES = ('pyqt', 'pyside')


# vispy's application
def _current_vispy_app() -> Application | None:
    """vispy's default application, if one has been selected (None before
    any canvas exists).  ``vispy.app.use_app()`` would select one, so
    vispy's own record is read instead."""
    if 'vispy.app' not in sys.modules:
        return None
    from vispy.app import _default_app

    return _default_app.default_app


def _is_qt(backend_name: str) -> bool:
    return backend_name.lower().startswith(_QT_PREFIXES)


def vispy_app_is_qt() -> bool:
    """Whether vispy draws through a Qt binding (a window or an off-screen
    widget) rather than an offscreen application.  Before any canvas is
    made, Qt counts as in use when it is already imported."""
    app = _current_vispy_app()
    if app is None:
        return 'qtpy' in sys.modules
    return _is_qt(app.backend_name)


def _qt_binding() -> str:
    from qtpy import API_NAME  # ImportError without a Qt binding

    return API_NAME


def available_offscreen_app() -> str | None:
    """The first of vispy's offscreen applications that loads here (the
    EGL or OSMesa library is found), or None."""
    from vispy import app

    for name in OFFSCREEN_APPS:
        try:
            app.Application(name)
        except Exception:  # vispy says why, in a RuntimeError
            continue
        return name
    return None


def use_vispy_app(kind: Literal['qt', 'offscreen']) -> str:
    """Select vispy's application backend and return its name.

    ``'qt'``: the binding qtpy uses, for a Qt canvas.  ``'offscreen'``:
    ``egl`` or ``osmesa`` where one loads, otherwise the Qt binding with
    an off-screen widget (Windows, macOS).  vispy allows one application
    per process, so the first canvas decides and a later, different
    choice raises.
    """
    from vispy import app

    current = _current_vispy_app()
    if current is not None:
        if kind == 'qt' and not _is_qt(current.backend_name):
            raise RuntimeError(
                f'vispy already draws on {current.backend_name!r} in this '
                'process (a headless or notebook viewer came first); a Qt '
                'window needs a process of its own'
            )
        return current.backend_name
    if kind == 'qt':
        name = _qt_binding()
    else:
        name = available_offscreen_app()
        if name is None:
            try:
                name = _qt_binding()
            except ImportError as e:
                raise ImportError(
                    "a headless viewer needs vispy's egl or osmesa "
                    'application (Linux: the EGL or OSMesa library) or a '
                    'Qt binding to draw with; none of them is available'
                ) from e
    app.use_app(name)
    return name


# superqt's throttle and debounce
# Whether the canvas being made sits in a Qt window, whose event loop
# fires Qt's timers; None outside ``qt_timers``: then any Qt canvas counts
_QT_TIMERS: ContextVar[bool | None] = ContextVar(
    'napari_lite_qt_timers', default=None
)


@contextlib.contextmanager
def qt_timers(enabled: bool) -> Iterator[None]:
    """Within, ``qthrottled`` and ``qdebounced`` use Qt's timers only if
    ``enabled``: the renderer says so while it makes a canvas and its
    layer visuals, True for a Qt window, False for a canvas drawn off the
    screen."""
    token = _QT_TIMERS.set(enabled)
    try:
        yield
    finally:
        _QT_TIMERS.reset(token)


def _use_qt_timers() -> bool:
    enabled = _QT_TIMERS.get()
    return vispy_app_is_qt() and enabled is not False


def qthrottled(func: Callable[..., Any], **kwargs: Any) -> Callable[..., Any]:
    """superqt's ``qthrottled`` for a canvas in a Qt window; ``func``
    itself otherwise."""
    if _use_qt_timers():
        from superqt.utils import qthrottled as _qthrottled

        return _qthrottled(func, **kwargs)
    return func


def qdebounced(func: Callable[..., Any], **kwargs: Any) -> Callable[..., Any]:
    """superqt's ``qdebounced`` for a canvas in a Qt window; ``func``
    itself otherwise."""
    if _use_qt_timers():
        from superqt.utils import qdebounced as _qdebounced

        return _qdebounced(func, **kwargs)
    return func


# fonts
class _LazyQtFontManager(type):
    """Stands for Qt's ``QtFontManager`` (utils/qt_font.py, which imports
    Qt) until one is made or checked for, so that the canvas module
    imports without Qt."""

    def _real(cls) -> type:
        from napari_lite._vispy.utils.qt_font import QtFontManager

        return QtFontManager

    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        return cls._real()(*args, **kwargs)

    def __instancecheck__(cls, instance: Any) -> bool:
        if 'qtpy' not in sys.modules:
            return False
        return isinstance(instance, cls._real())


class QtFontManager(metaclass=_LazyQtFontManager):
    """Qt's font manager, imported from utils/qt_font.py when first made."""


class _VispyFontManager:
    """vispy's own font manager (freetype), for text without Qt; the face
    names napari uses with a space ('Open Sans') are vispy's bundled fonts
    without one, so they are found without fontconfig."""

    _bundled = ('OpenSans', 'Cabin')

    def __init__(self) -> None:
        from vispy.visuals.text.text import FontManager

        self._manager = FontManager()

    def get_font(
        self, face: str, bold: bool = False, italic: bool = False
    ) -> Any:
        joined = face.replace(' ', '')
        if joined in self._bundled:
            face = joined
        return self._manager.get_font(face, bold, italic)


def default_font_manager() -> Any:
    """Qt's font manager when vispy runs on Qt; vispy's own otherwise."""
    if vispy_app_is_qt():
        from napari_lite._vispy.utils.qt_font import QtFontManager

        return QtFontManager()
    return _VispyFontManager()


def default_font_family() -> str:
    """The application font when vispy runs on Qt; vispy's bundled
    OpenSans otherwise."""
    if vispy_app_is_qt():
        from qtpy.QtGui import QGuiApplication

        return QGuiApplication.font().family()
    return 'OpenSans'


@dataclass
class FontInfo:
    """Which font the text visuals use and what renders its glyphs: the
    same two fields as napari's (utils/qt_font.py), with the renderer
    picked for the application vispy runs on."""

    face: str = 'Open Sans'
    font_manager: Any = field(default_factory=default_font_manager)


class _Size:
    __slots__ = ('_height', '_width')

    def __init__(self, width: float, height: float) -> None:
        self._width = width
        self._height = height

    def width(self) -> float:
        return self._width

    def height(self) -> float:
        return self._height


class _EstimatedMetrics:
    """Text sizes from the font size alone, for overlays drawn without
    Qt: 0.55 em per character and 1.2 em per line, about what a
    sans-serif face measures.  Same two methods as ``QFontMetricsF`` as
    the overlays use them."""

    __slots__ = ('_size',)

    def __init__(self, size: float) -> None:
        self._size = float(size)

    def height(self) -> float:
        return 1.2 * self._size

    def size(self, flags: int, text: str) -> _Size:
        lines = text.split('\n')
        return _Size(
            0.55 * self._size * max(len(line) for line in lines),
            1.2 * self._size * len(lines),
        )


def font_metrics(
    face: str, size: int, bold: bool = False, italic: bool = False
) -> Any:
    """Font metrics with ``height()`` and ``size(flags, text)``: Qt's
    when vispy runs on Qt, an estimate from the font size otherwise."""
    if vispy_app_is_qt():
        from qtpy.QtGui import QFontMetricsF

        from napari_lite._vispy.utils.qt_font import make_qfont

        return QFontMetricsF(make_qfont(face, size, bold=bold, italic=italic))
    return _EstimatedMetrics(size)
