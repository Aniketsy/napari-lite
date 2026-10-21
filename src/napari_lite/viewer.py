# napari-lite: own code
"""``Viewer``: a ``ViewerModel`` with a window, or without one.

Same constructor and methods as napari's ``Viewer`` where napari-lite has
the feature: ``title``, ``ndisplay``, ``order``, ``axis_labels``, ``show``;
``window``, ``screenshot``, ``export_figure``, ``show``, ``close``,
``close_all``.  There is no console, so ``update_console`` is absent.
``gui`` picks the front end and ``renderer`` the renderer
(``napari_lite.backends``): the Qt window and vispy by default; a
notebook cell with ``gui='jupyter'``; no window at all with ``gui=None``
(screenshots only).
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any, ClassVar
from weakref import WeakSet

import napari_lite.backends._actions  # noqa: F401  (registers Ctrl+O and co.)
from napari_lite.components.viewer_model import ViewerModel
from napari_lite.utils.events.event_utils import disconnect_events

if TYPE_CHECKING:
    from collections.abc import Callable

    import numpy as np

    from napari_lite.backends import CanvasBackend, Window
    from napari_lite.backends.headless import HeadlessCanvas

__all__ = ['Viewer', 'current_viewer']


class Viewer(ViewerModel):
    """napari-lite's n-dimensional array viewer.

    Parameters
    ----------
    title : str, optional
        Title of the viewer window. By default 'napari-lite'.
    ndisplay : {2, 3}, optional
        Number of displayed dimensions. By default 2.
    order : tuple of int, optional
        Order in which dimensions are displayed; the last two or three are
        the displayed ones. By default ().
    axis_labels : list of str, optional
        Dimension names. By default sequential numbers.
    show : bool, optional
        Show the window after instantiation. By default True.
    show_welcome_screen : bool, optional
        Accepted for compatibility with napari and ignored: napari-lite has
        no welcome screen.
    gui : str or None, optional
        The front end: ``'qt'``; ``'jupyter'``, the viewer as widgets in a
        notebook cell (the ``jupyter`` extra); the name of one another
        package registers (``napari_lite.backends``); or None for no window
        at all: the viewer draws off screen, ``screenshot`` and
        ``export_figure`` work, ``window`` and ``show`` do not. By default
        ``'default'``: what the environment variable ``NAPARI_LITE_GUI``
        says (``'qt'``, ``'jupyter'``, ``'none'``, or a name), and ``'qt'``
        when it is not set.
    renderer : str or callable, optional
        What draws the layers: ``'vispy'``, the name of a renderer another
        package registers, or the renderer class itself. By default
        ``'default'``: what ``NAPARI_LITE_RENDERER`` says, and vispy when
        it is not set.
    """

    _window: Window | None = None
    _headless: HeadlessCanvas | None = None
    _instances: ClassVar[WeakSet[Viewer]] = WeakSet()

    def __init__(
        self,
        *,
        title: str = 'napari-lite',
        ndisplay: int = 2,
        order: tuple[int, ...] = (),
        axis_labels: tuple[str, ...] = (),
        show: bool = True,
        show_welcome_screen: bool = False,
        gui: str | None = 'default',
        renderer: str | Callable[..., CanvasBackend] = 'default',
    ) -> None:
        super().__init__(
            title=title,
            ndisplay=ndisplay,
            order=order,
            axis_labels=axis_labels,
        )
        from napari_lite.backends import (
            get_gui,
            resolve_gui,
            resolve_renderer,
        )

        name = resolve_gui(gui)
        renderer_class = resolve_renderer(renderer, gui=name)
        if name is None:
            from napari_lite.backends.headless import HeadlessCanvas

            self._headless = HeadlessCanvas(self, renderer=renderer_class)
        else:
            # the toolkit (Qt by default) is imported here, when the first
            # Viewer is created
            self._window = get_gui(name)(
                self, show=show, renderer=renderer_class
            )
        self._instances.add(self)

    def __new__(cls, *args: Any, **kwargs: Any) -> Viewer:
        # accept and discard the constructor arguments so that __new__ can
        # be patched temporarily, as in napari
        return super().__new__(cls)

    @property
    def window(self) -> Window:
        """The window (kept off the pydantic model).  A viewer made with
        ``gui=None`` has none: asking raises ``AttributeError``, so that
        ``hasattr(viewer, 'window')`` says so."""
        if self._window is None:
            raise AttributeError(
                'this viewer has no window: it was made with gui=None '
                '(headless); screenshot() and export_figure() work, '
                'the window and show() do not'
            )
        return self._window

    @property
    def headless(self) -> bool:
        """Whether the viewer draws without a window (``gui=None``)."""
        return self._window is None

    def screenshot(
        self,
        path: str | None = None,
        *,
        size: tuple[int, int] | None = None,
        scale: float | None = None,
        canvas_only: bool = True,
        flash: bool = False,
    ) -> np.ndarray:
        """Render the canvas (or the whole window) to an RGBA array.

        Parameters
        ----------
        path : str, optional
            File to save the image to.
        size : (int, int), optional
            Height and width in pixels; default: as shown. Canvas only.
        scale : float, optional
            Scale factor for the canvas size. Canvas only.
        canvas_only : bool
            Only the canvas (default) or the whole window.  A viewer
            without a window (``gui=None``) gives its canvas either way, as
            the notebook window does, so ``nbscreenshot`` works for both.
        flash : bool
            Flash the widget after capturing (default False).
        """
        if self._headless is not None:
            return self._headless.screenshot(path, size=size, scale=scale)
        return self.window.screenshot(
            path=path,
            size=size,
            scale=scale,
            flash=flash,
            canvas_only=canvas_only,
        )

    def export_figure(
        self,
        path: str | None = None,
        *,
        scale_factor: float = 1,
        flash: bool = False,
    ) -> np.ndarray:
        """Screenshot tightly fitted around the data, one pixel per data
        pixel (times ``scale_factor``)."""
        if self._headless is not None:
            return self._headless.export_figure(path, scale=scale_factor)
        return self.window.export_figure(
            path=path, scale=scale_factor, flash=flash
        )

    def show(self, *, block: bool = False) -> None:
        """Show and raise the window."""
        self.window.show(block=block)

    def close(self) -> None:
        """Close the window, or release the off-screen canvas."""
        # shut the slicer down first so no more tasks are processed
        self._layer_slicer.shutdown()
        # no slicing while the layers are removed one by one
        disconnect_events(self.dims.events, self)
        self.layers.clear()
        if self._headless is not None:
            self._headless.close()
        else:
            self.window.close()
        self._instances.discard(self)

    @classmethod
    def close_all(cls) -> int:
        """Close every open viewer; return how many were closed."""
        viewers = list(cls._instances)
        for viewer in viewers:
            viewer.close()
        return len(viewers)


def current_viewer() -> Viewer | None:
    """The viewer whose Qt window was active last; without one, the viewer
    whose notebook window was shown last; or None.  A front end that was
    never imported has no windows, so asking imports no toolkit."""
    if 'napari_lite._qt.qt_main_window' in sys.modules:
        from napari_lite._qt.qt_main_window import _QtMainWindow

        viewer = _QtMainWindow.current_viewer()
        if viewer is not None:
            return viewer  # type: ignore[return-value]
    if 'napari_lite.backends.jupyter' in sys.modules:
        from napari_lite.backends.jupyter import JupyterWindow

        return JupyterWindow.current_viewer()  # type: ignore[return-value]
    return None
