# napari-lite: own code
"""Show a viewer screenshot in a Jupyter notebook.

Same API as ``napari.utils.notebook_display``; the alt text is escaped
with the standard library instead of being cleaned with lxml, which keeps
lxml out of the dependencies.
"""

from __future__ import annotations

import base64
import html
from io import BytesIO
from typing import TYPE_CHECKING

from napari_lite.utils.io import imsave_png

if TYPE_CHECKING:
    import numpy as np

    from napari_lite.viewer import Viewer

__all__ = ['NotebookScreenshot', 'nbscreenshot']


class NotebookScreenshot:
    """Rich display object: a PNG screenshot of the viewer.

    Jupyter shows an object with a ``_repr_png_`` method as an image, so
    returning one from a cell displays the screenshot.

    Parameters
    ----------
    viewer : Viewer
        The viewer.
    canvas_only : bool, optional
        Only the canvas (True) or the whole window (False, default).
    alt_text : str, optional
        Alternative text for the image, for screen readers.  Any markup in
        it is escaped.
    """

    def __init__(
        self,
        viewer: Viewer,
        *,
        canvas_only: bool = False,
        alt_text: str | None = None,
    ) -> None:
        self.viewer = viewer
        self.canvas_only = canvas_only
        self.image: np.ndarray | None = None
        self.alt_text = self._clean_alt_text(alt_text)

    @staticmethod
    def _clean_alt_text(alt_text: str | None) -> str | None:
        """Plain text only: unescape first so escaped markup cannot slip
        through, then let ``html.escape`` do the work when rendering."""
        if alt_text is None:
            return None
        text = html.unescape(str(alt_text)).strip()
        return text or None

    def _repr_png_(self) -> bytes:
        """The screenshot as PNG bytes (for IPython)."""
        from napari_lite._qt.qt_event_loop import get_qapp

        get_qapp().processEvents()
        self.image = self.viewer.screenshot(
            canvas_only=self.canvas_only, flash=False
        )
        with BytesIO() as file_obj:
            imsave_png(file_obj, self.image)
            file_obj.seek(0)
            return file_obj.read()

    def _repr_html_(self) -> str:
        png = self._repr_png_()
        url = 'data:image/png;base64,' + base64.b64encode(png).decode('utf-8')
        alt = html.escape(self.alt_text, quote=True) if self.alt_text else ''
        return f'<img src="{url}" alt="{alt}"></img>'


def nbscreenshot(
    viewer: Viewer,
    *,
    canvas_only: bool = False,
    alt_text: str | None = None,
) -> NotebookScreenshot:
    """Return a rich display object with a screenshot of ``viewer``.

    Examples
    --------
    >>> import napari_lite
    >>> from napari_lite.utils import nbscreenshot
    >>> viewer, layer = napari_lite.imshow(image)
    >>> nbscreenshot(viewer, canvas_only=True)
    """
    return NotebookScreenshot(
        viewer, canvas_only=canvas_only, alt_text=alt_text
    )
