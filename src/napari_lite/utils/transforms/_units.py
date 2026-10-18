from __future__ import annotations

from collections.abc import Sequence
from contextlib import suppress
from typing import (
    TYPE_CHECKING,
    Any,
    Union,
    overload,
)

# napari-lite: PIXEL stands in for pint's pixel unit (utils/_pixel.py), so
# a layer without units never imports pint
from napari_lite.utils._pixel import PIXEL, PixelUnit, is_pint_unit

if TYPE_CHECKING:
    import pint

    UnitsLike = Union[None, str, pint.Unit, Sequence[str | pint.Unit]]
    UnitsInfo = Union[None, pint.Unit, tuple[pint.Unit, ...]]
else:
    UnitsLike = Any
    UnitsInfo = Any


__all__ = (
    'UnitsInfo',
    'UnitsLike',
    'get_units_from_name',
)


def get_unit_from_name(unit: str | pint.Unit | None) -> pint.Unit:
    if isinstance(unit, PixelUnit) or is_pint_unit(unit):
        return unit
    if unit is None or unit == 'pixel':
        return PIXEL
    if isinstance(unit, str):
        import pint

        from napari_lite.utils._units import get_unit_registry

        with suppress(pint.errors.UndefinedUnitError):
            return get_unit_registry().parse_expression(unit).units

    raise ValueError(f'Could not find unit {unit}')


@overload
def get_units_from_name(units: None) -> None: ...


@overload
def get_units_from_name(units: str | pint.Unit | None) -> pint.Unit: ...


@overload
def get_units_from_name(
    units: Sequence[str | pint.Unit | None],
) -> tuple[pint.Unit, ...]: ...


def get_units_from_name(units: UnitsLike) -> UnitsInfo:
    """Convert a string or sequence of strings to pint units."""
    if isinstance(units, str) or units is None:
        return get_unit_from_name(units)
    if isinstance(units, Sequence):
        return tuple(get_unit_from_name(u) for u in units)
    raise ValueError(f'Could not find unit {units}')
