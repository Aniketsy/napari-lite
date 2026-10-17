# napari-lite: own code
"""The two lookups of the Tracks layer in numpy.

``TrackManager`` (layers/tracks/_track_utils.py) built a ``cKDTree`` of the
track vertices to find the ones nearest to the cursor, and a sparse matrix
to map a track id to its vertex indices.  Those were the Tracks layer's
only uses of scipy.  :class:`NearestVertices` answers the same ``query``
by distance over all vertices (a few milliseconds for a million of them),
:class:`IdIndex` answers the same lookup from a sorted index.
``tests/test_tracks_index.py`` compares both with scipy.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt


class NearestVertices:
    """The ``query`` of ``scipy.spatial.cKDTree`` that napari uses."""

    def __init__(self, points: npt.ArrayLike) -> None:
        self.points = np.asarray(points, dtype=np.float64)
        self.n = len(self.points)

    def query(
        self, x: npt.ArrayLike, k: int = 1
    ) -> tuple[np.floating | np.ndarray, np.integer | np.ndarray]:
        """Distances and indices of the ``k`` vertices nearest to ``x``,
        nearest first.  As with ``cKDTree``, missing neighbours (``k``
        larger than the number of vertices) come back with an infinite
        distance and the index ``len(points)``, and ``k=1`` returns scalars.
        """
        point = np.asarray(x, dtype=np.float64)
        distances = np.sqrt(((self.points - point) ** 2).sum(axis=1))
        found = min(k, self.n)
        order = np.argsort(distances, kind='stable')[:found]
        d = np.full(k, np.inf)
        idx = np.full(k, self.n, dtype=np.intp)
        d[:found] = distances[order]
        idx[:found] = order
        if k == 1:
            return d[0], idx[0]
        return d, idx


class IdIndex:
    """Vertex indices of every track id, as the rows of napari's sparse
    ``id -> vertex`` matrix listed them."""

    def __init__(self, track_ids: npt.ArrayLike) -> None:
        ids = np.asarray(track_ids)
        self._order = np.argsort(ids, kind='stable')
        self._sorted = ids[self._order]

    def __getitem__(self, track_id: int) -> npt.NDArray[np.intp]:
        lo = np.searchsorted(self._sorted, track_id, side='left')
        hi = np.searchsorted(self._sorted, track_id, side='right')
        return np.sort(self._order[lo:hi]).astype(np.intp)
