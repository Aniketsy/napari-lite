# napari-lite: own code
"""The ``napari-lite`` command: open a viewer, optionally with files.

    napari-lite                       # an empty viewer
    napari-lite image.png stack.tif   # one image layer per file
    napari-lite cells.npy --labels    # a .npy file as a Labels layer
    napari-lite --sample astronaut    # a built-in sample
    napari-lite --view stack.tif      # the view-only canvas: look, no editing
    napari-lite --view image.png --points spots.csv   # with points over it
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
from typing import Any

from napari_lite.plugins.io import read_array
from napari_lite.plugins.samples import SAMPLES

__all__ = ['cli', 'load', 'load_points', 'main']


def load(path: str | Path) -> Any:
    """Read ``path`` with the built-in reader: an array, or a list of
    ``(name, array)`` pairs for an ``.npz``."""
    return read_array(path)


def load_points(path: str | Path) -> Any:
    """Read point coordinates, one point per row: ``.npy``/``.npz``
    through numpy, ``.csv``/``.txt`` as comma-separated numbers with an
    optional header line."""
    import numpy as np

    path = Path(path)
    if path.suffix.lower() in ('.npy', '.npz'):
        data = read_array(path)
        coords = data[0][1] if isinstance(data, list) else data
    else:
        try:
            coords = np.loadtxt(path, delimiter=',', ndmin=2)
        except ValueError:  # a header line
            coords = np.loadtxt(path, delimiter=',', ndmin=2, skiprows=1)
    coords = np.asarray(coords, dtype=float)
    if coords.ndim != 2 or coords.shape[1] < 2:
        raise ValueError(
            f'{path}: points need one row per point with at least two '
            f'coordinates, got shape {coords.shape}'
        )
    return coords


def main(argv: list[str] | None = None, *, run: bool = True) -> Any:
    """Parse ``argv``, open the viewer, start the event loop (unless
    ``run`` is False) and return the viewer (with ``--view``: the
    ``QtView`` widget of the view-only canvas).

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
    parser.add_argument(
        '--view',
        action='store_true',
        help='the view-only canvas instead of the viewer: images and '
        'points, contrast, colormap, zoom and slicing, no editing',
    )
    parser.add_argument(
        '--points',
        metavar='FILE',
        help='points to draw over the images, one per row (.npy, .csv)',
    )
    args = parser.parse_args(argv)
    if args.view and args.labels:
        parser.error('--labels is not available with --view')
    if args.view and args.ndisplay != 2:
        parser.error('the view-only canvas is 2D')

    loaded: list[tuple[str, Any]] = []
    for path in args.paths:
        try:
            loaded.append((Path(path).stem, load(path)))
        except FileNotFoundError:
            parser.error(f'no such file: {path}')
        except (OSError, ValueError) as exc:
            # how imageio, numpy and tifffile report a file they cannot read
            parser.error(f'cannot read {path}: {exc}')

    points = None
    if args.points:
        try:
            points = load_points(args.points)
        except FileNotFoundError:
            parser.error(f'no such file: {args.points}')
        except (OSError, ValueError) as exc:
            parser.error(f'cannot read {args.points}: {exc}')

    import napari_lite

    if args.view:
        widget = _view(args, loaded, points)
        if run:
            napari_lite.run()
        return widget

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
    if points is not None:
        viewer.add_points(points, name=Path(args.points).stem)
    if loaded or args.sample:
        viewer.reset_view()
    if run:
        napari_lite.run()
    return viewer


def _view(args: argparse.Namespace, loaded: list, points: Any) -> Any:
    """The ``--view`` window: every array as an image item (a uint8 array
    with 3 or 4 entries in its last axis as RGB), the points over them."""
    from napari_lite.view import QtView, View, _qt

    view = View()
    arrays = []
    for name, data in loaded:
        for key, array in data if isinstance(data, list) else [(None, data)]:
            arrays.append((name if key is None else f'{name}[{key}]', array))
    if args.sample:
        for array, kwargs, _ in SAMPLES[args.sample].load():
            arrays.append((kwargs.get('name', args.sample), array))
    for name, array in arrays:
        rgb = (
            array.ndim == 3
            and array.shape[-1] in (3, 4)
            and array.dtype == 'uint8'
        )
        view.add_image(array, name=name, rgb=rgb)
    if points is not None:
        view.add_points(points, name=Path(args.points).stem)
    widget = QtView(view)
    widget.setWindowTitle(args.title)
    widget.resize(800, 640)
    _qt._windows.append(widget)  # kept alive, as show() does
    widget.show()
    return widget


def cli(argv: list[str] | None = None) -> None:
    """The ``napari-lite`` command: ``main`` without the returned viewer,
    so that the console-script wrapper's ``sys.exit`` reports success."""
    main(argv)


if __name__ == '__main__':
    cli()
