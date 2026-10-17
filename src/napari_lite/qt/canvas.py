# napari-lite: own code
"""``QtCanvas``: napari's canvas, dims sliders and status line in one widget.

This is the part of napari's ``QtViewer`` that draws layers and reacts to
the mouse and keyboard, without the layer list, layer controls, console,
welcome screen, menus and file dialogs.  It can live on its own in any Qt
layout:

    viewer = ViewerModel()
    viewer.add_image(image)
    canvas = QtCanvas(viewer)
    canvas.show()

``napari_lite.Viewer`` wraps one in a window (issue 13).
"""

from __future__ import annotations

import contextlib
import logging
import weakref
from typing import TYPE_CHECKING, Any, ClassVar, Literal
from weakref import WeakSet

import numpy as np
from qtpy.QtCore import QCoreApplication, Qt
from qtpy.QtGui import QGuiApplication
from qtpy.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget
from superqt import QElidingLabel

import napari_lite.qt._viewer_actions  # noqa: F401  (re-registers two actions)
from napari_lite._qt.utils import QImg2array, use_tabular_numerals
from napari_lite._qt.widgets.qt_dims import QtDims
from napari_lite._vispy import VispyCanvas, create_vispy_layer
from napari_lite._vispy.utils.qt_font import QtFontManager
from napari_lite.settings import get_settings
from napari_lite.utils.action_manager import bind_shortcuts_from_settings
from napari_lite.utils.io import imsave
from napari_lite.utils.key_bindings import KeymapHandler

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from qtpy.QtGui import QCloseEvent, QImage, QKeyEvent

    from napari_lite._vispy.layers.base import VispyBaseLayer
    from napari_lite.components import ViewerModel
    from napari_lite.layers import Layer
    from napari_lite.utils.events import Event

__all__ = ['QtCanvas', 'QtStatusLine']


class QtStatusLine(QWidget):
    """One line under the canvas: status text, cursor coordinates and the
    help text of the active layer (napari shows these in its status bar)."""

    def __init__(self, viewer: ViewerModel, parent: QWidget | None = None):
        super().__init__(parent)
        self.viewer = viewer
        self._status = QLabel('Ready')
        self._coordinates = QElidingLabel('')
        self._coordinates.setObjectName('coordinates status')
        self._help = QElidingLabel('')
        self._help.setObjectName('help status')
        self._help.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        layout = QHBoxLayout()
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(12)
        layout.addWidget(self._status)
        layout.addWidget(self._coordinates, stretch=1)
        layout.addWidget(self._help, stretch=1)
        self.setLayout(layout)
        use_tabular_numerals(self)

        viewer.events.status.connect(self._on_status)
        viewer.events.help.connect(self._on_help)

    def _on_status(self, event: Event) -> None:
        value = event.value
        if isinstance(value, str):
            self._status.setText(value)
            self._coordinates.setText('')
        else:  # the dict napari builds for a single layer
            self._status.setText(value.get('layer_base', ''))
            self._coordinates.setText(value.get('coordinates', ''))

    def _on_help(self, event: Event) -> None:
        self._help.setText(event.value)


class QtCanvas(QWidget):
    """Canvas, dims sliders and status line for a ``ViewerModel``.

    Parameters
    ----------
    viewer : ViewerModel
        The model to show.  Layers added to it later appear too.
    parent : QWidget, optional
        Qt parent.
    show_status : bool
        Show the status line under the sliders (default True).

    Attributes
    ----------
    canvas : VispyCanvas
        napari's vispy canvas (``canvas.native`` is the Qt widget).
    dims : QtDims
        The dimension sliders.
    status : QtStatusLine or None
        The status line.
    """

    _instances: ClassVar[WeakSet[QtCanvas]] = WeakSet()

    def __init__(
        self,
        viewer: ViewerModel,
        parent: QWidget | None = None,
        *,
        show_status: bool = True,
    ) -> None:
        super().__init__(parent)
        self._instances.add(self)
        # with a stylesheet active, fonts (e.g. tabular numerals) only
        # propagate from parent to child widgets with this attribute
        QCoreApplication.setAttribute(
            Qt.ApplicationAttribute.AA_UseStyleSheetPropagationInWidgetStyles,
            True,
        )
        self.viewer = viewer
        self._key_map_handler = KeymapHandler()
        self._key_map_handler.keymap_providers = [viewer]
        self._font_manager = QtFontManager()
        self._overlay_font = QGuiApplication.font().family()

        settings = get_settings()
        self.canvas: VispyCanvas = VispyCanvas(
            viewer=viewer,
            parent=self,
            font_manager=self._font_manager,
            font_family=self._overlay_font,
            key_map_handler=self._key_map_handler,
            size=viewer.canvas.size,
            autoswap=settings.advanced.autoswap_buffers,
            config={'samples': 4 if settings.advanced.multisampling else 0},
        )
        self.dims: QtDims = QtDims(viewer.dims)
        self.status: QtStatusLine | None = (
            QtStatusLine(viewer) if show_status else None
        )

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(0)
        layout.addWidget(self.canvas.native, stretch=1)
        layout.addWidget(self.dims)
        if self.status is not None:
            layout.addWidget(self.status)
        self.setLayout(layout)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        viewer._layer_slicer.events.ready.connect(self._on_slice_ready)
        viewer.layers.events.inserted.connect(self._update_camera_depth)
        viewer.layers.events.removed.connect(self._update_camera_depth)
        viewer.dims.events.ndisplay.connect(self._update_camera_depth)
        viewer.layers.selection.events.active.connect(self._on_active_change)
        viewer.layers.events.inserted.connect(self._on_add_layer_change)

        # shortcuts from the settings, bound to the registered actions
        bind_shortcuts_from_settings()

        self._on_active_change()
        for layer in viewer.layers:
            self._add_layer(layer)

    # ------------------------------------------------------------------
    # layers
    # ------------------------------------------------------------------

    @property
    def layer_to_visual(self) -> dict[Layer, VispyBaseLayer]:
        """Mapping of napari layer to its vispy visual."""
        return self.canvas.layer_to_visual

    def _on_add_layer_change(self, event: Event) -> None:
        self._add_layer(event.value)

    def _add_layer(self, layer: Layer) -> None:
        """Create the vispy visual of ``layer`` and put it in the scene."""
        vispy_layer = create_vispy_layer(
            layer, font_info=self.canvas.font_info()
        )
        self.canvas.add_layer_visual_mapping(layer, vispy_layer)

    def _on_active_change(self) -> None:
        """Keys go to the active layer first, then to the viewer."""
        active = self.viewer.layers.selection.active
        self._key_map_handler.keymap_providers = (
            [self.viewer] if active is None else [active, self.viewer]
        )

    def _on_slice_ready(self, event: Event) -> None:
        """Apply the result of asynchronous slicing (same as napari)."""
        responses: dict[weakref.ReferenceType[Layer], Any] = event.value
        logging.getLogger('napari_lite').debug(
            'QtCanvas._on_slice_ready: %s', responses
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

    # ------------------------------------------------------------------
    # mouse and keyboard
    # ------------------------------------------------------------------

    def _enter_canvas(self) -> None:
        """Called by the vispy canvas when the mouse enters it."""
        self.viewer.status = 'Ready'
        self.viewer.mouse_over_canvas = True

    def _leave_canvas(self) -> None:
        """Called by the vispy canvas when the mouse leaves it."""
        self.viewer.status = ''
        self.viewer.mouse_over_canvas = False

    def keyPressEvent(self, event: QKeyEvent | None) -> None:
        """Keys pressed anywhere in the widget go to the canvas key handler."""
        if event is None:
            return
        self.canvas._scene_canvas._backend._keyEvent(
            self.canvas._scene_canvas.events.key_press, event
        )
        event.accept()

    def keyReleaseEvent(self, event: QKeyEvent | None) -> None:
        if event is None:
            return
        self.canvas._scene_canvas._backend._keyEvent(
            self.canvas._scene_canvas.events.key_release, event
        )
        event.accept()

    # ------------------------------------------------------------------
    # screenshots
    # ------------------------------------------------------------------

    def screenshot(
        self,
        path: str | Path | None = None,
        flash: bool = False,
        size: tuple[int, int] | None = None,
        scale: float = 1.0,
        fit_to_data_extent: bool = False,
    ) -> np.ndarray[tuple[int, int, Literal[4]], np.dtype[np.uint8]]:
        """Render the canvas to an RGBA array (and save it if ``path``).

        Parameters
        ----------
        path : str or Path, optional
            File to save the image to.
        flash : bool
            Flash the widget after capturing (default False).
        size : (int, int), optional
            Height and width of the screenshot in pixels; default: as shown.
        scale : float
            Scale factor applied to the canvas size.
        fit_to_data_extent : bool
            Size the canvas tightly around the data before capturing.
        """
        img = QImg2array(
            self._screenshot(
                flash=flash,
                size=size,
                scale=scale,
                fit_to_data_extent=fit_to_data_extent,
            )
        )
        if path is not None:
            imsave(str(path), img)
        return img

    def _screenshot(
        self,
        flash: bool = False,
        size: tuple[int, int] | None = None,
        scale: float = 1.0,
        fit_to_data_extent: bool = False,
    ) -> QImage:
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

        with self.resize_canvas(size, scale):
            if fit_to_data_extent:
                self.viewer.fit_to_view(margin=0)
            img = self.canvas.screenshot()
            if flash:
                from napari_lite._qt.utils import add_flash_animation

                add_flash_animation(self)
            return img

    @contextlib.contextmanager
    def resize_canvas(
        self, size: tuple[int, int] | None, scale: float
    ) -> Iterator[None]:
        """Temporarily resize the canvas, keeping the camera."""
        canvas = self.canvas
        prev_size = canvas.size
        camera = self.viewer.scene.camera
        old_center = camera.center
        old_zoom = camera.zoom
        if size is not None:
            size_arr = np.asarray(size) / self.devicePixelRatio()
        else:
            size_arr = np.asarray(prev_size)
        size_arr = (size_arr * scale).astype(np.int64)
        canvas.size = tuple(size_arr)
        try:
            yield
        finally:
            canvas.size = prev_size
            camera.center = old_center
            camera.zoom = old_zoom

    def clipboard(self, flash: bool = False) -> None:
        """Copy a screenshot of the canvas to the clipboard."""
        cb = QGuiApplication.clipboard()
        if cb is not None:
            cb.setImage(self._screenshot(flash))

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------

    def closeEvent(self, event: QCloseEvent | None) -> None:
        """Stop the animation thread and release the vispy canvas."""
        self.dims.stop()
        self.canvas.delete()
        if event is not None:
            event.accept()
