# napari-lite: own code
"""``Viewer``: a ``ViewerModel`` with a window.

Same constructor and methods as napari's ``Viewer`` where napari-lite has
the feature: ``title``, ``ndisplay``, ``order``, ``axis_labels``, ``show``;
``window``, ``screenshot``, ``export_figure``, ``show``, ``close``,
``close_all``.  There is no console, so ``update_console`` is absent.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar
from weakref import WeakSet

from napari_lite.components.viewer_model import ViewerModel
from napari_lite.utils.events.event_utils import disconnect_events

if TYPE_CHECKING:
    import numpy as np

    from napari_lite.window import Window

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
    """

    _window: Window = None  # type: ignore[assignment]
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
    ) -> None:
        super().__init__(
            title=title,
            ndisplay=ndisplay,
            order=order,
            axis_labels=axis_labels,
        )
        # Qt is imported here, when the first Viewer is created
        from napari_lite.window import Window

        self._window = Window(self, show=show)
        self._instances.add(self)

    def __new__(cls, *args: Any, **kwargs: Any) -> Viewer:
        # accept and discard the constructor arguments so that __new__ can
        # be patched temporarily, as in napari
        return super().__new__(cls)

    @property
    def window(self) -> Window:
        """The window (kept off the pydantic model)."""
        return self._window

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
            Only the canvas (default) or the whole window.
        flash : bool
            Flash the widget after capturing (default False).
        """
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
        return self.window.export_figure(
            path=path, scale=scale_factor, flash=flash
        )

    def show(self, *, block: bool = False) -> None:
        """Show and raise the window."""
        self.window.show(block=block)

    def close(self) -> None:
        """Close the window."""
        # shut the slicer down first so no more tasks are processed
        self._layer_slicer.shutdown()
        # no slicing while the layers are removed one by one
        disconnect_events(self.dims.events, self)
        self.layers.clear()
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
    """The viewer whose window was active last, or None."""
    try:
        from napari_lite._qt.qt_main_window import _QtMainWindow
    except ImportError:
        return None
    return _QtMainWindow.current_viewer()  # type: ignore[return-value]
