# napari-lite: own code
"""Grey-value dilation and erosion with symmetric footprints, in numpy.

``get_contours`` (layers/labels/_labels_utils.py) keeps the pixels where a
dilation and an erosion of the labels differ.  It used four functions of
``scipy.ndimage`` for that, with scipy's default ``'reflect'`` border; the
same four live here for the footprints it builds, a cross and the diamonds
grown from it, which are symmetric.  A dilation is the maximum, and an
erosion the minimum, over the input shifted by every offset of the
footprint.  ``tests/test_morphology.py`` compares them with scipy.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

BoolArray = npt.NDArray[np.bool_]


def generate_binary_structure(rank: int, connectivity: int) -> BoolArray:
    """The ``(3,) * rank`` structuring element of the given connectivity,
    as ``scipy.ndimage.generate_binary_structure``."""
    connectivity = max(connectivity, 1)
    if rank < 1:
        return np.array(True, dtype=bool)
    distance = np.abs(np.indices((3,) * rank) - 1).sum(axis=0)
    return distance <= connectivity


def _offsets(footprint: npt.ArrayLike) -> npt.NDArray[np.intp]:
    footprint = np.asarray(footprint, dtype=bool)
    centre = np.array([s // 2 for s in footprint.shape])
    if not np.array_equal(
        footprint, footprint[(slice(None, None, -1),) * footprint.ndim]
    ):
        raise ValueError('only symmetric footprints are supported')
    return np.argwhere(footprint) - centre


def _binary_dilation(image: BoolArray, structure: npt.ArrayLike) -> BoolArray:
    out = image.copy()
    for offset in _offsets(structure):
        shifted = np.zeros_like(image)
        src = tuple(
            slice(max(0, -o), image.shape[axis] - max(0, o))
            for axis, o in enumerate(offset)
        )
        dst = tuple(
            slice(max(0, o), image.shape[axis] - max(0, -o))
            for axis, o in enumerate(offset)
        )
        shifted[dst] = image[src]
        out |= shifted
    return out


def iterate_structure(structure: npt.ArrayLike, iterations: int) -> BoolArray:
    """``structure`` dilated with itself ``iterations - 1`` times, as
    ``scipy.ndimage.iterate_structure`` without an origin."""
    structure = np.asarray(structure, dtype=bool)
    if iterations < 2:
        return structure.copy()
    grow = iterations - 1
    out = np.zeros([s + 2 * grow for s in structure.shape], dtype=bool)
    out[
        tuple(
            slice(grow * (s // 2), grow * (s // 2) + s)
            for s in structure.shape
        )
    ] = structure
    for _ in range(grow):
        out = _binary_dilation(out, structure)
    return out


def _filter(
    image: npt.ArrayLike, footprint: npt.ArrayLike, reduce
) -> np.ndarray:
    image = np.asarray(image)
    offsets = _offsets(footprint)
    reach = np.abs(offsets).max(axis=0)
    # scipy's 'reflect' border repeats the edge pixel: numpy's 'symmetric'
    padded = np.pad(image, [(int(r), int(r)) for r in reach], mode='symmetric')
    out = None
    for offset in offsets:
        window = padded[
            tuple(
                slice(int(r + o), int(r + o) + n)
                for r, o, n in zip(reach, offset, image.shape, strict=True)
            )
        ]
        out = window.copy() if out is None else reduce(out, window, out=out)
    return out


def grey_dilation(
    image: npt.ArrayLike, footprint: npt.ArrayLike
) -> np.ndarray:
    """``scipy.ndimage.grey_dilation(image, footprint=footprint)`` for a
    symmetric footprint, with the reflecting border scipy defaults to."""
    return _filter(image, footprint, np.maximum)


def grey_erosion(image: npt.ArrayLike, footprint: npt.ArrayLike) -> np.ndarray:
    """``scipy.ndimage.grey_erosion(image, footprint=footprint)`` for a
    symmetric footprint, with the reflecting border scipy defaults to."""
    return _filter(image, footprint, np.minimum)
