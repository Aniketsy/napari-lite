# napari-lite: own code
"""utils/_tracks_index.py against scipy's cKDTree and sparse matrix, as
the Tracks layer used them."""

from __future__ import annotations

import numpy as np
import pytest

from napari_lite.utils._tracks_index import IdIndex, NearestVertices

spatial = pytest.importorskip('scipy.spatial')
sparse = pytest.importorskip('scipy.sparse')


@pytest.mark.parametrize('seed', range(10))
def test_query_matches_ckdtree(seed) -> None:
    rng = np.random.default_rng(seed)
    points = rng.uniform(0, 100, (300, 3)).round(1)
    tree = spatial.cKDTree(points)
    ours = NearestVertices(points)
    for _ in range(20):
        x = rng.uniform(0, 100, 3)
        d_ref, i_ref = tree.query(x, k=10)
        d, i = ours.query(x, k=10)
        np.testing.assert_allclose(d, d_ref, rtol=1e-12)
        # the same vertices; ties (equal distances) may come in any order
        assert set(i.tolist()) == set(i_ref.tolist())


def test_query_more_neighbours_than_vertices_and_k_one() -> None:
    points = np.array([[0.0, 0.0], [3.0, 4.0], [6.0, 8.0]])
    tree = spatial.cKDTree(points)
    ours = NearestVertices(points)
    d_ref, i_ref = tree.query([0.0, 1.0], k=5)
    d, i = ours.query([0.0, 1.0], k=5)
    np.testing.assert_allclose(d, d_ref)
    np.testing.assert_array_equal(i, i_ref)  # padded with len(points)
    d1, i1 = ours.query([6.0, 7.0], k=1)
    assert np.isscalar(d1) and np.isscalar(i1)
    assert (d1, i1) == tree.query([6.0, 7.0], k=1)


def test_id_index_matches_sparse_rows() -> None:
    rng = np.random.default_rng(1)
    track_ids = rng.integers(0, 12, 200).astype(np.uint32)
    csr = sparse.coo_matrix(
        (
            np.broadcast_to(1, track_ids.size),
            (track_ids, np.arange(track_ids.size)),
        )
    ).tocsr()
    index = IdIndex(track_ids)
    for track_id in np.unique(track_ids):
        np.testing.assert_array_equal(
            index[int(track_id)], csr[int(track_id)].nonzero()[1]
        )
    assert index[999].size == 0


def test_tracks_layer_value_lookup() -> None:
    """The layer's nearest-track lookup, which was the KD-tree's job."""
    from napari_lite.layers import Tracks

    data = np.array(
        [[0, 0, 10.0, 10.0], [0, 1, 11.0, 12.0], [1, 0, 50.0, 50.0]]
    )
    layer = Tracks(data)
    manager = layer._manager
    assert manager.get_value(np.array([1.0, 11.2, 12.1])) == 0
    assert manager.get_value(np.array([0.0, 49.0, 51.0])) == 1
    np.testing.assert_array_equal(manager._vertex_indices_from_id(0), [0, 1])
