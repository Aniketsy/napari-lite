# napari-lite: own code
"""vispy draws a ``ViewerModel``: the canvas, one visual per layer and the
wiring between model and canvas that napari keeps in its ``QtViewer``
(issue 5).

The built-in renderer behind the ``CanvasBackend`` contract
(``napari_lite.backends``).  A front end builds one and puts its
``native`` widget somewhere, or nowhere: ``QtCanvas`` (``qt/canvas.py``)
with ``gui='qt'`` and its own widget as the parent, the notebook window
(``backends/jupyter.py``) with ``gui='jupyter'``, the headless viewer
(``backends/headless.py``) with ``gui=None``.  vispy's application is
chosen here from ``gui``: the Qt binding for a Qt window; otherwise vispy's
egl application where EGL loads (Linux), else the Qt binding with the
widget kept off the screen.  In a notebook the canvas reaches the browser
through a jupyter_rfb widget (``_vispy/_jupyter.py``).

A canvas drawn off the screen is used on the thread that made it, which
in a notebook runs the kernel's loop: work that arrives on another thread
is handed over (``utils/_owner_thread.py``).
"""

from __future__ import annotations

import collections
import contextlib
import logging
import weakref
from typing import TYPE_CHECKING, Any

import numpy as np

from napari_lite._vispy import VispyCanvas, create_vispy_layer
from napari_lite._vispy._qt_optional import (
    default_font_family,
    default_font_manager,
    qt_timers,
    use_vispy_app,
    vispy_app_is_qt,
)
from napari_lite.settings import get_settings
from napari_lite.utils._owner_thread import OwnerThread
from napari_lite.utils.key_bindings import KeymapHandler

if TYPE_CHECKING:
    from collections.abc import Iterator

    from napari_lite._vispy._jupyter import VispyFrameWidget
    from napari_lite._vispy.layers.base import VispyBaseLayer
    from napari_lite.components import ViewerModel
    from napari_lite.layers import Layer
    from napari_lite.utils.events import Event

__all__ = ['GUIS', 'VispyBackend']

# the toolkits this renderer gives a canvas for; None is no window
GUIS = ('qt', 'jupyter', None)


class VispyBackend:
    """napari's vispy canvas for ``viewer``, with its layers kept in step.

    Parameters
    ----------
    viewer : ViewerModel
        The model to draw.  Layers added to it later appear too.
    gui : str or None
        The toolkit the front end places the canvas in: ``'qt'`` (vispy
        draws through the Qt binding in use), ``'jupyter'`` (a notebook
        widget streams the frames) or None for no window.  Without a Qt
        window vispy draws off the screen: with its egl application where
        EGL loads, else through the Qt binding with the widget kept off the
        screen.
    parent : QWidget, optional
        The Qt parent of the canvas widget, for ``gui='qt'``.
    key_map_handler : KeymapHandler, optional
        Receives the canvas key events; made here if not given.
    font_manager, font_family : optional
        The font of the text visuals; by default the one for the
        application vispy runs on (``_qt_optional``).
    size : (int, int), optional
        The canvas size handed to vispy, by default the model's
        ``canvas.size``, as napari hands it.

    Attributes
    ----------
    canvas : VispyCanvas
        napari's canvas (``canvas.native`` is vispy's: the Qt widget, or
        the egl canvas backend).
    app_name : str
        vispy's application backend: the Qt binding, or 'egl'.
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
        if gui not in GUIS:
            raise ValueError(
                "the vispy renderer draws for the 'qt' or 'jupyter' toolkit, "
                f'or for no window; not for {gui!r}'
            )
        if gui == 'jupyter':
            _require_notebook_widgets()  # before vispy's application is chosen
        self.viewer = viewer
        self.gui = gui
        self._closed = False
        self._owner = OwnerThread()
        self.app_name = use_vispy_app('qt' if gui == 'qt' else 'offscreen')
        # no Qt window, but Qt draws: a widget shown off the screen has its
        # GL context and appears nowhere (a never-shown one draws black)
        self._offscreen_widget = gui != 'qt' and vispy_app_is_qt()
        if self._offscreen_widget:
            from napari_lite._qt.qt_event_loop import get_qapp

            # the widget needs the application; IPython's Qt loop stays as
            # it is (a notebook's frames run on asyncio)
            get_qapp(ipython_loop=False)
        self.key_map_handler = key_map_handler or KeymapHandler()
        settings = get_settings()
        # Qt's timers fire only in a Qt window's event loop (_qt_optional)
        with qt_timers(gui == 'qt'):
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
                config={
                    'samples': 4 if settings.advanced.multisampling else 0
                },
            )
        if self.app_name == 'egl':
            self._fill_in_for_egl()
        if self._offscreen_widget:
            self._guard_gl_thread()
        # the slicer reports from its worker thread; the result is applied
        # on the canvas's thread (napari: @ensure_main_thread on QtViewer's
        # _on_slice_ready)
        self._pending_slices: collections.deque[Event] = collections.deque()
        if gui == 'qt':
            from superqt.utils import ensure_main_thread

            self._on_slice_ready = ensure_main_thread(self._apply_slice_ready)
        else:
            self._on_slice_ready = self._slice_ready_off_screen
        self._connections: list[tuple[Any, Any]] = [
            (viewer._layer_slicer.events.ready, self._on_slice_ready),
            (viewer.layers.events.inserted, self._on_add_layer_change),
            (viewer.layers.events.inserted, self._update_camera_depth),
            (viewer.layers.events.removed, self._update_camera_depth),
            (viewer.layers.events.removed, self._forget_removed_layer),
            (viewer.dims.events.ndisplay, self._update_camera_depth),
            (viewer.layers.selection.events.active, self._on_active_change),
        ]
        self._frame_widget: VispyFrameWidget | None = None
        if gui == 'jupyter':
            self._frame_widget = self._make_frame_widget()
            self._connections += [
                (viewer.cursor.events.style, self._on_notebook_cursor),
                (viewer.cursor.events.size, self._on_notebook_cursor),
                (viewer.scene.camera.events.zoom, self._on_notebook_cursor),
            ]
        for emitter, callback in self._connections:
            emitter.connect(callback)
        self._on_active_change()
        for layer in viewer.layers:
            self.add_layer(layer)
        if self._offscreen_widget:
            from qtpy.QtCore import Qt

            widget = self.canvas.native
            widget.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
            widget.show()
        if gui == 'jupyter':
            self._on_notebook_cursor()

    @property
    def native(self) -> Any:
        """The widget a front end places: the Qt widget for ``'qt'``, the
        notebook widget for ``'jupyter'``, None without a window."""
        if self.gui == 'qt':
            return self.canvas.native
        return self._frame_widget

    def key_event(self, event: Any, *, release: bool = False) -> None:
        """A Qt key event from the front end's widget, handed to the
        canvas's key handling as if the canvas had received it.  (The
        notebook widget hands its key events over itself.)"""
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

    # what vispy's backends leave out

    def _fill_in_for_egl(self) -> None:
        """vispy's egl backend changes its size without a resize event (Qt
        and the others send one): napari keeps the model's canvas size, and
        vispy lays out the scene, from that event.  As with Qt, asking for
        the size the canvas has changes nothing and sends no event: napari
        writes every resize back to the canvas through the model, and a
        second resize event inside the first is one vispy refuses.  The
        backend also has no double clicks of its own and makes them from
        presses, without a position; the notebook widget hands the
        browser's over instead."""
        scene_canvas = self.canvas._scene_canvas
        backend = scene_canvas._backend
        set_size = backend._vispy_set_size

        def set_size_and_tell(width: int, height: int) -> None:
            if backend._vispy_get_size() == (width, height):
                return
            set_size(width, height)
            scene_canvas.events.resize(size=(width, height))

        backend._vispy_set_size = set_size_and_tell
        backend._double_click_supported = True
        scene_canvas.events.resize(size=tuple(scene_canvas.size))

    def _guard_gl_thread(self) -> None:
        """Qt ends the process when a GL context is made current on another
        thread than its own; refuse with an error the notebook can show."""
        backend = self.canvas._scene_canvas._backend
        set_current = backend._vispy_set_current
        owner = self._owner

        def set_current_on_owner() -> None:
            if not owner.is_current:
                raise RuntimeError(
                    "napari-lite: the viewer's canvas was used from another "
                    'thread than the one that made the viewer (in JupyterLab '
                    'a widget callback can run on a thread of its own); '
                    'change the viewer from that thread, or dock the widget '
                    'with viewer.window.add_dock_widget'
                )
            set_current()

        backend._vispy_set_current = set_current_on_owner

    # layers

    def add_layer(self, layer: Layer) -> None:
        """Create the vispy visual of ``layer`` and put it in the scene."""
        with qt_timers(self.gui == 'qt'):
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

    def _slice_ready_off_screen(self, event: Event) -> None:
        """A slicing result for a canvas drawn off the screen: applied on
        the canvas's thread, handed to its loop when it has one (a
        notebook), else kept for the next screenshot, which runs there (a
        script)."""
        if self._owner.is_current:
            self._apply_slice_ready(event)
        elif self._owner.can_hand_over:
            self._owner.call(self._apply_slice_ready, event)
        else:
            self._pending_slices.append(event)

    def _apply_pending_slices(self) -> None:
        while self._pending_slices:
            self._apply_slice_ready(self._pending_slices.popleft())

    def _apply_slice_ready(self, event: Event) -> None:
        """Apply the result of asynchronous slicing (same as napari)."""
        responses: dict[weakref.ReferenceType[Layer], Any] = event.value
        logging.getLogger('napari_lite').debug(
            'VispyBackend._apply_slice_ready: %s', responses
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

    # the notebook

    def _make_frame_widget(self) -> VispyFrameWidget:
        """The notebook widget, told whenever the scene wants redrawing:
        vispy asks its canvas backend for an update on every change, and
        the widget then asks the browser for a frame."""
        from napari_lite._vispy._jupyter import VispyFrameWidget

        widget = VispyFrameWidget(self)
        backend = self.canvas._scene_canvas._backend
        update = backend._vispy_update

        def update_and_stream() -> None:
            update()
            widget.scene_changed()

        backend._vispy_update = update_and_stream
        # the first frame, for when the browser shows the widget; vispy
        # passes later changes on once a frame has been drawn
        widget.request_draw()
        return widget

    def _on_notebook_cursor(self) -> None:
        """napari's cursor style as a CSS cursor, with napari's brush
        circle for painting: what ``VispyCanvas._on_cursor`` does with Qt
        cursors."""
        from napari_lite._vispy._jupyter import CSS_CURSORS

        if self._frame_widget is None:
            return
        cursor = self.viewer.cursor
        style = str(cursor.style)
        brush = self.viewer.canvas.overlays._brush_circle
        brush.visible = False
        css = CSS_CURSORS.get(style, 'default')
        if style in ('square', 'circle', 'circle_frozen'):
            size = cursor.size
            if cursor.scaled:
                size *= self.viewer.scene.camera.zoom
            size = int(size)
            # too small or too large to see as a brush: a plain cross
            if (
                size < 8 or size > min(*self.canvas.size) - 4
            ) and style != 'circle_frozen':
                css = 'crosshair'
            elif style.startswith('circle'):
                brush.size = size
                brush.position_is_frozen = style == 'circle_frozen'
                brush.visible = True
        self._frame_widget.cursor = css

    # screenshots

    def _device_pixel_ratio(self) -> float:
        """Device pixels per canvas pixel: a Qt widget's on a HiDPI screen
        (its framebuffer has that many more pixels), else 1."""
        native = self.canvas.native
        ratio = getattr(native, 'devicePixelRatioF', None)
        return float(ratio()) if callable(ratio) else 1.0

    @contextlib.contextmanager
    def resized(
        self,
        size: tuple[int, int] | None = None,
        scale: float = 1.0,
        fit_to_data_extent: bool = False,
        device_pixel_ratio: float | None = None,
    ) -> Iterator[None]:
        """The canvas temporarily at ``size`` (height, width, in device
        pixels) times ``scale``, or sized tightly around the data, one
        device pixel per data pixel; the camera is restored afterwards.
        Waits for slicing first, so what is drawn inside is complete.
        ``device_pixel_ratio``: by default the canvas's own."""
        if size is not None and len(size) != 2:
            raise ValueError(
                f'screenshot size must be 2 values, got {len(size)}'
            )
        if device_pixel_ratio is None:
            device_pixel_ratio = self._device_pixel_ratio()
        try:
            self.viewer._layer_slicer.wait_until_idle(timeout=5)
        except TimeoutError as e:  # pragma: no cover
            raise TimeoutError(
                'Slicing was too slow. Wait for all layers to load before '
                'taking a screenshot, or disable async slicing.'
            ) from e
        self._apply_pending_slices()

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
        if self._offscreen_widget and not self._owner.is_current:
            # Qt would make the widget's context current here, and end the
            # process for it
            raise RuntimeError(
                "napari-lite: the viewer's canvas can only be drawn on the "
                'thread that made the viewer'
            )
        if hasattr(self.canvas.native, 'grabFramebuffer'):
            # Qt: the widget's framebuffer, as napari does; it draws for a
            # widget that is shown, on the screen or off it
            from napari_lite._qt.utils import QImg2array

            return QImg2array(self.canvas.screenshot())
        # egl: vispy renders into its own framebuffer
        scene_canvas = self.canvas._scene_canvas
        try:
            self.canvas.on_draw(None)
            array = scene_canvas.render(alpha=True)
        except ImportError as e:
            if 'freetype' not in str(e):
                raise
            raise ImportError(
                'text drawn without Qt needs freetype-py: pip install '
                "'napari-lite[headless]'"
            ) from e
        # vispy passes one update to the backend until the next draw event
        # (SceneCanvas.update); render() is no draw event, so say it here,
        # or later changes would never ask for a frame
        scene_canvas._update_pending = False
        return array

    def screenshot(
        self,
        *,
        size: tuple[int, int] | None = None,
        scale: float = 1.0,
        fit_to_data_extent: bool = False,
        device_pixel_ratio: float | None = None,
    ) -> np.ndarray:
        """The canvas drawn at ``size`` times ``scale`` (or around the
        data), as an RGBA uint8 array.  Off the screen, a call from another
        thread is drawn on the canvas's own and waits for it."""
        if self._hand_over():
            return self._owner.run(
                self.screenshot,
                size=size,
                scale=scale,
                fit_to_data_extent=fit_to_data_extent,
                device_pixel_ratio=device_pixel_ratio,
            )
        with self.resized(size, scale, fit_to_data_extent, device_pixel_ratio):
            return self.capture()

    # lifecycle

    def _hand_over(self) -> bool:
        """Whether this call is for the canvas's own thread: a canvas drawn
        off the screen, called from another thread that can reach it."""
        return (
            self.gui != 'qt'
            and not self._owner.is_current
            and self._owner.can_hand_over
        )

    def close(self) -> None:
        """Let the model go and release the canvas (once)."""
        if self._closed:
            return
        if self._hand_over():
            self._owner.run(self.close)
            return
        self._closed = True
        for emitter, callback in self._connections:
            emitter.disconnect(callback)
        self._connections = []
        if self._frame_widget is not None:
            # with the output widget jupyter_rfb made for its error messages
            output = getattr(self._frame_widget, '_output_context', None)
            self._frame_widget.close()
            if output is not None:
                output.close()
        if self._offscreen_widget:
            self._close_offscreen_widget()
        else:
            self.canvas.delete()
        if self.app_name == 'egl':
            _release_egl(self.canvas._scene_canvas)

    def _close_offscreen_widget(self) -> None:
        """No event loop runs to delete the widget later (deleteLater), and
        it is the widget's deletion that cuts the canvas from the model:
        both happen now."""
        from qtpy.QtCore import QCoreApplication, QEvent

        widget = self.canvas.native
        widget.hide()
        self.canvas._disconnect_events()
        self.canvas.delete()
        QCoreApplication.sendPostedEvents(widget, QEvent.Type.DeferredDelete)


def _require_notebook_widgets() -> None:
    try:
        import ipywidgets  # noqa: F401
        import jupyter_rfb  # noqa: F401
    except ImportError as e:
        raise ImportError(
            f"Viewer(gui='jupyter') needs {e.name}: pip install "
            "'napari-lite[jupyter]'"
        ) from e


def _release_egl(scene_canvas: Any) -> None:
    """vispy's egl backend keeps every canvas it made in a module list and
    never destroys their contexts; a closed canvas lets both go."""
    try:
        import ctypes

        from vispy.app.backends import _egl
    except ImportError:  # pragma: no cover
        return
    backend = getattr(scene_canvas, '_backend', None)
    if backend in _egl._VP_EGL_ALL_WINDOWS:
        _egl._VP_EGL_ALL_WINDOWS.remove(backend)
    context = getattr(backend, '_native_context', None)
    shared = getattr(getattr(scene_canvas, 'context', None), 'shared', None)
    if context is None or getattr(shared, 'ref', None) is not backend:
        return  # not this canvas's own context
    egl = _egl.egl
    with contextlib.suppress(Exception):
        egl.eglMakeCurrent(
            _egl._EGL_DISPLAY,
            egl.EGL_NO_SURFACE,
            egl.EGL_NO_SURFACE,
            egl.EGL_NO_CONTEXT,
        )
        destroy = egl._lib.eglDestroyContext
        destroy.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        destroy.restype = ctypes.c_uint
        destroy(_egl._EGL_DISPLAY, context)
        backend._native_context = None
