# napari-lite: own code
"""What napari's model takes from vispy that is not drawing, without
importing vispy.

The vendor tool points the copied imports here (``tools/vendor.toml``):

- ``_handle_exception``: how an event emitter reports an exception raised
  by a callback (napari's ``utils/events/event.py``), vispy's logic with
  napari-lite's logger.
- ``rotate``: the 4x4 matrix of a rotation about an axis (``utils/_tube.py``).
- ``Triangulation``: vispy's polygon triangulation, imported when a shapes
  layer first needs the pure-python backend (``layers/shapes/_shapes_utils.py``).
- ``Colormap``, ``get_colormap``, ``get_colormaps``, ``Color``,
  ``ColorArray``: what ``utils/colormaps/colormap_utils.py`` names.  vispy's
  colormaps by name (``hot``, ``ice``, ...) are looked up when asked for,
  importing vispy then; they are not listed up front, so ``get_colormaps``
  is empty and ``AVAILABLE_COLORMAPS`` holds napari's own maps.
"""

from __future__ import annotations

import importlib
import logging
import math
import sys
from typing import Any

import numpy as np

from napari_lite.utils._colors import Color, ColorArray

__all__ = [
    'Color',
    'ColorArray',
    'Colormap',
    'Triangulation',
    '_handle_exception',
    'get_colormap',
    'get_colormaps',
    'rotate',
]

logger = logging.getLogger('napari_lite')


# exceptions in event callbacks
def _handle_exception(
    ignore_callback_errors: bool,
    print_callback_errors: str,
    obj: Any,
    cb_event: tuple[Any, Any] | None = None,
    node: Any = None,
) -> None:
    """Called from an ``except`` block: re-raise unless errors are ignored,
    and log the first occurrence, every one, or reminders at 1, 2, 4, 8,
    ... repeats, as ``print_callback_errors`` says ('first', 'reminders',
    'always', 'never')."""
    if not hasattr(obj, '_vispy_err_registry'):
        obj._vispy_err_registry = {}
    registry = obj._vispy_err_registry
    if cb_event is not None:
        cb, event = cb_event
        what = f'Invoking {cb} for {event}'
        key = repr(cb) + repr(event)
    else:
        what = f'Drawing node {node}'
        key = repr(node)
    type_, value, tb = sys.exc_info()
    if tb is not None:
        tb = tb.tb_next  # skip this frame
    sys.last_type, sys.last_value, sys.last_traceback = type_, value, tb
    del tb
    if not ignore_callback_errors:
        raise
    if print_callback_errors == 'never':
        return
    this_print: Any = 'full'
    if print_callback_errors in ('first', 'reminders'):
        if key in registry:
            registry[key] += 1
            if print_callback_errors == 'first':
                this_print = None
            else:
                count = registry[key]
                this_print = (
                    count if count == 2 ** int(math.log2(count)) else None
                )
        else:
            registry[key] = 1
    if this_print == 'full':
        logger.exception(what)
    elif this_print is not None:
        logger.error('%s repeat %s', what, this_print)


# a rotation matrix
def rotate(angle: float, axis: Any, dtype: Any = None) -> np.ndarray:
    """The 4x4 matrix of a rotation by ``angle`` degrees about ``axis``
    (x, y, z), as vispy's ``rotate``."""
    angle = np.radians(angle)
    x, y, z = np.asarray(axis, dtype=float) / np.linalg.norm(axis)
    c, s = math.cos(angle), math.sin(angle)
    cx, cy, cz = (1 - c) * x, (1 - c) * y, (1 - c) * z
    return np.array(
        [
            [cx * x + c, cy * x - z * s, cz * x + y * s, 0.0],
            [cx * y + z * s, cy * y + c, cz * y - x * s, 0.0],
            [cx * z - y * s, cy * z + x * s, cz * z + c, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
        dtype,
    ).T


# vispy's triangulation, when a shapes layer needs it
def Triangulation(vertices: Any, edges: Any) -> Any:
    """``vispy.geometry.Triangulation(vertices, edges)``, importing vispy."""
    from vispy.geometry import Triangulation as _Triangulation

    return _Triangulation(vertices, edges)


# vispy's colormaps, by name, when asked for
def get_colormap(name: str) -> Any:
    """vispy's colormap ``name``; imports vispy.  Raises ``KeyError`` for
    an unknown name, like vispy."""
    from vispy.color import get_colormap as _get_colormap

    return _get_colormap(name)


def get_colormaps() -> dict[str, Any]:
    """vispy's colormaps are not listed up front (that would import
    vispy with the model); ``get_colormap`` finds them by name."""
    return {}


class _LazyVispyClass(type):
    """A class that stands for a vispy class until vispy is imported:
    constructing it constructs vispy's, ``isinstance`` asks vispy's."""

    _vispy_path: tuple[str, str]

    def _real(cls) -> type:
        module, name = cls._vispy_path
        return getattr(importlib.import_module(module), name)

    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        return cls._real()(*args, **kwargs)

    def __instancecheck__(cls, instance: Any) -> bool:
        if 'vispy' not in sys.modules:
            return False
        return isinstance(instance, cls._real())


class Colormap(metaclass=_LazyVispyClass):
    """``vispy.color.Colormap``, imported when constructed or checked."""

    _vispy_path = ('vispy.color', 'Colormap')
