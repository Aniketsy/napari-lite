# napari-lite: own code
"""Drawing a ``View`` with vispy: one Image visual per image item, one
Markers visual per points item, a pan-zoom camera kept in step with the
view's camera in both directions.

This is the whole of what a renderer has to do; another one (pygfx, a
matplotlib axes, ...) would implement the same methods against the same
model without touching it.
"""

from __future__ import annotations

from functools import partial
from typing import Any

import numpy as np
from vispy import scene
from vispy.color import (
    Color,
    ColorArray,
    Colormap,
    get_colormap,
    get_colormaps,
)
from vispy.color.colormap import BaseColormap

from napari_lite.view._model import (
    LISTED_COLORMAPS,
    RAMP_COLORMAPS,
    ImageItem,
    Item,
    PointsItem,
    View,
)

__all__ = ['VispyRenderer', 'vispy_colormap']

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
            return Colormap([Color('black').rgba, Color(name).rgba])
        raise ValueError(f'unknown colormap {spec!r}')
    return Colormap(ColorArray(spec).rgba)


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
    """

    def __init__(
        self,
        view: View,
        *,
        background: Any = 'black',
        size: tuple[int, int] = (800, 600),
    ) -> None:
        self.view = view
        self._visuals: dict[Item, Any] = {}
        self._callbacks: dict[Item, Any] = {}
        # the model leads: nothing the camera does while being set up (its
        # default rectangle, the flip, joining the view box) reaches it
        self._syncing = True
        self.canvas = scene.SceneCanvas(
            keys=None, size=size, bgcolor=background
        )
        # points lie in the plane of the images: drawn later, they must
        # pass the depth test at an equal depth (napari does the same)
        self.canvas.context.set_depth_func('lequal')
        self.scene_view = self.canvas.central_widget.add_view()
        self.camera = _SyncedCamera(self)
        self.scene_view.camera = self.camera

        for item in view.items:
            self._add(item)
        self._order()
        view.changed.connect(self._on_view_change)
        view.camera.changed.connect(self._model_to_camera)
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
        for item in list(self._visuals):
            self._remove(item)
        self.canvas.close()

    # --------------------------- items ------------------------
    def visual(self, item: Item) -> Any:
        """The vispy visual that draws ``item``."""
        return self._visuals[item]

    def _on_view_change(self, what: str) -> None:
        if what == 'items':
            for item in list(self._visuals):
                if item not in self.view.items:
                    self._remove(item)
            for item in self.view.items:
                if item not in self._visuals:
                    self._add(item)
            self._order()
        elif what == 'current_step':
            for item in self._visuals:
                self._set_data(item)

    def _add(self, item: Item) -> None:
        if isinstance(item, ImageItem):
            visual = scene.visuals.Image(
                parent=self.scene_view.scene,
                interpolation=item.interpolation,
                cmap=vispy_colormap(item.colormap),
            )
            if item.contrast_limits is not None:
                visual.clim = item.contrast_limits
        elif isinstance(item, PointsItem):
            visual = scene.visuals.Markers(
                parent=self.scene_view.scene, scaling='scene'
            )
        else:
            raise TypeError(f'cannot draw {item!r}')
        visual.opacity = item.opacity
        visual.visible = item.visible
        self._visuals[item] = visual
        self._set_data(item)
        self._callbacks[item] = partial(self._on_item_change, item)
        item.changed.connect(self._callbacks[item])

    def _remove(self, item: Item) -> None:
        visual = self._visuals.pop(item)
        item.changed.disconnect(self._callbacks.pop(item))
        visual.parent = None

    def _order(self) -> None:
        for i, item in enumerate(self.view.items):
            if item in self._visuals:
                self._visuals[item].order = i

    def _on_item_change(self, item: Item, what: str) -> None:
        visual = self._visuals.get(item)
        if visual is None:
            return
        if what == 'opacity':
            visual.opacity = item.opacity
        elif what == 'visible':
            visual.visible = item.visible
        elif what == 'colormap' and isinstance(item, ImageItem):
            visual.cmap = vispy_colormap(item.colormap)
        elif what == 'contrast_limits' and isinstance(item, ImageItem):
            if item.contrast_limits is not None:
                visual.clim = item.contrast_limits
        elif what == 'interpolation' and isinstance(item, ImageItem):
            visual.interpolation = item.interpolation
        elif what in ('size', 'color', 'symbol'):
            self._set_data(item)
        self.canvas.update()

    def _set_data(self, item: Item) -> None:
        visual = self._visuals[item]
        step = self.view.current_step
        if isinstance(item, ImageItem):
            visual.set_data(item.slice(step))
        elif isinstance(item, PointsItem):
            shown = item.slice(step)
            if len(shown) == 0:
                visual.visible = False
                return
            visual.visible = item.visible
            coords = item.coords[shown][:, -2:]
            color = item.color
            if not isinstance(color, str) and np.ndim(color) == 2:
                color = np.asarray(color)[shown]
            rgba = ColorArray(color).rgba
            visual.set_data(
                pos=coords[:, ::-1],  # x is the column, y the row
                size=item.size[shown],
                face_color=rgba,
                edge_width=0,
                edge_color=rgba,
                symbol=item.symbol,
            )
        self.canvas.update()

    # ---------------------------------- camera ------------------------
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
