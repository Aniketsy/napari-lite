# napari-lite: own code
"""Drawing a ``View`` with vispy.

One adapter per item draws it with a vispy visual and follows the item's
``changed`` signal; ``VispyRenderer`` keeps the set of adapters in step
with the view's items, re-slices them when the step changes and keeps a
pan-zoom camera in step with the view's camera in both directions.

Images are uploaded in their own dtype (uint8, uint16, int8, int16,
float32) and the contrast limits are applied on the GPU, as in napari;
a lazy array (dask, zarr) is sliced in a worker when the renderer is
given an ``executor``, so the window stays responsive, and the newest
step always wins.

This is the whole of what a renderer has to do: another one (pygfx, a
matplotlib axes, ...) implements ``Renderer`` against the same model.
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Executor, Future
from typing import Any, ClassVar

import numpy as np
from psygnal import Signal
from vispy import scene
from vispy.color import (
    ColorArray,
    Colormap,
    get_colormap,
    get_colormaps,
)
from vispy.color.colormap import BaseColormap
from vispy.visuals.transforms import STTransform

from napari_lite._vispy.utils.gl import get_gl_extensions
from napari_lite.view._colormaps import RAMP_RGB
from napari_lite.view._model import (
    LISTED_COLORMAPS,
    RAMP_COLORMAPS,
    ImageItem,
    Item,
    PointsItem,
    View,
)

__all__ = [
    'VispyImage',
    'VispyPoints',
    'VispyRenderer',
    'texture_format',
    'vispy_colormap',
]

# napari's names for maps vispy spells differently
_ALIASES = {'gray': 'grays', 'grey': 'grays'}


def vispy_colormap(spec: Any) -> BaseColormap:
    """vispy's colormap for a name or a sequence of colours from low to high.

    Names: vispy's own maps, then the matplotlib maps napari carries as
    plain data (magma, inferno, plasma, cividis, twilight, turbo, ...; no
    matplotlib needed), then napari's single-colour ramps from black.
    """
    if isinstance(spec, BaseColormap):
        return spec
    if isinstance(spec, str):
        name = _ALIASES.get(spec, spec)
        if name in get_colormaps():
            return get_colormap(name)
        if name in LISTED_COLORMAPS:
            from napari_lite.utils.colormaps.vendored import _cm_listed

            return Colormap(np.asarray(getattr(_cm_listed, f'_{name}_data')))
        if name in RAMP_COLORMAPS:
            return Colormap([[0.0, 0.0, 0.0, 1.0], [*RAMP_RGB[name], 1.0]])
        raise ValueError(f'unknown colormap {spec!r}')
    return Colormap(ColorArray(spec).rgba)


_texture_format: list[str | None] = []


def texture_format() -> str | None:
    """'auto' when the GPU scales textures itself (integer data uploaded
    as it is), None when it has no float textures and vispy must convert
    on the CPU; napari makes the same choice.  Found out once."""
    if not _texture_format:
        try:
            ok = 'texture_float' in get_gl_extensions()
        except Exception:  # no OpenGL context: be safe
            ok = False
        _texture_format.append('auto' if ok else None)
    return _texture_format[0]


class _SyncedCamera(scene.PanZoomCamera):
    """A pan-zoom camera that writes the rectangle it shows back into the
    view's camera, so the model knows where the user panned and zoomed."""

    def __init__(self, renderer: VispyRenderer) -> None:
        self._renderer = renderer
        super().__init__(aspect=1)
        self.flip = (False, True, False)  # row 0 at the top

    def view_changed(self) -> None:
        super().view_changed()
        self._renderer._camera_to_model()


class _Adapter:
    """Draws one item with one visual; subclasses say how."""

    visual: Any

    def __init__(self, item: Item, renderer: VispyRenderer) -> None:
        self.item = item
        self.renderer = renderer
        self._own_step: tuple[int, ...] | None = None
        self.visual = self._make_visual()
        self.visual.opacity = item.opacity
        self.visual.visible = item.visible
        item.changed.connect(self.update)

    def _make_visual(self) -> Any:
        raise NotImplementedError

    def remove(self) -> None:
        self.item.changed.disconnect(self.update)
        self.visual.parent = None

    def set_step(self, step: tuple[int, ...]) -> None:
        """Show the slice at the view's ``step``; nothing happens when the
        item's own axes did not move."""
        own = self.item.own_step(step)
        if own == self._own_step:
            return
        self._own_step = own
        self._slice(own)

    def _slice(self, own: tuple[int, ...]) -> None:
        raise NotImplementedError

    def update(self, what: str) -> None:
        if what == 'opacity':
            self.visual.opacity = self.item.opacity
        elif what == 'visible':
            self.visual.visible = self.item.visible
        self.renderer.canvas.update()


class VispyImage(_Adapter):
    """An ``ImageItem`` as a vispy Image visual."""

    item: ImageItem

    def __init__(self, item: ImageItem, renderer: VispyRenderer) -> None:
        self._request = 0
        self.array: np.ndarray | None = None  # the slice shown
        super().__init__(item, renderer)
        self._apply_clim(None)

    def _make_visual(self) -> Any:
        visual = scene.visuals.Image(
            parent=self.renderer.scene_view.scene,
            interpolation=self.item.interpolation,
            cmap=vispy_colormap(self.item.colormap),
            texture_format=self.renderer.texture_format,
        )
        # vispy draws pixel i from i to i + 1; napari's data coordinates
        # put its centre at i, so a point at (10, 10) sits on pixel (10, 10)
        visual.transform = STTransform(translate=(-0.5, -0.5))
        return visual

    def _slice(self, own: tuple[int, ...]) -> None:
        self._request += 1
        request = self._request
        executor = self.renderer.executor
        if executor is None or isinstance(self.item.data, np.ndarray):
            self._show(self.item.slice(own))  # in memory: at once
            return

        def done(future: Future, request: int = request) -> None:
            if future.cancelled() or request != self._request:
                return  # a newer step won
            array = future.result()
            self.renderer.call_soon(lambda: self._show(array, request))

        executor.submit(self.item.slice, own).add_done_callback(done)

    def _show(self, array: np.ndarray, request: int | None = None) -> None:
        if request is not None and request != self._request:
            return
        self.array = array
        self.visual.set_data(array)
        if self.item.rgb:
            self._apply_clim(array)
        self.renderer.canvas.update()

    def _apply_clim(self, array: np.ndarray | None) -> None:
        if self.item.rgb:
            # colour channels are shown as they are: uint8 is 0..255,
            # anything else was scaled to 0..1 by the item
            if array is not None:
                is_uint8 = array.dtype == np.uint8
                self.visual.clim = (0, 255) if is_uint8 else (0, 1)
        elif self.item.contrast_limits is not None:
            self.visual.clim = self.item.contrast_limits

    def update(self, what: str) -> None:
        if what == 'colormap':
            self.visual.cmap = vispy_colormap(self.item.colormap)
        elif what == 'contrast_limits':
            self._apply_clim(None)
        elif what == 'interpolation':
            self.visual.interpolation = self.item.interpolation
        super().update(what)


class VispyPoints(_Adapter):
    """A ``PointsItem`` as a vispy Markers visual."""

    item: PointsItem

    def __init__(self, item: PointsItem, renderer: VispyRenderer) -> None:
        self._shown = 0
        super().__init__(item, renderer)

    def _make_visual(self) -> Any:
        return scene.visuals.Markers(
            parent=self.renderer.scene_view.scene, scaling='scene'
        )

    def _slice(self, own: tuple[int, ...]) -> None:
        item = self.item
        shown = item.slice(own)
        self._shown = len(shown)
        if not self._shown:
            self.visual.visible = False
            self.renderer.canvas.update()
            return
        self.visual.visible = item.visible
        coords = item.coords[shown][:, -2:]
        color = item.color
        if not isinstance(color, str) and np.ndim(color) == 2:
            color = np.asarray(color)[shown]
        rgba = ColorArray(color).rgba
        self.visual.set_data(
            pos=np.ascontiguousarray(coords[:, ::-1]),  # x: column, y: row
            size=item.size[shown],
            face_color=rgba,
            edge_width=0,
            edge_color=rgba,
            symbol=item.symbol,
        )
        self.renderer.canvas.update()

    def update(self, what: str) -> None:
        if what in ('size', 'color', 'symbol') and self._own_step is not None:
            self._slice(self._own_step)
        elif what == 'visible':
            self.visual.visible = self.item.visible and self._shown > 0
            self.renderer.canvas.update()
        else:
            super().update(what)


class VispyRenderer:
    """Draws ``view`` on a vispy scene canvas; ``native`` is the Qt widget.

    Parameters
    ----------
    view : View
        The model to draw; items added to it later are drawn too.
    background : str or sequence of float
        Canvas colour (default black).
    size : (int, int)
        Initial canvas size in pixels, width by height.
    executor : concurrent.futures.Executor, optional
        Where lazy arrays are sliced; in-memory arrays are sliced at once.
        Needs ``call_soon``.  Without an executor everything is sliced at
        once, on the calling thread.
    call_soon : callable, optional
        Runs a function on the thread that owns the canvas; called from
        the executor's thread (the Qt widget passes a queued signal).
    """

    adapters: ClassVar[dict[type[Item], type[_Adapter]]] = {
        ImageItem: VispyImage,
        PointsItem: VispyPoints,
    }

    cursor_moved = Signal(object)
    """Emitted with ``(row, column)`` in data coordinates as the pointer
    moves over the canvas."""

    def __init__(
        self,
        view: View,
        *,
        background: Any = 'black',
        size: tuple[int, int] = (800, 600),
        executor: Executor | None = None,
        call_soon: Callable[[Callable[[], None]], None] | None = None,
    ) -> None:
        if executor is not None and call_soon is None:
            raise ValueError('an executor needs call_soon')
        self.view = view
        self.executor = executor
        self.call_soon = call_soon or (lambda fn: fn())
        self._adapters: dict[Item, _Adapter] = {}
        # the model leads: nothing the camera does while being set up (its
        # default rectangle, the flip, joining the view box) reaches it
        self._syncing = True
        self.canvas = scene.SceneCanvas(
            keys=None, size=size, bgcolor=background
        )
        # points lie in the plane of the images: drawn later, they must
        # pass the depth test at an equal depth (napari does the same)
        self.canvas.context.set_depth_func('lequal')
        self.texture_format = texture_format()
        self.scene_view = self.canvas.central_widget.add_view()
        self.camera = _SyncedCamera(self)
        self.scene_view.camera = self.camera

        for item in view.items:
            self._add(item)
        self._order()
        view.changed.connect(self._on_view_change)
        view.camera.changed.connect(self._model_to_camera)
        self.canvas.events.mouse_move.connect(self._on_mouse_move)
        self._syncing = False
        self._model_to_camera()

    @property
    def native(self) -> Any:
        """The Qt widget of the canvas."""
        return self.canvas.native

    def screenshot(self) -> np.ndarray:
        """The canvas as an RGBA uint8 array."""
        return np.asarray(self.canvas.render())

    def close(self) -> None:
        self.view.changed.disconnect(self._on_view_change)
        self.view.camera.changed.disconnect(self._model_to_camera)
        self.canvas.events.mouse_move.disconnect(self._on_mouse_move)
        for item in list(self._adapters):
            self._remove(item)
        self.canvas.close()

    # items
    def adapter(self, item: Item) -> _Adapter:
        """The adapter that draws ``item``."""
        return self._adapters[item]

    def visual(self, item: Item) -> Any:
        """The vispy visual that draws ``item``."""
        return self._adapters[item].visual

    def _on_view_change(self, what: str) -> None:
        if what == 'items':
            for item in list(self._adapters):
                if item not in self.view.items:
                    self._remove(item)
            for item in self.view.items:
                if item not in self._adapters:
                    self._add(item)
            self._order()
        elif what == 'current_step':
            for adapter in self._adapters.values():
                adapter.set_step(self.view.current_step)

    def _add(self, item: Item) -> None:
        for cls, adapter_cls in self.adapters.items():
            if isinstance(item, cls):
                adapter = adapter_cls(item, self)
                break
        else:
            raise TypeError(f'cannot draw {item!r}')
        self._adapters[item] = adapter
        adapter.set_step(self.view.current_step)

    def _remove(self, item: Item) -> None:
        self._adapters.pop(item).remove()

    def _order(self) -> None:
        for i, item in enumerate(self.view.items):
            if item in self._adapters:
                self._adapters[item].visual.order = i

    # cursor
    def data_position(self, canvas_xy: Any) -> tuple[float, float]:
        """``(row, column)`` in data coordinates under canvas pixel
        ``canvas_xy`` (x, y)."""
        x, y = self.scene_view.scene.transform.imap(list(canvas_xy))[:2]
        return (float(y), float(x))

    def value_at(self, row: float, col: float) -> Any:
        """The value of the topmost visible image under ``(row, col)``:
        a number, a list for RGB, or None outside every image."""
        r, c = round(row), round(col)
        for item in reversed(self.view.items):
            adapter = self._adapters.get(item)
            if not isinstance(adapter, VispyImage) or not item.visible:
                continue
            array = adapter.array
            if array is None:
                continue
            if 0 <= r < array.shape[0] and 0 <= c < array.shape[1]:
                return array[r, c].tolist()
        return None

    def _on_mouse_move(self, event: Any) -> None:
        self.cursor_moved.emit(self.data_position(event.pos))

    # camera
    def _model_to_camera(self) -> None:
        if self._syncing:
            return
        row, col, height, width = self.view.camera.rect
        self._syncing = True
        try:
            self.camera.rect = (col, row, width, height)
        finally:
            self._syncing = False

    def _camera_to_model(self) -> None:
        # vispy calls view_changed while the camera is being built
        if self._syncing or getattr(self, 'camera', None) is None:
            return
        rect = self.camera.rect
        self._syncing = True
        try:
            self.view.camera.rect = (
                rect.pos[1],
                rect.pos[0],
                rect.size[1],
                rect.size[0],
            )
        finally:
            self._syncing = False
