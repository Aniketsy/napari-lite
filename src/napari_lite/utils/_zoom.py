# napari-lite: own code
"""Nearest-neighbour zoom in numpy, for the layer thumbnails.

napari shrinks a slice to its 32x32 thumbnail with
``scipy.ndimage.zoom(..., order=0, prefilter=False)``.  The work is a pure
index lookup, but the import of ``scipy.ndimage`` behind it brings about
200 modules (``scipy.special`` among them) to the first image and to every
Labels or Image slice.  :func:`zoom` takes the same arguments and returns
the same array for ``order=0``: output index ``i`` reads input index
``round(i * (n_in - 1) / (n_out - 1))`` on every axis, which is scipy's
mapping without ``grid_mode``.

One difference on purpose: when floating-point error pushes the last
coordinate a hair past the last pixel, scipy's default ``mode='constant'``
fills that row or column with zeros; here the edge pixel is used (what
scipy's ``mode='nearest'`` does), which is what a thumbnail wants.
``tests/test_zoom.py`` compares the two.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
import numpy.typing as npt


def zoom(
    input: npt.ArrayLike,
    zoom: float | Sequence[float],
    output: None = None,
    order: int = 0,
    mode: str = 'constant',
    cval: float = 0.0,
    prefilter: bool = True,
    *,
    grid_mode: bool = False,
) -> npt.NDArray[Any]:
    """Zoom ``input`` by ``zoom`` with nearest-neighbour sampling.

    Same signature as ``scipy.ndimage.zoom``; only ``order=0`` without
    ``grid_mode`` and without a preallocated ``output`` is implemented.
    ``mode``, ``cval`` and ``prefilter`` are accepted so that call sites
    written for scipy work unchanged; see the module docstring for the one
    place where ``mode`` would have mattered.
    """
    if order != 0:
        raise NotImplementedError(
            'napari_lite.utils._zoom.zoom implements order=0 only'
        )
    if grid_mode or output is not None:
        raise NotImplementedError(
            'napari_lite.utils._zoom.zoom has no grid_mode and no output'
        )
    array = np.asarray(input)
    if array.ndim == 0:
        return array.copy()
    if np.isscalar(zoom):
        factors = (float(zoom),) * array.ndim  # type: ignore[arg-type]
    else:
        factors = tuple(float(f) for f in zoom)  # type: ignore[union-attr]
    if len(factors) != array.ndim:
        raise RuntimeError(
            f'zoom has {len(factors)} factors for {array.ndim} axes'
        )
    index: list[npt.NDArray[np.intp]] = []
    for n_in, factor in zip(array.shape, factors, strict=True):
        n_out = round(n_in * factor)
        # scipy maps output i to input i * (n_in - 1) / (n_out - 1) and
        # takes the nearest pixel, rounding halves up
        ratio = (n_in - 1) / (n_out - 1) if n_out > 1 else 1.0
        positions = np.floor(np.arange(n_out) * ratio + 0.5).astype(np.intp)
        index.append(np.clip(positions, 0, max(n_in - 1, 0)))
    return array[np.ix_(*index)]
