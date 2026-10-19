# napari-lite: own code
"""Take the README's screenshot: napari's own README example, run with
napari-lite.

    python tools/readme_images.py

The example shows scikit-image's cells3d sample as two channels in 3D, so
scikit-image and pooch must be importable (they are not napari-lite
dependencies; napari's own README uses the same sample).  The window is
shown on screen and saved whole as docs/images/readme_viewer.png.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / 'docs' / 'images'


def pump(seconds: float) -> None:
    from qtpy.QtWidgets import QApplication

    app = QApplication.instance()
    end = time.perf_counter() + seconds
    while time.perf_counter() < end:
        app.processEvents()
        time.sleep(0.02)


def main() -> int:
    try:
        from skimage import data
    except ImportError:
        print(
            'scikit-image with pooch is needed for the cells3d sample',
            file=sys.stderr,
        )
        return 1
    import napari_lite as napari

    OUT.mkdir(parents=True, exist_ok=True)
    viewer, _layers = napari.imshow(
        data.cells3d(), channel_axis=1, ndisplay=3, title='napari-lite'
    )
    viewer.window.resize(1180, 780)
    pump(1.0)
    viewer.reset_view()  # fit the volume to the resized canvas
    pump(2.0)
    path = OUT / 'readme_viewer.png'
    viewer.screenshot(str(path), canvas_only=False)
    pump(0.5)
    viewer.close()
    print('wrote', path)
    return 0


if __name__ == '__main__':
    sys.exit(main())
