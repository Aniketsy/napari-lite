# napari-lite: own code
"""PIXEL, the unit of layers that have no units: equal to pint's pixel unit
in both directions, a plain string otherwise, pint on demand for the rest.
(That the first image imports no pint is checked in test_startup_imports.)"""

# ruff: noqa: SIM300  (both orders of == are the point of these tests)

from __future__ import annotations

import copy
import pickle

import numpy as np
import pint
import pytest

from napari_lite.utils._pixel import PIXEL, PixelUnit, is_pint_unit
from napari_lite.utils._units import get_unit_registry
from napari_lite.utils.transforms._units import get_units_from_name


@pytest.fixture
def pixel():
    return get_unit_registry().pixel


def test_equal_to_pints_pixel_both_ways(pixel) -> None:
    assert PIXEL == pixel
    assert pixel == PIXEL
    assert PIXEL == 'pixel'
    assert PIXEL != get_unit_registry().micrometer
    assert hash(PIXEL) == hash('pixel')
    assert str(PIXEL) == 'pixel'
    assert repr(PIXEL) == "<Unit('pixel')>"
    assert f'{PIXEL}' == 'pixel'
    assert format(PIXEL, '~P') == format(pixel, '~P')


def test_pint_on_demand(pixel) -> None:
    assert PIXEL.dimensionality == pixel.dimensionality
    assert 2 * PIXEL == 2 * pixel
    assert PIXEL * 3 == pixel * 3
    assert PIXEL / 2 == pixel / 2
    assert PIXEL**2 == pixel**2
    assert not is_pint_unit(PIXEL)
    assert is_pint_unit(pixel)
    assert not is_pint_unit('um')


def test_copy_and_pickle() -> None:
    clones = [
        copy.copy(PIXEL),
        copy.deepcopy(PIXEL),
        pickle.loads(pickle.dumps(PIXEL)),
    ]
    for clone in clones:
        assert isinstance(clone, PixelUnit)
        assert clone == PIXEL


def test_names_to_units(pixel) -> None:
    registry = get_unit_registry()
    assert get_units_from_name(None) is PIXEL
    assert get_units_from_name('pixel') is PIXEL
    assert get_units_from_name(PIXEL) is PIXEL
    assert get_units_from_name(('um', 'pixel', None)) == (
        registry.micrometer,
        PIXEL,
        PIXEL,
    )
    with pytest.raises(ValueError, match='Could not find unit'):
        get_units_from_name('nosuchunit')


def test_layers_default_to_pixel(pixel) -> None:
    from napari_lite.layers import Image

    layer = Image(np.zeros((4, 8, 8)))
    assert layer.units == (PIXEL,) * 3
    assert layer.units == (pixel,) * 3
    assert all(isinstance(u, PixelUnit) for u in layer.units)
    affine = layer._transforms['data2physical']
    assert affine.physical_scale == tuple(1.0 * pixel for _ in range(3))
    layer.units = 'um'
    assert all(is_pint_unit(u) for u in layer.units)
    layer.units = None
    assert layer.units == (PIXEL,) * 3


def test_dims_and_layer_list_units(pixel) -> None:
    from napari_lite.components import ViewerModel

    registry = get_unit_registry()
    viewer = ViewerModel()
    image = viewer.add_image(np.zeros((4, 8, 8)))
    points = viewer.add_points(np.zeros((2, 3)))
    assert viewer.layers.extent.units == (PIXEL,) * 3
    assert viewer.dims.units == (pixel,) * 3
    image.units = ('um', 'um', 'um')
    # pixels against lengths: no common units, as in napari
    assert viewer.layers.extent.units is None
    assert viewer.dims.units is None
    points.units = ('um', 'um', 'um')
    assert viewer.layers.extent.units == (registry.micrometer,) * 3
    assert viewer.dims.units == (registry.micrometer,) * 3
    viewer.dims.units = ('mm', 'mm', 'mm')
    assert viewer.dims.units == (registry.millimeter,) * 3
    viewer.dims.units = None
    assert viewer.dims.units is None


def test_registry_is_the_application_registry() -> None:
    assert get_unit_registry() is pint.get_application_registry()
    assert get_unit_registry().pixel == PIXEL


def test_private_attributes_are_not_forwarded(pixel) -> None:
    """pint tells its own objects from strings by ``_REGISTRY``; a stand-in
    that answered would be compared as a quantity and never be equal
    (pint 0.25, the version Python 3.11 gets)."""
    with pytest.raises(AttributeError):
        _ = PIXEL._REGISTRY
    assert PIXEL.dimensionality == pixel.dimensionality
