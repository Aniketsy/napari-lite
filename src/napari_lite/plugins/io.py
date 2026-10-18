# napari-lite: own code
"""The built-in reader behind ``viewer.open`` (and the command line), and
the writers napari-lite does not have.

Images go through imageio, ``.npy``/``.npz`` through numpy and TIFF through
tifffile when it is installed (the ``tiff`` extra), imageio otherwise.
Every file becomes an image layer (``viewer.open(..., layer_type='labels')``
makes Labels); an ``.npz`` gives one layer per array; ``stack=True`` makes
one layer of the arrays of all the paths.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from napari_lite.plugins import (
    NO_WRITERS,
    READER,
    is_readable,
    no_plugins,
    no_readers,
)

LayerData = tuple[Any, dict[str, Any], str]


def read_array(path: str | Path) -> Any:
    """Read one file: an array, or a list of ``(name, array)`` pairs for
    an ``.npz``."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    suffix = path.suffix.lower()
    if suffix == '.npy':
        import numpy as np

        return np.load(path)
    if suffix == '.npz':
        import numpy as np

        with np.load(path) as archive:
            return [(key, archive[key]) for key in archive.files]
    if suffix in {'.tif', '.tiff'}:
        try:
            import tifffile
        except ImportError:
            pass
        else:
            return tifffile.imread(path)
    import imageio.v3 as iio

    return iio.imread(path)


def read_file(path: str | Path) -> list[LayerData]:
    """The layer data tuples of one file: image layers, named after the
    file by the viewer (the arrays of an ``.npz`` after the file and their
    keys)."""
    loaded = read_array(path)
    if isinstance(loaded, list):
        stem = Path(path).stem
        return [
            (array, {'name': f'{stem}[{key}]'}, 'image')
            for key, array in loaded
        ]
    return [(loaded, {}, 'image')]


def read_data_with_plugins(
    paths: Any, plugin: str | None = None, stack: bool = False
) -> tuple[list[LayerData], str]:
    """What ``ViewerModel._add_layers_with_plugins`` calls: the layer data
    of ``paths`` and the reader's name.

    With ``stack`` the arrays of all the paths become one layer (their
    shapes must agree); otherwise every file gives its own layers.
    """
    if plugin not in (None, READER, 'napari'):
        raise no_plugins(
            f'napari-lite has no plugins; its reader is {READER!r}.', plugin
        )
    paths = [str(p) for p in paths]
    unreadable = [p for p in paths if not is_readable(p)]
    if unreadable:
        raise no_readers(unreadable)
    if stack and len(paths) > 1:
        import numpy as np

        arrays = []
        for path in paths:
            loaded = read_array(path)
            if isinstance(loaded, list):
                arrays.extend(array for _key, array in loaded)
            else:
                arrays.append(loaded)
        shapes = {array.shape for array in arrays}
        if len(shapes) != 1:
            raise ValueError(
                f'cannot stack {len(arrays)} arrays of different shapes: '
                f'{sorted(shapes)}'
            )
        return [(np.stack(arrays), {}, 'image')], READER
    layer_data: list[LayerData] = []
    for path in paths:
        layer_data.extend(read_file(path))
    return layer_data, READER


def save_layers(path: Any = None, *args: Any, **kwargs: Any) -> Any:
    raise no_plugins(NO_WRITERS, path)
