# napari-lite: own code
"""A viewer without a window: ``Viewer(gui=None)`` (issue 5,
docs/backends.md).

The renderer draws into a canvas nobody shows; ``screenshot`` and
``export_figure`` give the pictures.  On Linux vispy's ``egl`` or
``osmesa`` application draws with no Qt in the process; elsewhere (and
on Linux without those libraries) the Qt binding draws into a widget
kept off the screen, so Qt is imported but no window appears.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from napari_lite._vispy._qt_optional import use_vispy_app, vispy_app_is_qt
from napari_lite.utils.io import imsave

if TYPE_CHECKING:
    import numpy as np

    from napari_lite._vispy.backend import VispyBackend
    from napari_lite.components import ViewerModel

__all__ = ['HeadlessCanvas']


class HeadlessCanvas:
    """The canvas of a viewer that has no window.

    Parameters
    ----------
    viewer : ViewerModel
        The model to draw.

    Attributes
    ----------
    app_name : str
        vispy's application backend: 'egl' or 'osmesa', or the Qt binding
        when the widget off the screen is the way to draw here.
    uses_qt : bool
        Whether that is a Qt binding.
    backend : VispyBackend
        The renderer.
    """

    def __init__(self, viewer: ViewerModel) -> None:
        self.viewer = viewer
        self.app_name = use_vispy_app('offscreen')
        self.uses_qt = vispy_app_is_qt()
        if self.uses_qt:
            from napari_lite._qt.qt_event_loop import get_qapp

            get_qapp()  # the widget needs the application to exist
        from napari_lite._vispy.backend import VispyBackend

        self.backend: VispyBackend = VispyBackend(viewer)
        if self.uses_qt:
            # a Qt widget draws once it is shown: shown off the screen, it
            # has its GL context and no window appears anywhere
            from qtpy.QtCore import Qt

            native = self.backend.native
            native.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
            native.show()

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
        if self.uses_qt:
            self.backend.native.hide()
        self.backend.close()
