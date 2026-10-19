# napari-lite: own code
"""Colormaps as tables for any renderer: ``(N, 4)`` float32 RGBA rows from
the lowest to the highest value.

Names: 'gray', the matplotlib maps napari carries as plain data (magma,
inferno, plasma, viridis, cividis, twilight, turbo, ...), napari's
single-colour ramps from black, and vispy's own maps (hot, autumn, ice,
...; vispy is a dependency of napari-lite anyway).  A sequence of colours
is interpolated from the first to the last.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from napari_lite.view._model import LISTED_COLORMAPS, RAMP_COLORMAPS

__all__ = ['RAMP_RGB', 'colormap_table']

# napari's single-colour maps go from black to these
RAMP_RGB: dict[str, tuple[float, float, float]] = {
    'red': (1.0, 0.0, 0.0),
    'green': (0.0, 1.0, 0.0),
    'blue': (0.0, 0.0, 1.0),
    'cyan': (0.0, 1.0, 1.0),
    'magenta': (1.0, 0.0, 1.0),
    'yellow': (1.0, 1.0, 0.0),
    'white': (1.0, 1.0, 1.0),
}
_ALIASES = {'gray': 'grays', 'grey': 'grays'}


def _with_alpha(rgb: np.ndarray) -> np.ndarray:
    table = np.ones((len(rgb), 4), dtype=np.float32)
    table[:, :3] = rgb
    return table


def colormap_table(spec: Any, n: int = 256) -> np.ndarray:
    """The ``(n, 4)`` RGBA table of a colormap name or a colour sequence."""
    if isinstance(spec, str):
        name = _ALIASES.get(spec, spec)
        if name == 'grays':
            t = np.linspace(0.0, 1.0, n, dtype=np.float32)
            return _with_alpha(np.column_stack([t, t, t]))
        if name in LISTED_COLORMAPS:
            from napari_lite.utils.colormaps.vendored import _cm_listed

            rgb = np.asarray(getattr(_cm_listed, f'_{name}_data'), np.float32)
            return _with_alpha(rgb)
        if name in RAMP_COLORMAPS:
            t = np.linspace(0.0, 1.0, n, dtype=np.float32)[:, None]
            return _with_alpha(t * np.asarray(RAMP_RGB[name], np.float32))
        from vispy.color import get_colormap

        try:
            cmap = get_colormap(name)
        except KeyError:
            raise ValueError(f'unknown colormap {spec!r}') from None
        return np.asarray(cmap.map(np.linspace(0.0, 1.0, n)), np.float32)
    from vispy.color import ColorArray  # colour names, tuples, arrays

    stops = np.asarray(ColorArray(spec).rgba, dtype=np.float32)
    if len(stops) == 1:
        return np.repeat(stops, n, axis=0)
    x = np.linspace(0.0, 1.0, n)
    xp = np.linspace(0.0, 1.0, len(stops))
    return np.column_stack(
        [np.interp(x, xp, stops[:, i]) for i in range(4)]
    ).astype(np.float32)
