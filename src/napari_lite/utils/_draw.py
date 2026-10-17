# napari-lite: own code
"""Rasterization in numpy: the four scikit-image functions the copied code
used.

napari calls ``skimage.draw.line`` and ``skimage.draw.polygon`` for the
masks and labels made from Shapes, ``skimage.measure.points_in_poly`` to
cull the triangles outside a polygon, and ``skimage.segmentation.flood``
for the fill tool of Labels.  scikit-image was a 43 MB dependency
(networkx and tifffile come with it) for those four calls.  The functions
here take the same arguments and return the same pixels in the same order;
``tests/test_draw.py`` compares them with scikit-image where it is
installed.

The algorithms are the ones scikit-image uses (version 0.26): Bresenham's
line; O'Rourke's ray test for a point against a polygon, which tells
outside, inside, on a vertex and on an edge apart and counts the last three
as in (run over the polygon's bounding box for :func:`polygon`); and a
breadth-first flood fill.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import numpy.typing as npt

IntArray = npt.NDArray[np.intp]
FloatArray = npt.NDArray[np.float64]

# O'Rourke, Computational Geometry in C, chapter 7, as in scikit-image's
# ``_shared/geometry.pyx``: the point classification and its tolerance
OUTSIDE, INSIDE, VERTEX, EDGE = 0, 1, 2, 3
VERTEX_EPS = 1e-12


def line(r0: int, c0: int, r1: int, c1: int) -> tuple[IntArray, IntArray]:
    """Row and column indices of the pixels of a line, both ends included.

    The same pixels as ``skimage.draw.line``.
    """
    r0, c0, r1, c1 = int(r0), int(c0), int(r1), int(c1)
    r, c = r0, c0
    dr, dc = abs(r1 - r0), abs(c1 - c0)
    sr = 1 if r1 > r0 else -1
    sc = 1 if c1 > c0 else -1
    steep = dr > dc
    if steep:
        r, c = c, r
        dr, dc = dc, dr
        sr, sc = sc, sr
    d = 2 * dr - dc
    rr = np.empty(dc + 1, dtype=np.intp)
    cc = np.empty(dc + 1, dtype=np.intp)
    for i in range(dc):
        if steep:
            rr[i], cc[i] = c, r
        else:
            rr[i], cc[i] = r, c
        while d >= 0:
            r += sr
            d -= 2 * dc
        c += sc
        d += 2 * dr
    rr[dc], cc[dc] = r1, c1
    return rr, cc


def _classify(
    x: FloatArray, y: FloatArray, xp: FloatArray, yp: FloatArray
) -> npt.NDArray[np.uint8]:
    """OUTSIDE, INSIDE, VERTEX or EDGE for every point ``(x, y)`` against
    the polygon ``(xp, yp)``, in scikit-image's arithmetic.

    Two rays leave each point along the x axis, one to each side; an edge
    straddling the axis counts for the side its crossing lies on.  Odd
    crossings on the right mean inside; different parities on the two
    sides mean the point sits on an edge.
    """
    r_cross = np.zeros(np.shape(x), dtype=np.intp)
    l_cross = np.zeros(np.shape(x), dtype=np.intp)
    on_vertex = np.zeros(np.shape(x), dtype=bool)
    x1, y1 = xp[-1] - x, yp[-1] - y
    for i in range(len(xp)):
        x0, y0 = xp[i] - x, yp[i] - y
        on_vertex |= (np.abs(x0) < VERTEX_EPS) & (np.abs(y0) < VERTEX_EPS)
        # the crossing is only read where an edge straddles the axis, and
        # there y1 - y0 is not zero
        with np.errstate(divide='ignore', invalid='ignore'):
            crossing = (x0 * y1 - x1 * y0) / (y1 - y0)
        r_cross += ((y0 > 0) != (y1 > 0)) & (crossing > 0)
        l_cross += ((y0 < 0) != (y1 < 0)) & (crossing < 0)
        x1, y1 = x0, y0
    on_edge = (r_cross & 1) != (l_cross & 1)
    inside = (r_cross & 1).astype(bool)
    codes = np.where(inside, INSIDE, OUTSIDE).astype(np.uint8)
    codes[on_edge] = EDGE
    codes[on_vertex] = VERTEX
    return codes


def polygon(
    r: npt.ArrayLike, c: npt.ArrayLike, shape: Sequence[int] | None = None
) -> tuple[IntArray, IntArray]:
    """Row and column indices of the pixels inside a polygon, boundary
    included.

    The same pixels, in the same order, as ``skimage.draw.polygon``: every
    integer position of the polygon's bounding box, clipped to ``shape``
    when given, that is inside the polygon or on its boundary.
    """
    r = np.atleast_1d(np.asarray(r, dtype=np.float64))
    c = np.atleast_1d(np.asarray(c, dtype=np.float64))
    if r.size != c.size:
        raise ValueError('`r` and `c` must have the same size.')
    min_r, min_c = int(max(0, r.min())), int(max(0, c.min()))
    max_r, max_c = int(np.ceil(r.max())), int(np.ceil(c.max()))
    if shape is not None:
        max_r, max_c = min(shape[0] - 1, max_r), min(shape[1] - 1, max_c)
    rows = np.arange(min_r, max_r + 1, dtype=np.float64)
    cols = np.arange(min_c, max_c + 1, dtype=np.float64)
    if rows.size == 0 or cols.size == 0:
        return np.empty(0, dtype=np.intp), np.empty(0, dtype=np.intp)
    grid_r, grid_c = np.meshgrid(rows, cols, indexing='ij')
    keep = _classify(grid_c, grid_r, c, r) != OUTSIDE
    return grid_r[keep].astype(np.intp), grid_c[keep].astype(np.intp)


def points_in_poly(
    points: npt.ArrayLike, verts: npt.ArrayLike
) -> npt.NDArray[np.bool_]:
    """Which of the ``(K, 2)`` points lie inside the ``(L, 2)`` polygon or
    on its boundary.

    The same answer as ``skimage.measure.points_in_poly``.
    """
    points = np.asarray(points, dtype=np.float64)
    verts = np.asarray(verts, dtype=np.float64)
    codes = _classify(points[:, 0], points[:, 1], verts[:, 0], verts[:, 1])
    return codes != OUTSIDE


def _neighbour_offsets(
    ndim: int, connectivity: int | None, footprint: npt.ArrayLike | None
) -> IntArray:
    if footprint is not None:
        footprint = np.asarray(footprint, dtype=bool)
        centre = np.array([s // 2 for s in footprint.shape])
        offsets = np.argwhere(footprint) - centre
    else:
        if connectivity is None:
            connectivity = ndim
        grid = np.indices((3,) * ndim).reshape(ndim, -1).T - 1
        offsets = grid[np.abs(grid).sum(axis=1) <= connectivity]
    return offsets[np.any(offsets != 0, axis=1)].astype(np.intp)


def flood(
    image: npt.ArrayLike,
    seed_point: int | Sequence[int],
    *,
    footprint: npt.ArrayLike | None = None,
    connectivity: int | None = None,
    tolerance: float | None = None,
) -> npt.NDArray[np.bool_]:
    """Mask of the pixels connected to ``seed_point`` with its value.

    The same mask as ``skimage.segmentation.flood``: neighbours are the
    pixels within ``connectivity`` orthogonal steps (all of them by
    default), or the non-zero offsets of ``footprint``; with ``tolerance``
    a pixel counts when its value lies within the tolerance of the seed's,
    inclusive.
    """
    image = np.asarray(image)
    if image.ndim == 0:
        return np.ones((), dtype=bool)
    seed = tuple(int(i) for i in np.atleast_1d(seed_point))
    seed_value = image[seed]
    if tolerance is None:
        candidates = image == seed_value
    else:
        candidates = (image >= seed_value - tolerance) & (
            image <= seed_value + tolerance
        )
    offsets = _neighbour_offsets(image.ndim, connectivity, footprint)
    filled = np.zeros(image.shape, dtype=bool)
    filled[seed] = True
    flat_candidates = candidates.ravel()
    flat_filled = filled.ravel()  # a view: filled is new and contiguous
    shape = np.array(image.shape)
    frontier = np.array([seed], dtype=np.intp)
    while frontier.size:
        around = (frontier[:, None, :] + offsets[None, :, :]).reshape(
            -1, image.ndim
        )
        around = around[np.all((around >= 0) & (around < shape), axis=1)]
        flat = np.unique(np.ravel_multi_index(around.T, image.shape))
        flat = flat[flat_candidates[flat] & ~flat_filled[flat]]
        flat_filled[flat] = True
        frontier = np.stack(np.unravel_index(flat, image.shape), axis=1)
    return filled
