# napari-lite: own code
"""Drawing a ``View`` with pygfx (WGPU): the second renderer.

The same model, the same signals and the same one-adapter-per-item shape
as ``_vispy.py``; nothing in the model or in the widget knows which one
draws.  Needs the ``pygfx`` extra (pygfx, rendercanvas, wgpu).

Images are uploaded in their own dtype with the contrast limits applied on
the GPU.  Rows grow downwards on screen through a group scaled by -1 in y,
so an item's local coordinates are (column, row) and the world's are
(column, -row).  Every item sits at its own depth in drawing order, so a
later item passes the depth test over an earlier one.
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Executor, Future
from typing import Any, ClassVar

import numpy as np
import pygfx as gfx
from psygnal import Signal

from napari_lite.view._colormaps import colormap_table
from napari_lite.view._model import ImageItem, Item, PointsItem, View

__all__ = ['PygfxImage', 'PygfxPoints', 'PygfxRenderer']

# vispy's marker names (the model's) to pygfx's
_MARKERS = {
    'disc': 'circle',
    'ring': 'ring',
    'square': 'square',
    'diamond': 'diamond',
    'cross': 'plus',
    'x': 'cross',
    'triangle_up': 'triangle_up',
    'triangle_down': 'triangle_down',
    'star': 'asterix',
}
_DEPTH_STEP = 1e-3  # between items, in drawing order


def _colormap(spec: Any) -> gfx.TextureMap:
    texture = gfx.Texture(colormap_table(spec), dim=1)
    return gfx.TextureMap(texture, filter='linear', wrap='clamp')


class _Adapter:
    """Draws one item with one pygfx object; subclasses say how."""

    node: Any

    def __init__(self, item: Item, renderer: PygfxRenderer) -> None:
        self.item = item
        self.renderer = renderer
        self._own_step: tuple[int, ...] | None = None
        self.node = self._make_node()
        self.node.material.opacity = item.opacity
        self.node.visible = item.visible
        renderer.world.add(self.node)
        item.changed.connect(self.update)

    def _make_node(self) -> Any:
        raise NotImplementedError

    def remove(self) -> None:
        self.item.changed.disconnect(self.update)
        self.renderer.world.remove(self.node)

    def set_step(self, step: tuple[int, ...]) -> None:
        own = self.item.own_step(step)
        if own == self._own_step:
            return
        self._own_step = own
        self._slice(own)

    def _slice(self, own: tuple[int, ...]) -> None:
        raise NotImplementedError

    def update(self, what: str) -> None:
        if what == 'opacity':
            self.node.material.opacity = self.item.opacity
        elif what == 'visible':
            self.node.visible = self.item.visible
        self.renderer.request_draw()


class PygfxImage(_Adapter):
    """An ``ImageItem`` as a pygfx Image."""

    item: ImageItem

    def __init__(self, item: ImageItem, renderer: PygfxRenderer) -> None:
        self._request = 0
        self.array: np.ndarray | None = None  # the slice shown
        super().__init__(item, renderer)

    def _make_node(self) -> Any:
        item = self.item
        material = gfx.ImageBasicMaterial(
            clim=item.contrast_limits or (0.0, 1.0),
            map=None if item.rgb else _colormap(item.colormap),
            interpolation=item.interpolation,
        )
        placeholder = gfx.Texture(np.zeros((1, 1), np.float32), dim=2)
        return gfx.Image(gfx.Geometry(grid=placeholder), material)

    def _slice(self, own: tuple[int, ...]) -> None:
        self._request += 1
        request = self._request
        executor = self.renderer.executor
        if executor is None or isinstance(self.item.data, np.ndarray):
            self._show(self.item.slice(own))
            return

        def done(future: Future, request: int = request) -> None:
            if future.cancelled() or request != self._request:
                return
            array = future.result()
            self.renderer.call_soon(lambda: self._show(array, request))

        executor.submit(self.item.slice, own).add_done_callback(done)

    def _show(self, array: np.ndarray, request: int | None = None) -> None:
        if request is not None and request != self._request:
            return
        self.array = array
        upload = array
        if self.item.rgb:
            if array.shape[-1] == 3:  # the GPU has no 3-channel textures
                alpha = 255 if array.dtype == np.uint8 else 1.0
                upload = np.concatenate(
                    [
                        array,
                        np.full((*array.shape[:2], 1), alpha, array.dtype),
                    ],
                    axis=-1,
                )
            is_uint8 = array.dtype == np.uint8
            self.node.material.clim = (0, 255) if is_uint8 else (0, 1)
        self.node.geometry = gfx.Geometry(grid=gfx.Texture(upload, dim=2))
        self.renderer.request_draw()

    def update(self, what: str) -> None:
        material = self.node.material
        if what == 'colormap' and not self.item.rgb:
            material.map = _colormap(self.item.colormap)
        elif what == 'contrast_limits' and self.item.contrast_limits:
            material.clim = self.item.contrast_limits
        elif what == 'interpolation':
            material.interpolation = self.item.interpolation
        super().update(what)


class PygfxPoints(_Adapter):
    """A ``PointsItem`` as pygfx Points with markers."""

    item: PointsItem

    def __init__(self, item: PointsItem, renderer: PygfxRenderer) -> None:
        self._shown = 0
        super().__init__(item, renderer)

    def _make_node(self) -> Any:
        geometry = gfx.Geometry(
            positions=np.zeros((1, 3), np.float32),
            sizes=np.ones(1, np.float32),
            colors=np.ones((1, 4), np.float32),
        )
        material = gfx.PointsMarkerMaterial(
            marker=_MARKERS.get(self.item.symbol, 'circle'),
            size_space='world',
            size_mode='vertex',
            color_mode='vertex',
            edge_width=0,
        )
        return gfx.Points(geometry, material)

    def _slice(self, own: tuple[int, ...]) -> None:
        from vispy.color import ColorArray  # colour names and tuples

        item = self.item
        shown = item.slice(own)
        self._shown = len(shown)
        if not self._shown:
            self.node.visible = False
            self.renderer.request_draw()
            return
        coords = item.coords[shown][:, -2:]
        color = item.color
        if not isinstance(color, str) and np.ndim(color) == 2:
            color = np.asarray(color)[shown]
        rgba = np.asarray(ColorArray(color).rgba, np.float32)
        if len(rgba) == 1:
            rgba = np.repeat(rgba, self._shown, axis=0)
        positions = np.zeros((self._shown, 3), np.float32)
        positions[:, 0] = coords[:, 1]  # x: column
        positions[:, 1] = coords[:, 0]  # y: row (the group flips it)
        self.node.geometry = gfx.Geometry(
            positions=positions,
            sizes=item.size[shown].astype(np.float32),
            colors=rgba,
        )
        self.node.material.marker = _MARKERS.get(item.symbol, 'circle')
        self.node.visible = item.visible
        self.renderer.request_draw()

    def update(self, what: str) -> None:
        if what in ('size', 'color', 'symbol') and self._own_step is not None:
            self._slice(self._own_step)
        elif what == 'visible':
            self.node.visible = self.item.visible and self._shown > 0
            self.renderer.request_draw()
        else:
            super().update(what)


class PygfxRenderer:
    """Draws ``view`` with pygfx; ``native`` is the canvas widget.

    Parameters
    ----------
    view : View
        The model to draw; items added to it later are drawn too.
    background : colour
        Canvas colour (default black).
    size : (int, int)
        Canvas size in logical pixels, width by height.
    executor, call_soon
        As for ``VispyRenderer``: where lazy arrays are sliced and how
        the result reaches the canvas's thread.
    canvas : rendercanvas canvas, optional
        A canvas to draw on; by default a Qt widget
        (``rendercanvas.qt.QRenderWidget``).  Tests pass an offscreen one.
    pixel_ratio : float, optional
        Physical pixels per logical pixel; the canvas's by default.
    """

    adapters: ClassVar[dict[type[Item], type[_Adapter]]] = {
        ImageItem: PygfxImage,
        PointsItem: PygfxPoints,
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
        canvas: Any = None,
        pixel_ratio: float | None = None,
    ) -> None:
        if executor is not None and call_soon is None:
            raise ValueError('an executor needs call_soon')
        self.view = view
        self.executor = executor
        self.call_soon = call_soon or (lambda fn: fn())
        self._adapters: dict[Item, _Adapter] = {}
        self._syncing = True
        self._applied: tuple[float, ...] | None = None
        if canvas is None:
            import qtpy  # noqa: F401 - picks the Qt binding for rendercanvas
            from rendercanvas.qt import QRenderWidget

            canvas = QRenderWidget(size=size)
        self.canvas = canvas
        self.renderer = gfx.renderers.WgpuRenderer(
            canvas, pixel_ratio=pixel_ratio
        )
        self.scene = gfx.Scene()
        self.scene.add(gfx.Background.from_color(gfx.Color(background)))
        self.world = gfx.Group()
        self.world.local.scale = (1, -1, 1)  # rows grow downwards on screen
        self.scene.add(self.world)
        self.camera = gfx.OrthographicCamera(1, 1, maintain_aspect=True)
        self.controller = gfx.PanZoomController(
            self.camera, register_events=self.renderer
        )
        self.renderer.add_event_handler(self._on_pointer, 'pointer_move')

        for item in view.items:
            self._add(item)
        self._order()
        view.changed.connect(self._on_view_change)
        view.camera.changed.connect(self._model_to_camera)
        self._syncing = False
        self._model_to_camera()
        self.canvas.request_draw(self._draw)

    # canvas
    @property
    def native(self) -> Any:
        """The canvas widget."""
        return self.canvas

    def request_draw(self) -> None:
        self.canvas.request_draw(self._draw)

    def _draw(self) -> None:
        self.renderer.render(self.scene, self.camera)
        self._camera_to_model()  # after the controller's pans and zooms

    def screenshot(self) -> np.ndarray:
        """The canvas as an RGBA uint8 array."""
        self.renderer.render(self.scene, self.camera)
        return np.asarray(self.renderer.snapshot())

    def close(self) -> None:
        self.view.changed.disconnect(self._on_view_change)
        self.view.camera.changed.disconnect(self._model_to_camera)
        for item in list(self._adapters):
            self._remove(item)
        self.canvas.close()

    # items
    def adapter(self, item: Item) -> _Adapter:
        return self._adapters[item]

    def node(self, item: Item) -> Any:
        """The pygfx object that draws ``item``."""
        return self._adapters[item].node

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
        self.request_draw()

    def _order(self) -> None:
        for i, item in enumerate(self.view.items):
            if item in self._adapters:
                self._adapters[item].node.local.z = i * _DEPTH_STEP
        self.request_draw()

    # cursor
    def data_position(self, canvas_xy: Any) -> tuple[float, float]:
        """``(row, column)`` under canvas pixel ``canvas_xy`` (x, y), in
        logical pixels."""
        x, y = canvas_xy
        width, height = self.canvas.get_logical_size()
        ndc = np.array([2 * x / width - 1, 1 - 2 * y / height, 0.0, 1.0])
        matrix = self.camera.projection_matrix @ self.camera.view_matrix
        world = np.linalg.inv(matrix) @ ndc
        col, y_world = world[:2] / world[3]
        return (float(-y_world), float(col))

    def value_at(self, row: float, col: float) -> Any:
        r, c = round(row), round(col)
        for item in reversed(self.view.items):
            adapter = self._adapters.get(item)
            if not isinstance(adapter, PygfxImage) or not item.visible:
                continue
            array = adapter.array
            if array is None:
                continue
            if 0 <= r < array.shape[0] and 0 <= c < array.shape[1]:
                return array[r, c].tolist()
        return None

    def _on_pointer(self, event: Any) -> None:
        self.cursor_moved.emit(self.data_position((event.x, event.y)))

    # camera
    def _model_to_camera(self) -> None:
        if self._syncing:
            return
        row, col, height, width = self.view.camera.rect
        self._syncing = True
        try:
            self.camera.width = width
            self.camera.height = height
            self.camera.local.position = (
                col + width / 2,
                -(row + height / 2),
                1,
            )
            self._applied = self._camera_state()
        finally:
            self._syncing = False
        self.request_draw()

    def _camera_state(self) -> tuple[float, ...]:
        x, y, _ = self.camera.local.position
        return (
            float(x),
            float(y),
            float(self.camera.width),
            float(self.camera.height),
        )

    def _camera_to_model(self) -> None:
        if self._syncing:
            return
        state = self._camera_state()
        if state == self._applied:
            return
        x, y, width, height = state
        self._syncing = True
        try:
            self.view.camera.rect = (
                -y - height / 2,
                x - width / 2,
                height,
                width,
            )
            self._applied = state
        finally:
            self._syncing = False
