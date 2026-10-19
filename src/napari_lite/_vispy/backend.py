# napari-lite: own code
"""vispy draws a ``ViewerModel``: the canvas, one visual per layer and the
wiring between model and canvas that napari keeps in its ``QtViewer``
(docs/backends.md).

The built-in renderer behind the ``CanvasBackend`` contract
(``napari_lite.backends``).  A front end builds one and puts its
``native`` widget somewhere, or nowhere: ``QtCanvas`` (``qt/canvas.py``)
with ``gui='qt'`` and its own widget as the parent, the headless viewer
(``backends/headless.py``) with ``gui=None``.  vispy's application is
chosen here from ``gui``: the Qt binding, or an offscreen one (egl,
osmesa) where it exists and otherwise the Qt binding with the widget
kept off the screen.
"""

from __future__ import annotations

import contextlib
import logging
import weakref
from typing import TYPE_CHECKING, Any

import numpy as np

from napari_lite._vispy import VispyCanvas, create_vispy_layer
from napari_lite._vispy._qt_optional import (
    default_font_family,
    default_font_manager,
    use_vispy_app,
    vispy_app_is_qt,
)
from napari_lite.settings import get_settings
from napari_lite.utils.key_bindings import KeymapHandler

if TYPE_CHECKING:
    from collections.abc import Iterator

    from napari_lite._vispy.layers.base import VispyBaseLayer
    from napari_lite.components import ViewerModel
    from napari_lite.layers import Layer
    from napari_lite.utils.events import Event

__all__ = ['VispyBackend']


class VispyBackend:
    """napari's vispy canvas for ``viewer``, with its layers kept in step.

    Parameters
    ----------
    viewer : ViewerModel
        The model to draw.  Layers added to it later appear too.
    gui : str or None
        The front end: ``'qt'`` (vispy draws through the Qt binding in
        use) or None for no window (an offscreen application where one
        exists, else the Qt binding with the widget kept off the screen).
    parent : QWidget, optional
        The Qt parent of the canvas widget; None for a top-level widget,
        or when vispy runs without Qt.
    key_map_handler : KeymapHandler, optional
        Receives the canvas key events; made here if not given.
    font_manager, font_family : optional
        The font of the text visuals; by default the one for the
        application vispy runs on (``_qt_optional``).
    size : (int, int), optional
        Canvas size as (height, width); by default the model's.

    Attributes
    ----------
    canvas : VispyCanvas
        napari's canvas (``canvas.native`` is the widget, or the
        offscreen canvas backend).
    app_name : str
        vispy's application backend: the Qt binding, 'egl' or 'osmesa'.
    key_map_handler : KeymapHandler
        Keys go to the active layer first, then to the viewer.
    """

    def __init__(
        self,
        viewer: ViewerModel,
        *,
        gui: str | None = None,
        parent: Any = None,
        key_map_handler: KeymapHandler | None = None,
        font_manager: Any = None,
        font_family: str | None = None,
        size: tuple[int, int] | None = None,
    ) -> None:
        if gui not in ('qt', None):
            raise ValueError(
                f"the vispy renderer draws for the 'qt' front end or for "
                f'none; not for {gui!r}'
            )
        self.viewer = viewer
        self.gui = gui
        self.app_name = use_vispy_app('qt' if gui == 'qt' else 'offscreen')
        # no window, but Qt draws: a widget shown off the screen has its
        # GL context and appears nowhere (a never-shown one draws black)
        self._offscreen_widget = gui is None and vispy_app_is_qt()
        if self._offscreen_widget:
            from napari_lite._qt.qt_event_loop import get_qapp

            get_qapp()  # the widget needs the application to exist
        self.key_map_handler = key_map_handler or KeymapHandler()
        settings = get_settings()
        self.canvas: VispyCanvas = VispyCanvas(
            viewer=viewer,
            key_map_handler=self.key_map_handler,
            font_manager=(
                default_font_manager()
                if font_manager is None
                else font_manager
            ),
            font_family=font_family or default_font_family(),
            parent=parent,
            size=viewer.canvas.size if size is None else size,
            autoswap=settings.advanced.autoswap_buffers,
            config={'samples': 4 if settings.advanced.multisampling else 0},
        )
        self._connections = (
            (viewer._layer_slicer.events.ready, self._on_slice_ready),
            (viewer.layers.events.inserted, self._on_add_layer_change),
            (viewer.layers.events.inserted, self._update_camera_depth),
            (viewer.layers.events.removed, self._update_camera_depth),
            (viewer.layers.events.removed, self._forget_removed_layer),
            (viewer.dims.events.ndisplay, self._update_camera_depth),
            (viewer.layers.selection.events.active, self._on_active_change),
        )
        for emitter, callback in self._connections:
            emitter.connect(callback)
        self._on_active_change()
        for layer in viewer.layers:
            self.add_layer(layer)
        if self._offscreen_widget:
            from qtpy.QtCore import Qt

            self.native.setAttribute(
                Qt.WidgetAttribute.WA_DontShowOnScreen, True
            )
            self.native.show()

    @property
    def native(self) -> Any:
        """The canvas widget (Qt), or vispy's offscreen canvas backend
        (which no front end places)."""
        return self.canvas.native

    def key_event(self, event: Any, *, release: bool = False) -> None:
        """A Qt key event from the front end's widget, handed to the
        canvas's key handling as if the canvas had received it."""
        scene_canvas = self.canvas._scene_canvas
        if not hasattr(scene_canvas._backend, '_keyEvent'):
            return  # no Qt widget, so no Qt key events either
        emitter = (
            scene_canvas.events.key_release
            if release
            else scene_canvas.events.key_press
        )
        scene_canvas._backend._keyEvent(emitter, event)

    @property
    def layer_to_visual(self) -> dict[Layer, VispyBaseLayer]:
        """Mapping of napari layer to its vispy visual."""
        return self.canvas.layer_to_visual

    # layers

    def add_layer(self, layer: Layer) -> None:
        """Create the vispy visual of ``layer`` and put it in the scene."""
        vispy_layer = create_vispy_layer(
            layer, font_info=self.canvas.font_info()
        )
        self.canvas.add_layer_visual_mapping(layer, vispy_layer)

    def _on_add_layer_change(self, event: Event) -> None:
        self.add_layer(event.value)

    def _forget_removed_layer(self, event: Event) -> None:
        """Drop the selection's "current" item when that layer is removed.

        In napari the Qt layer list keeps ``selection._current`` in step with
        its current row, so a removed layer is released.  Without one the
        canvas does it; otherwise the layer (and its data) would stay alive
        until another layer became current.
        """
        selection = self.viewer.layers.selection
        if selection._current is event.value:
            selection._current = selection.active

    def _on_active_change(self) -> None:
        """Keys go to the active layer first, then to the viewer."""
        active = self.viewer.layers.selection.active
        self.key_map_handler.keymap_providers = (
            [self.viewer] if active is None else [active, self.viewer]
        )

    def _on_slice_ready(self, event: Event) -> None:
        """Apply the result of asynchronous slicing (same as napari)."""
        responses: dict[weakref.ReferenceType[Layer], Any] = event.value
        logging.getLogger('napari_lite').debug(
            'VispyBackend._on_slice_ready: %s', responses
        )
        for weak_layer, response in responses.items():
            if layer := weak_layer():
                layer._slicing_state._update_slice_response(response)
                layer._slicing_state._update_loaded_slice_id(
                    response.request_id
                )
                layer.events.set_data()
                layer._refresh_sync(
                    data_displayed=False,
                    thumbnail=True,
                    highlight=True,
                    extent=False,
                )

    def _update_camera_depth(self) -> None:
        """Keep the 3D camera's depth range close to the data (napari #2138)."""
        if self.viewer.dims.ndisplay == 2:
            return
        extent = self.viewer.layers.extent
        extent_all = extent.world[1] - extent.world[0] + extent.step
        extent_displayed = extent_all[list(self.viewer.dims.displayed)]
        diameter = np.linalg.norm(extent_displayed)
        # see napari's QtViewer._update_camera_depth for the reasoning
        max_depth = 2.0 / (10.0 * np.finfo(np.float32).eps)
        for camera in [self.canvas.camera, *self.canvas.grid_cameras]:
            camera._3D_camera.depth_value = min(128 * diameter, max_depth)

    # screenshots

    @contextlib.contextmanager
    def resized(
        self,
        size: tuple[int, int] | None = None,
        scale: float = 1.0,
        fit_to_data_extent: bool = False,
        device_pixel_ratio: float = 1.0,
    ) -> Iterator[None]:
        """The canvas temporarily at ``size`` (height, width, in pixels)
        times ``scale``, or sized tightly around the data, one canvas
        pixel per data pixel; the camera is restored afterwards.  Waits
        for slicing first, so what is drawn inside is complete."""
        if size is not None and len(size) != 2:
            raise ValueError(
                f'screenshot size must be 2 values, got {len(size)}'
            )
        try:
            self.viewer._layer_slicer.wait_until_idle(timeout=5)
        except TimeoutError as e:  # pragma: no cover
            raise TimeoutError(
                'Slicing was too slow. Wait for all layers to load before '
                'taking a screenshot, or disable async slicing.'
            ) from e

        if fit_to_data_extent:
            ndisplay = self.viewer.dims.ndisplay
            extent, scene_size, _ = self.viewer._get_scene_parameters()
            extent_scale = min(self.viewer.layers.extent.step[-ndisplay:])
            if ndisplay == 3:
                scene_size = self.viewer._calculate_bounding_box(
                    extent=extent,
                    view_direction=self.viewer.scene.camera.view_direction,
                    up_direction=self.viewer.scene.camera.up_direction,
                )
            grid_shape = self.viewer.canvas.grid.actual_shape(
                self.viewer.layers
            )
            size = np.ceil(scene_size / extent_scale * grid_shape).astype(int)

        canvas = self.canvas
        prev_size = canvas.size
        camera = self.viewer.scene.camera
        old_center = camera.center
        old_zoom = camera.zoom
        if size is not None:
            size_arr = np.asarray(size) / device_pixel_ratio
        else:
            size_arr = np.asarray(prev_size)
        size_arr = (size_arr * scale).astype(np.int64)
        canvas.size = tuple(size_arr)
        try:
            if fit_to_data_extent:
                self.viewer.fit_to_view(margin=0)
            yield
        finally:
            canvas.size = prev_size
            camera.center = old_center
            camera.zoom = old_zoom

    def capture(self) -> np.ndarray:
        """Draw now and return the canvas as an RGBA uint8 array."""
        if hasattr(self.native, 'grabFramebuffer'):
            # Qt: the widget's framebuffer, as napari does; it draws for a
            # widget that is shown, on the screen or off it
            from napari_lite._qt.utils import QImg2array

            return QImg2array(self.canvas.screenshot())
        # an offscreen application: vispy renders into its own framebuffer
        self.canvas.on_draw(None)
        return self.canvas._scene_canvas.render(alpha=True)

    def screenshot(
        self,
        *,
        size: tuple[int, int] | None = None,
        scale: float = 1.0,
        fit_to_data_extent: bool = False,
        device_pixel_ratio: float = 1.0,
    ) -> np.ndarray:
        """The canvas drawn at ``size`` times ``scale`` (or around the
        data), as an RGBA uint8 array."""
        with self.resized(size, scale, fit_to_data_extent, device_pixel_ratio):
            return self.capture()

    # lifecycle

    def close(self) -> None:
        """Let the model go and release the canvas."""
        for emitter, callback in self._connections:
            emitter.disconnect(callback)
        if self._offscreen_widget:
            self.native.hide()
        self.canvas.delete()
