# napari-lite: own code
"""The unit of layers that have no units, ``'pixel'``, without pint.

napari gives every layer pint's ``pixel`` unit by default.  Importing pint
costs 0.6 s and 340 modules and building its registry 0.2 s more, at the
first image of every session, whether or not a unit is ever set.
:data:`PIXEL` stands in for that default: a ``str`` equal to ``'pixel'``,
which pint's units compare equal to (pint compares units with strings, in
both directions), hashable and printable like the string, and handing
everything else, the dimensionality, conversions, arithmetic, formatting,
to pint's pixel unit on demand.  A layer that sets a real unit gets pint
units, and the first of those imports pint.

The one visible difference from napari: ``layer.units`` of a layer without
units holds :class:`PixelUnit` objects, equal to ``pint.Unit('pixel')`` but
not instances of ``pint.Unit``.
"""

from __future__ import annotations

import sys
from typing import Any


class PixelUnit(str):
    """``'pixel'`` as a unit; see the module docstring."""

    __slots__ = ()

    def __new__(cls) -> PixelUnit:
        return str.__new__(cls, 'pixel')

    def __repr__(self) -> str:
        return "<Unit('pixel')>"

    def __reduce__(self) -> tuple[type[PixelUnit], tuple[()]]:
        return (PixelUnit, ())

    @property
    def _pint_unit(self) -> Any:
        """pint's pixel unit, importing pint and building its registry."""
        from napari_lite.utils._units import get_unit_registry

        return get_unit_registry().pixel

    def __getattr__(self, name: str) -> Any:
        # dimensionality, to, is_compatible_with, ...: pint's.  Not the
        # private ones: pint tells its own objects from strings by asking
        # for ``_REGISTRY``, and a stand-in that answered would be compared
        # as a quantity (never equal) instead of as the string 'pixel'
        # (pint 0.25, the newest on Python 3.11; 0.26 checks strings first)
        if name.startswith('_'):
            raise AttributeError(name)
        return getattr(self._pint_unit, name)

    def __format__(self, spec: str) -> str:
        return format(self._pint_unit, spec) if spec else 'pixel'

    # arithmetic gives pint quantities, not repeated strings
    def __mul__(self, other: Any) -> Any:
        return self._pint_unit * other

    def __rmul__(self, other: Any) -> Any:
        return other * self._pint_unit

    def __truediv__(self, other: Any) -> Any:
        return self._pint_unit / other

    def __rtruediv__(self, other: Any) -> Any:
        return other / self._pint_unit

    def __pow__(self, other: Any) -> Any:
        return self._pint_unit**other


PIXEL = PixelUnit()
"""The default unit of every layer axis."""


def is_pint_unit(obj: object) -> bool:
    """True for a pint ``Unit``, found out without importing pint: when
    pint is not in the process, nothing can be one."""
    pint = sys.modules.get('pint')
    return pint is not None and isinstance(obj, pint.Unit)
