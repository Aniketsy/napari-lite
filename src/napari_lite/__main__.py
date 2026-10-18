# napari-lite: own code
"""The ``napari-lite`` command: open a viewer, optionally with files.

    napari-lite                       # an empty viewer
    napari-lite image.png stack.tif   # one image layer per file
    napari-lite cells.npy --labels    # a .npy file as a Labels layer
    napari-lite --sample astronaut    # a built-in sample
    python -m napari_lite ...         # the same

napari-lite has no plugins, so this reads what its built-in reader reads
(``napari_lite.plugins.io``): images through imageio, ``.npy``/``.npz``
through numpy and TIFF through tifffile when it is installed (the ``tiff``
extra), imageio otherwise.  Anything else: load it in Python and call
``add_image``.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING, Any

from napari_lite.plugins.io import read_array
from napari_lite.plugins.samples import SAMPLES

if TYPE_CHECKING:
    from napari_lite.viewer import Viewer

__all__ = ['cli', 'load', 'main']


def load(path: str | Path) -> Any:
    """Read ``path`` with the built-in reader: an array, or a list of
    ``(name, array)`` pairs for an ``.npz``."""
    return read_array(path)


def main(argv: list[str] | None = None, *, run: bool = True) -> Viewer:
    """Parse ``argv``, open the viewer, start the event loop (unless
    ``run`` is False) and return the viewer.

    A file that does not exist or that no reader can open ends the program
    with a message and exit status 2, before any window opens.
    """
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
        '--sample',
        choices=list(SAMPLES),
        metavar='NAME',
        help='open a built-in sample: ' + ', '.join(SAMPLES),
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

    loaded: list[tuple[str, Any]] = []
    for path in args.paths:
        try:
            loaded.append((Path(path).stem, load(path)))
        except FileNotFoundError:
            parser.error(f'no such file: {path}')
        except (OSError, ValueError) as exc:
            # how imageio, numpy and tifffile report a file they cannot read
            parser.error(f'cannot read {path}: {exc}')

    import napari_lite

    viewer = napari_lite.Viewer(title=args.title, ndisplay=args.ndisplay)
    for name, data in loaded:
        arrays = data if isinstance(data, list) else [(None, data)]
        for key, array in arrays:
            layer_name = name if key is None else f'{name}[{key}]'
            if args.labels:
                viewer.add_labels(array, name=layer_name)
            else:
                viewer.add_image(array, name=layer_name)
    if args.sample:
        viewer.open_sample('napari-lite', args.sample)
    if loaded or args.sample:
        viewer.reset_view()
    if run:
        napari_lite.run()
    return viewer


def cli(argv: list[str] | None = None) -> None:
    """The ``napari-lite`` command: ``main`` without the returned viewer,
    so that the console-script wrapper's ``sys.exit`` reports success."""
    main(argv)


if __name__ == '__main__':
    cli()
