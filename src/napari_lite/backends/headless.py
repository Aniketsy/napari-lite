# napari-lite: own code
"""A viewer without a window: ``Viewer(gui=None)`` (issue 5).

The renderer draws into a canvas nobody shows; ``screenshot`` and
``export_figure`` give the pictures.  With the vispy renderer, on Linux
vispy's ``egl`` application draws with no Qt in the process (text then
needs freetype-py, the ``headless`` extra); elsewhere, and on Linux
without EGL, the Qt binding draws into a widget kept off the screen, so
Qt is imported but no window appears.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from napari_lite.backends import CanvasBackend, resolve_renderer
from napari_lite.utils.io import imsave

if TYPE_CHECKING:
    import numpy as np

    from napari_lite.components import ViewerModel

__all__ = ['HeadlessCanvas']


class HeadlessCanvas:
    """The canvas of a viewer that has no window.

    Parameters
    ----------
    viewer : ViewerModel
        The model to draw.
    renderer : str or callable, optional
        The renderer's name or class (``napari_lite.backends``); by
        default the one ``NAPARI_LITE_RENDERER`` names, else vispy.

    Attributes
    ----------
    backend : CanvasBackend
        The renderer, made with ``gui=None``.
    """

    def __init__(
        self,
        viewer: ViewerModel,
        *,
        renderer: str | Callable[..., CanvasBackend] = 'default',
    ) -> None:
        self.viewer = viewer
        self.backend: CanvasBackend = resolve_renderer(renderer)(
            viewer, gui=None
        )

    def screenshot(
        self,
        path: str | None = None,
        *,
        size: tuple[int, int] | None = None,
        scale: float | None = None,
        fit_to_data_extent: bool = False,
    ) -> np.ndarray:
        """The canvas as an RGBA array (and saved to ``path`` if given);
        ``size`` is (height, width) in pixels, by default the canvas's."""
        img = self.backend.screenshot(
            size=size,
            scale=1.0 if scale is None else scale,
            fit_to_data_extent=fit_to_data_extent,
        )
        if path is not None:
            imsave(str(path), img)
        return img

    def export_figure(
        self, path: str | None = None, *, scale: float = 1.0
    ) -> np.ndarray:
        """Screenshot tightly fitted around the data, one pixel per data
        pixel (times ``scale``)."""
        return self.screenshot(path, scale=scale, fit_to_data_extent=True)

    def close(self) -> None:
        """Release the canvas."""
        self.backend.close()
