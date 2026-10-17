# napari-lite: own code
"""The ``napari-lite`` command: open a viewer, optionally with files.

    napari-lite                       # an empty viewer
    napari-lite image.png stack.tif   # one image layer per file
    napari-lite cells.npy --labels    # a .npy file as a Labels layer
    python -m napari_lite ...         # the same

napari-lite has no plugins, so this reads only what its own dependencies
can: images through imageio, ``.npy``/``.npz`` through numpy and TIFF
through tifffile when it is installed (the ``tiff`` extra), imageio
otherwise.  Anything else: load it in Python and call ``add_image``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from napari_lite.viewer import Viewer

__all__ = ['load', 'main']


def load(path: str | Path) -> Any:
    """Read ``path`` into an array with numpy, tifffile or imageio."""
    path = Path(path)
    suffix = path.suffix.lower()
    if not path.exists():
        raise FileNotFoundError(path)
    if suffix == '.npy':
        import numpy as np

        return np.load(path)
    if suffix == '.npz':
        import numpy as np

        with np.load(path) as archive:
            return [archive[k] for k in archive.files]
    if suffix in {'.tif', '.tiff'}:
        try:
            import tifffile
        except ImportError:
            pass
        else:
            return tifffile.imread(path)
    import imageio.v3 as iio

    return iio.imread(path)


def main(argv: list[str] | None = None, *, run: bool = True) -> Viewer:
    """Parse ``argv``, open the viewer, start the event loop (unless
    ``run`` is False) and return the viewer."""
    parser = argparse.ArgumentParser(
        prog='napari-lite',
        description='Open a napari-lite viewer, optionally with files.',
        epilog='Supported files: images (imageio), .npy/.npz (numpy), '
        'TIFF (tifffile when installed).',
    )
    parser.add_argument('paths', nargs='*', help='files to show')
    parser.add_argument(
        '--labels', action='store_true', help='show the files as Labels'
    )
    parser.add_argument(
        '--ndisplay',
        type=int,
        choices=(2, 3),
        default=2,
        help='start in 2D (default) or 3D',
    )
    parser.add_argument('--title', default='napari-lite', help='window title')
    args = parser.parse_args(argv)

    import napari_lite

    viewer = napari_lite.Viewer(title=args.title, ndisplay=args.ndisplay)
    for path in args.paths:
        data = load(path)
        name = Path(path).stem
        if args.labels:
            viewer.add_labels(data, name=name)
        elif isinstance(data, list):
            for i, item in enumerate(data):
                viewer.add_image(item, name=f'{name}[{i}]')
        else:
            viewer.add_image(data, name=name)
    if args.paths:
        viewer.reset_view()
    if run:
        napari_lite.run()
    return viewer


if __name__ == '__main__':
    sys.exit(0 if main() else 1)
