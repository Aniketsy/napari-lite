# napari-lite: own code
"""The numpy rasterization helpers in utils/_draw.py return what the
scikit-image functions they replace return: the same pixels in the same
order for lines and polygons, the same answers for points in a polygon,
the same masks for a flood fill."""

from __future__ import annotations

import numpy as np
import pytest

from napari_lite.utils import _draw

skimage_draw = pytest.importorskip('skimage.draw')
skimage_measure = pytest.importorskip('skimage.measure')
skimage_segmentation = pytest.importorskip('skimage.segmentation')


def assert_same_pixels(ours, theirs) -> None:
    for a, b in zip(ours, theirs, strict=True):
        assert a.dtype == b.dtype
        np.testing.assert_array_equal(a, b)


@pytest.mark.parametrize('seed', range(40))
def test_line(seed) -> None:
    rng = np.random.default_rng(seed)
    r0, c0, r1, c1 = rng.integers(-60, 60, size=4)
    assert_same_pixels(
        _draw.line(r0, c0, r1, c1), skimage_draw.line(r0, c0, r1, c1)
    )


@pytest.mark.parametrize(
    'ends',
    [(3, 3, 3, 3), (0, 0, 0, 9), (0, 0, 9, 0), (0, 0, 9, 9), (5, 1, 0, 7)],
)
def test_line_special_cases(ends) -> None:
    assert_same_pixels(_draw.line(*ends), skimage_draw.line(*ends))


@pytest.mark.parametrize('seed', range(40))
@pytest.mark.parametrize('shape', [None, (30, 40)])
def test_polygon(seed, shape) -> None:
    rng = np.random.default_rng(seed)
    n = rng.integers(3, 9)
    r = rng.uniform(-5, 45, n)
    c = rng.uniform(-5, 45, n)
    if seed % 3 == 0:  # the shapes layer rounds its vertices first
        r, c = np.round(r), np.round(c)
    assert_same_pixels(
        _draw.polygon(r, c, shape), skimage_draw.polygon(r, c, shape)
    )


def test_polygon_outside_the_shape_is_empty() -> None:
    rr, cc = _draw.polygon([50.0, 60.0, 60.0], [50.0, 50.0, 60.0], (30, 40))
    assert rr.size == 0 and cc.size == 0
    assert rr.dtype == np.intp


@pytest.mark.parametrize('seed', range(30))
def test_points_in_poly(seed) -> None:
    rng = np.random.default_rng(seed)
    verts = rng.uniform(0, 20, (rng.integers(3, 8), 2))
    points = rng.uniform(-2, 22, (200, 2))
    np.testing.assert_array_equal(
        _draw.points_in_poly(points, verts),
        skimage_measure.points_in_poly(points, verts),
    )


@pytest.mark.parametrize('seed', range(30))
def test_points_in_poly_on_the_boundary(seed) -> None:
    # vertices and edge midpoints exercise the boundary rule; integer
    # vertices keep the arithmetic exact: with arbitrary floats the answer
    # for a point exactly on an edge hangs on the last bit, and
    # scikit-image's own answer then differs between x86 and arm64 (fused
    # multiply-add), so it is no reference there
    rng = np.random.default_rng(seed)
    verts = rng.integers(0, 20, (rng.integers(3, 8), 2)).astype(np.float64)
    midpoints = (verts + np.roll(verts, 1, axis=0)) / 2
    boundary = np.concatenate([verts, midpoints])
    np.testing.assert_array_equal(
        _draw.points_in_poly(boundary, verts),
        skimage_measure.points_in_poly(boundary, verts),
    )


def test_points_in_poly_boundary_counts_as_inside() -> None:
    square = np.array([[0.0, 0.0], [0.0, 4.0], [4.0, 4.0], [4.0, 0.0]])
    on_it = [[0.0, 0.0], [0.0, 2.0], [2.0, 4.0], [4.0, 1.0], [2.0, 2.0]]
    assert _draw.points_in_poly(on_it, square).all()
    assert not _draw.points_in_poly([[-1.0, 2.0], [5.0, 5.0]], square).any()


@pytest.mark.parametrize('seed', range(20))
@pytest.mark.parametrize(
    ('shape', 'connectivity'),
    [((40, 50), 1), ((40, 50), 2), ((12, 15, 18), 1), ((12, 15, 18), 3)],
)
def test_flood(seed, shape, connectivity) -> None:
    rng = np.random.default_rng(seed)
    labels = rng.integers(0, 3, shape)
    seed_point = tuple(int(rng.integers(0, s)) for s in shape)
    ours = _draw.flood(labels, seed_point, connectivity=connectivity)
    theirs = skimage_segmentation.flood(
        labels, seed_point, connectivity=connectivity
    )
    assert ours.dtype == bool
    np.testing.assert_array_equal(ours, theirs)


def test_flood_tolerance_and_footprint() -> None:
    rng = np.random.default_rng(1)
    image = rng.uniform(0, 1, (30, 30)).astype(np.float32)
    for seed_point, tolerance in [((3, 4), 0.2), ((20, 25), 0.05)]:
        np.testing.assert_array_equal(
            _draw.flood(image, seed_point, tolerance=tolerance),
            skimage_segmentation.flood(image, seed_point, tolerance=tolerance),
        )
    footprint = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], dtype=bool)
    labels = rng.integers(0, 2, (25, 25))
    np.testing.assert_array_equal(
        _draw.flood(labels, (5, 5), footprint=footprint),
        skimage_segmentation.flood(labels, (5, 5), footprint=footprint),
    )


def test_flood_single_pixel_and_full_region() -> None:
    labels = np.ones((5, 6), dtype=np.int32)
    assert _draw.flood(labels, (2, 2), connectivity=1).all()
    labels[2, 2] = 7
    mask = _draw.flood(labels, (2, 2), connectivity=1)
    assert mask.sum() == 1 and mask[2, 2]
