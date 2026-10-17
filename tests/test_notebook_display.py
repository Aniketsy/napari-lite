# napari-lite: own code
"""nbscreenshot renders a viewer as PNG for Jupyter, without lxml."""

from __future__ import annotations

import base64

import numpy as np
import pytest


@pytest.fixture
def viewer(qtbot):
    from napari_lite import Viewer

    v = Viewer(show=False)
    v.add_image(np.random.random((16, 16)))
    yield v
    v.close()


def test_nbscreenshot_png(viewer) -> None:
    from napari_lite.utils import nbscreenshot

    shot = nbscreenshot(viewer, canvas_only=True)
    png = shot._repr_png_()
    assert png[:8] == b'\x89PNG\r\n\x1a\n'
    assert shot.image is not None
    assert shot.image.shape[-1] == 4


def test_nbscreenshot_html_escapes_alt_text(viewer) -> None:
    from napari_lite.utils.notebook_display import NotebookScreenshot

    shot = NotebookScreenshot(
        viewer, canvas_only=True, alt_text='<script>alert(1)</script> a cat'
    )
    html_text = shot._repr_html_()
    assert '<script>' not in html_text
    assert '&lt;script&gt;' in html_text
    assert 'a cat' in html_text
    payload = html_text.split('base64,', 1)[1].split('"', 1)[0]
    assert base64.b64decode(payload)[:4] == b'\x89PNG'


def test_empty_alt_text_is_dropped(viewer) -> None:
    from napari_lite.utils.notebook_display import NotebookScreenshot

    assert NotebookScreenshot(viewer, alt_text='   ').alt_text is None
    assert NotebookScreenshot(viewer).alt_text is None
