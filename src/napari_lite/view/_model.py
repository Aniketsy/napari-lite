# napari-lite: own code
"""The model of the view-only canvas: items, the current slice, the camera.

numpy and psygnal only: no Qt, no vispy, no pydantic, none of napari's
layer code.  A renderer (``_vispy.py``) draws what is here and follows the
``changed`` signals; a widget (``_qt.py``) adds the sliders.

Axes follow napari's convention: the last two axes of an image are the
displayed ones (rows, columns), the leading axes are stepped through with
``View.current_step``.  Items with fewer axes than the view align on the
right, like napari layers.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

import numpy as np
from psygnal import Signal

__all__ = ['COLORMAPS', 'Camera', 'ImageItem', 'Item', 'PointsItem', 'View']

# the colormap names the renderer resolves: vispy's own maps, the
# matplotlib maps napari carries (``utils/colormaps/vendored``) and
# napari's single-colour ramps; an unknown name is refused when set
VISPY_COLORMAPS = frozenset(
    {
        'GrBu',
        'GrBu_d',
        'HiLo',
        'PuGr',
        'RdBu',
        'RdYeBuCy',
        'autumn',
        'blues',
        'cool',
        'coolwarm',
        'cubehelix',
        'diverging',
        'fire',
        'grays',
        'greens',
        'hot',
        'hsl',
        'husl',
        'ice',
        'light_blues',
        'orange',
        'reds',
        'single_hue',
        'spring',
        'summer',
        'viridis',
        'winter',
        'gray',
        'grey',
    }
)
LISTED_COLORMAPS = frozenset(
    {
        'magma',
        'inferno',
        'plasma',
        'cividis',
        'twilight',
        'twilight_shifted',
        'turbo',
        'berlin',
        'managua',
        'vanimo',
    }
)
RAMP_COLORMAPS = frozenset(
    {
        'red',
        'green',
        'blue',
        'cyan',
        'magenta',
        'yellow',
        'white',
    }
)
COLORMAPS = VISPY_COLORMAPS | LISTED_COLORMAPS | RAMP_COLORMAPS


def _as_tuple(value: Sequence[float], n: int, what: str) -> tuple[float, ...]:
    out = tuple(float(v) for v in value)
    if len(out) != n:
        raise ValueError(f'{what} needs {n} values, got {len(out)}')
    return out


class Item:
    """Something drawn: a name, an opacity and a visibility.

    ``changed`` is emitted with the name of the property that changed.
    """

    changed = Signal(str)

    def __init__(
        self, *, name: str = '', opacity: float = 1.0, visible: bool = True
    ) -> None:
        self._name = name
        self._opacity = 1.0
        self._visible = True
        self.opacity = opacity
        self.visible = visible

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        self._name = str(value)
        self.changed.emit('name')

    @property
    def opacity(self) -> float:
        """0 (invisible) to 1 (opaque)."""
        return self._opacity

    @opacity.setter
    def opacity(self, value: float) -> None:
        value = float(value)
        if not 0.0 <= value <= 1.0:
            raise ValueError(f'opacity must be between 0 and 1, got {value}')
        self._opacity = value
        self.changed.emit('opacity')

    @property
    def visible(self) -> bool:
        return self._visible

    @visible.setter
    def visible(self, value: bool) -> None:
        self._visible = bool(value)
        self.changed.emit('visible')

    @property
    def ndim(self) -> int:
        """Number of axes (without an image's channel axis)."""
        raise NotImplementedError

    @property
    def shape(self) -> tuple[int, ...]:
        """Extent along each axis, as a number of steps or pixels."""
        raise NotImplementedError

    def __repr__(self) -> str:
        return f'<{type(self).__name__} {self.name!r} {self.shape}>'


def _align(
    step: Sequence[int], own: int, shape: Sequence[int]
) -> tuple[int, ...]:
    """The last ``own`` entries of ``step`` (the view's step, right-aligned);
    entries the step lacks are the middle of the axis."""
    step = tuple(int(s) for s in step)[max(len(step) - own, 0) :]
    missing = own - len(step)
    return tuple(n // 2 for n in shape[:missing]) + step


def _to_renderable(array: np.ndarray, rgb: bool) -> np.ndarray:
    """A dtype the renderer takes as is: uint8 or float32."""
    if array.dtype == np.uint8:
        return array
    if array.dtype == np.bool_:
        return array.astype(np.uint8)
    if rgb and np.issubdtype(array.dtype, np.integer):
        # integer colour channels other than uint8: scale to 0..1
        info = np.iinfo(array.dtype)
        return (array.astype(np.float32) - info.min) / (info.max - info.min)
    return array.astype(np.float32, copy=False)


class ImageItem(Item):
    """An image: any array with ``shape``, ``dtype`` and ``__getitem__``
    (numpy, dask, zarr, ...), 2D or more; ``rgb=True`` takes the last
    axis as colour channels (3 or 4).

    Only the current 2D slice is read from ``data``, so a lazy array is
    loaded slice by slice.
    """

    def __init__(
        self,
        data: Any,
        *,
        colormap: Any = 'gray',
        contrast_limits: Sequence[float] | None = None,
        opacity: float = 1.0,
        rgb: bool = False,
        interpolation: str = 'nearest',
        name: str = '',
        visible: bool = True,
    ) -> None:
        super().__init__(name=name, opacity=opacity, visible=visible)
        self._data = data
        self._rgb = bool(rgb)
        shape = tuple(int(s) for s in data.shape)
        if self._rgb:
            if len(shape) < 3 or shape[-1] not in (3, 4):
                raise ValueError(
                    'an RGB image needs a last axis of 3 or 4 channels, '
                    f'got shape {shape}'
                )
            shape = shape[:-1]
        if len(shape) < 2:
            raise ValueError(f'an image needs at least 2 axes, got {shape}')
        self._shape = shape
        self._colormap: Any = 'gray'
        self.colormap = colormap
        self._interpolation = interpolation
        self._contrast_limits: tuple[float, float] | None = None
        if self._rgb:
            self._contrast_limits = None
        elif contrast_limits is None:
            self._contrast_limits = self._auto_contrast()
        else:
            self.contrast_limits = contrast_limits

    @property
    def data(self) -> Any:
        return self._data

    @property
    def rgb(self) -> bool:
        return self._rgb

    @property
    def ndim(self) -> int:
        return len(self._shape)

    @property
    def shape(self) -> tuple[int, ...]:
        return self._shape

    @property
    def colormap(self) -> Any:
        """A colormap name ('gray', 'magma', 'viridis', 'green', ...) or a
        sequence of colours from low to high."""
        return self._colormap

    @colormap.setter
    def colormap(self, value: Any) -> None:
        if isinstance(value, str) and value not in COLORMAPS:
            raise ValueError(
                f'unknown colormap {value!r}; one of {sorted(COLORMAPS)}, '
                'or a sequence of colours'
            )
        self._colormap = value
        self.changed.emit('colormap')

    @property
    def contrast_limits(self) -> tuple[float, float] | None:
        """The data values shown as black and as white (None for RGB)."""
        return self._contrast_limits

    @contrast_limits.setter
    def contrast_limits(self, value: Sequence[float]) -> None:
        if self._rgb:
            raise ValueError('an RGB image has no contrast limits')
        lo, hi = _as_tuple(value, 2, 'contrast_limits')
        if not hi > lo:
            raise ValueError(f'contrast_limits must increase, got {value}')
        self._contrast_limits = (lo, hi)
        self.changed.emit('contrast_limits')

    @property
    def interpolation(self) -> str:
        """'nearest' or 'linear'."""
        return self._interpolation

    @interpolation.setter
    def interpolation(self, value: str) -> None:
        if value not in ('nearest', 'linear'):
            raise ValueError(
                f"interpolation is 'nearest' or 'linear', not {value!r}"
            )
        self._interpolation = value
        self.changed.emit('interpolation')

    def slice(self, step: Sequence[int]) -> np.ndarray:
        """The 2D slice at ``step`` (the view's step, right-aligned), as an
        array the renderer takes: rows by columns, uint8 or float32, with
        the colour channels last for RGB."""
        own = self.ndim - 2
        step = _align(step, own, self._shape)
        index = tuple(
            min(max(s, 0), n - 1)
            for s, n in zip(step, self._shape[:own], strict=True)
        )
        array = np.asarray(self._data[index] if index else self._data)
        return _to_renderable(array, self._rgb)

    def _auto_contrast(self) -> tuple[float, float]:
        """Min and max of the middle slice."""
        middle = tuple(n // 2 for n in self._shape[:-2])
        array = self.slice(middle)
        finite = (
            array[np.isfinite(array)] if array.dtype.kind == 'f' else array
        )
        if finite.size == 0:
            return (0.0, 1.0)
        lo, hi = float(finite.min()), float(finite.max())
        if not hi > lo:
            hi = lo + 1.0
        return (lo, hi)


class PointsItem(Item):
    """Points: an ``(N, D)`` array of coordinates in the axes order of the
    images (rows, columns last), ``D`` at least 2.  Points whose
    non-displayed coordinates round to the current step are drawn.
    """

    def __init__(
        self,
        coords: Any,
        *,
        size: float | Sequence[float] = 10.0,
        color: Any = 'cyan',
        symbol: str = 'disc',
        opacity: float = 1.0,
        name: str = '',
        visible: bool = True,
    ) -> None:
        super().__init__(name=name, opacity=opacity, visible=visible)
        coords = np.asarray(coords, dtype=float)
        if coords.ndim != 2 or coords.shape[1] < 2:
            raise ValueError(
                f'points need an (N, D) array with D >= 2, got {coords.shape}'
            )
        self._coords = coords
        self._size: np.ndarray = np.zeros(0)
        self._color: Any = color
        self._symbol = symbol
        self.size = size

    @property
    def coords(self) -> np.ndarray:
        return self._coords

    @property
    def ndim(self) -> int:
        return int(self._coords.shape[1])

    @property
    def shape(self) -> tuple[int, ...]:
        """The steps or pixels each axis spans: ``floor(max) + 1``."""
        if len(self._coords) == 0:
            return (0,) * self.ndim
        return tuple(math.floor(v) + 1 for v in self._coords.max(axis=0))

    @property
    def size(self) -> np.ndarray:
        """Diameter of every point in data units, one value per point."""
        return self._size

    @size.setter
    def size(self, value: float | Sequence[float]) -> None:
        size = np.broadcast_to(
            np.asarray(value, dtype=float), (len(self._coords),)
        ).copy()
        if (size <= 0).any():
            raise ValueError('point sizes must be positive')
        self._size = size
        self.changed.emit('size')

    @property
    def color(self) -> Any:
        """One colour (a name or RGBA) for all points, or one per point."""
        return self._color

    @color.setter
    def color(self, value: Any) -> None:
        self._color = value
        self.changed.emit('color')

    @property
    def symbol(self) -> str:
        """'disc', 'ring', 'square', 'diamond', 'cross', 'x', 'triangle_up',
        'triangle_down', 'star' (vispy's names)."""
        return self._symbol

    @symbol.setter
    def symbol(self, value: str) -> None:
        self._symbol = str(value)
        self.changed.emit('symbol')

    def slice(self, step: Sequence[int]) -> np.ndarray:
        """Indices of the points in the slice at ``step`` (the view's step,
        right-aligned)."""
        own = self.ndim - 2
        if not own:
            return np.arange(len(self._coords))
        step = np.asarray(_align(step, own, self.shape))
        leading = np.round(self._coords[:, :own])
        return np.flatnonzero((leading == step).all(axis=1))


class Camera:
    """The rectangle of the data shown: ``rect`` is (row, column, height,
    width) in data coordinates.  The renderer keeps the aspect ratio, so
    the rectangle is what is shown at least."""

    changed = Signal()

    def __init__(self) -> None:
        self._rect: tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0)

    @property
    def rect(self) -> tuple[float, float, float, float]:
        return self._rect

    @rect.setter
    def rect(self, value: Sequence[float]) -> None:
        row, col, height, width = _as_tuple(value, 4, 'rect')
        if not (height > 0 and width > 0):
            raise ValueError(
                f'rect needs a positive height and width: {value}'
            )
        self._rect = (row, col, height, width)
        self.changed.emit()

    @property
    def center(self) -> tuple[float, float]:
        """(row, column) at the middle of the view."""
        row, col, height, width = self._rect
        return (row + height / 2, col + width / 2)

    @center.setter
    def center(self, value: Sequence[float]) -> None:
        row, col = _as_tuple(value, 2, 'center')
        _, _, height, width = self._rect
        self.rect = (row - height / 2, col - width / 2, height, width)

    def zoom(self, factor: float) -> None:
        """Zoom in by ``factor`` (out for a factor below 1) around the center."""
        if not factor > 0:
            raise ValueError('the zoom factor must be positive')
        row, col = self.center
        _, _, height, width = self._rect
        height, width = height / factor, width / factor
        self.rect = (row - height / 2, col - width / 2, height, width)


class View:
    """Images and points, the current slice and the camera.

    ``changed`` is emitted with 'items' when an item is added or removed
    and with 'current_step' when the slice changes; the camera has its own
    signal.
    """

    changed = Signal(str)

    def __init__(self) -> None:
        self._items: list[Item] = []
        self._current_step: tuple[int, ...] = ()
        self.camera = Camera()

    # --------------------------- items -------------------------*
    @property
    def items(self) -> tuple[Item, ...]:
        """In drawing order: the last one is on top."""
        return tuple(self._items)

    def add(self, item: Item) -> Item:
        """Add ``item``; the first item sets the view to show it whole."""
        if item in self._items:
            raise ValueError(f'{item!r} is already in the view')
        first = not self._items
        self._items.append(item)
        step_changed = self._fit_step()
        self.changed.emit('items')
        if step_changed:
            self.changed.emit('current_step')
        if first:
            self.reset_view()
        return item

    def add_image(self, data: Any, **kwargs: Any) -> ImageItem:
        """Add an image; the keywords are those of ``ImageItem``."""
        item = ImageItem(data, **kwargs)
        self.add(item)
        return item

    def add_points(self, coords: Any, **kwargs: Any) -> PointsItem:
        """Add points; the keywords are those of ``PointsItem``."""
        item = PointsItem(coords, **kwargs)
        self.add(item)
        return item

    def remove(self, item: Item) -> None:
        self._items.remove(item)
        step_changed = self._fit_step()
        self.changed.emit('items')
        if step_changed:
            self.changed.emit('current_step')

    def clear(self) -> None:
        self._items.clear()
        step_changed = self._fit_step()
        self.changed.emit('items')
        if step_changed:
            self.changed.emit('current_step')

    # ------------------- axes -------------------------------
    @property
    def ndim(self) -> int:
        """Axes of the item with the most; at least 2."""
        return max((item.ndim for item in self._items), default=2)

    @property
    def nsteps(self) -> tuple[int, ...]:
        """How many steps each non-displayed axis has (the leading
        ``ndim - 2`` axes), from the items that have the axis."""
        n = self.ndim - 2
        steps = [1] * n
        for item in self._items:
            own = item.ndim - 2
            for i, extent in enumerate(item.shape[:own]):
                steps[n - own + i] = max(steps[n - own + i], extent)
        return tuple(steps)

    @property
    def current_step(self) -> tuple[int, ...]:
        """The slice shown: one index per non-displayed axis."""
        return self._current_step

    @current_step.setter
    def current_step(self, value: Sequence[int]) -> None:
        nsteps = self.nsteps
        step = tuple(int(v) for v in value)
        if len(step) != len(nsteps):
            raise ValueError(
                f'current_step needs {len(nsteps)} values for the '
                f'non-displayed axes, got {len(step)}'
            )
        step = tuple(
            min(max(s, 0), n - 1) for s, n in zip(step, nsteps, strict=True)
        )
        if step != self._current_step:
            self._current_step = step
            self.changed.emit('current_step')

    def _fit_step(self) -> bool:
        """Keep the step valid when the axes change: new leading axes start
        in the middle (as napari does), the others keep their index.
        Returns whether the step changed; the caller emits 'items' first."""
        nsteps = self.nsteps
        old = self._current_step
        if len(old) < len(nsteps):
            new = tuple(n // 2 for n in nsteps[: len(nsteps) - len(old)]) + old
        else:
            new = old[len(old) - len(nsteps) :]
        new = tuple(
            min(max(s, 0), n - 1) for s, n in zip(new, nsteps, strict=True)
        )
        if new != self._current_step:
            self._current_step = new
            return True
        return False

    # ---------------------- camera -------------------------
    @property
    def extent(self) -> tuple[tuple[float, float], tuple[float, float]]:
        """((row_min, row_max), (col_min, col_max)) over all items, in data
        coordinates, pixel edges included."""
        rows: list[float] = []
        cols: list[float] = []
        for item in self._items:
            if isinstance(item, PointsItem):
                if len(item.coords):
                    rows += [
                        item.coords[:, -2].min() - 0.5,
                        item.coords[:, -2].max() + 0.5,
                    ]
                    cols += [
                        item.coords[:, -1].min() - 0.5,
                        item.coords[:, -1].max() + 0.5,
                    ]
            else:
                rows += [-0.5, item.shape[-2] - 0.5]
                cols += [-0.5, item.shape[-1] - 0.5]
        if not rows:
            return ((-0.5, 0.5), (-0.5, 0.5))
        return (
            (float(min(rows)), float(max(rows))),
            (float(min(cols)), float(max(cols))),
        )

    def reset_view(self, margin: float = 0.02) -> None:
        """Show every item whole, with ``margin`` of the extent around."""
        (r0, r1), (c0, c1) = self.extent
        height, width = max(r1 - r0, 1e-9), max(c1 - c0, 1e-9)
        self.camera.rect = (
            r0 - height * margin,
            c0 - width * margin,
            height * (1 + 2 * margin),
            width * (1 + 2 * margin),
        )
