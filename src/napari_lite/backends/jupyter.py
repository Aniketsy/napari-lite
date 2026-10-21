# napari-lite: own code
"""A viewer in a notebook cell: ``Viewer(gui='jupyter')`` (issue 5).

The canvas is the renderer's notebook widget: for vispy, a jupyter_rfb
widget that streams the frames of an off-screen canvas, so the mouse and
the keys work on it as in a window.  Around it, ipywidgets: a slider with
a play button for each dimension that is not displayed, a small layer
list (visibility, selection), 2D/3D and reset-view buttons, the status
line, and whatever ``add_dock_widget`` adds.  Layer controls are the
model's API from code (``layer.contrast_limits = ...``): a front end owns
its widgets, and this one stays small.

Needs the ``jupyter`` extra: jupyter_rfb and ipywidgets.

The window's widgets, and the ones docked next to it, have their
messages handled on the kernel's main shell, the thread that made the
viewer, also where JupyterLab sends widget messages to a subshell, a
thread of its own; a callback that still arrives on another thread is
handed over (``utils/_owner_thread.py``).
"""

from __future__ import annotations

import contextlib
import html
import tempfile
import weakref
from collections.abc import Callable, Iterator, Sequence
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

try:
    import ipywidgets as widgets
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "Viewer(gui='jupyter') needs ipywidgets: pip install "
        "'napari-lite[jupyter]'"
    ) from e

from napari_lite.backends import CanvasBackend, resolve_renderer
from napari_lite.utils._owner_thread import OwnerThread, on_main_shell
from napari_lite.utils.action_manager import bind_shortcuts_from_settings
from napari_lite.utils.io import imsave
from napari_lite.utils.task_status import TaskStatusManager

if TYPE_CHECKING:
    import uuid

    import numpy as np

    from napari_lite.components import ViewerModel
    from napari_lite.layers import Layer
    from napari_lite.utils.task_status import Status

__all__ = ['JupyterWindow']

_SIDE_WIDTH = '230px'


class JupyterWindow:
    """The window of a ``Viewer`` in a notebook: ipywidgets around the
    renderer's notebook widget.

    Parameters
    ----------
    viewer : ViewerModel
        The viewer shown.
    show : bool
        Display the window in the output of the running cell right away
        (default True).
    renderer : str or callable, optional
        The renderer's name or class (``napari_lite.backends``); None for
        the default (``NAPARI_LITE_RENDERER``, else vispy).  It must give
        an ipywidget as its ``native`` for ``gui='jupyter'``.

    Attributes
    ----------
    widget : ipywidgets.HBox
        The whole window, to display or to put in your own layout.
    backend : CanvasBackend
        The renderer.
    """

    # weak: the list keeps no window alive (ipywidgets keep an open
    # window's widgets, and so the window, until it is closed)
    _instances: ClassVar[list[weakref.ref[JupyterWindow]]] = []

    def __init__(
        self,
        viewer: ViewerModel,
        *,
        show: bool = True,
        renderer: Any = None,
    ) -> None:
        self.viewer = viewer
        self._owner = OwnerThread()
        self._task_status_manager = TaskStatusManager()
        self.backend: CanvasBackend = resolve_renderer(
            'default' if renderer is None else renderer, gui='jupyter'
        )(viewer, gui='jupyter')
        canvas = self.backend.native
        if not isinstance(canvas, widgets.Widget):
            self.backend.close()
            raise TypeError(
                f'the renderer {type(self.backend).__name__} gives no '
                f'notebook widget for its canvas (got {canvas!r})'
            )
        self._canvas = canvas
        self._closed = False
        self._updating = False
        self._connections: list[tuple[Any, Callable[..., Any]]] = []
        self._layer_connections: dict[int, list[tuple[Any, Any]]] = {}
        self._slider_widgets: list[widgets.Widget] = []
        self._sliders_by_axis: dict[int, widgets.IntSlider] = {}
        self._row_widgets: list[widgets.Widget] = []
        self._name_buttons: dict[int, widgets.Button] = {}
        self._visible_boxes: dict[int, widgets.Checkbox] = {}
        self._docks: dict[str, tuple[widgets.Box, Any]] = {}
        self._unnamed_dock_count = 1
        self._slider_spec: list[tuple[int, int, str]] = []
        self._status_due = False  # an update is scheduled
        self._status_dirty = False  # the cursor moved while waiting

        self._title = widgets.HTML()
        self._ndisplay = widgets.ToggleButton(
            description='3D',
            tooltip='Show the last three dimensions in 3D',
            layout=widgets.Layout(width='56px'),
        )
        self._reset = widgets.Button(
            description='Reset view',
            tooltip='Fit the data in the canvas',
            layout=widgets.Layout(width='auto'),
        )
        self._layers_title = widgets.HTML('<b>Layers</b>')
        self._layer_rows = widgets.VBox()
        self._left_docks = widgets.VBox()
        self._sliders = widgets.VBox()
        self._status = widgets.HTML()
        self._help = widgets.HTML(layout=widgets.Layout(margin='0 0 0 auto'))
        self._status_row = widgets.HBox(
            [self._status, self._help], layout=widgets.Layout(width='100%')
        )
        self._bottom_docks = widgets.VBox()
        self._right_docks = widgets.VBox()
        self._buttons_row = widgets.HBox([self._ndisplay, self._reset])
        self._side = widgets.VBox(
            [
                self._title,
                self._buttons_row,
                self._layers_title,
                self._layer_rows,
                self._left_docks,
            ],
            layout=widgets.Layout(width=_SIDE_WIDTH, min_width=_SIDE_WIDTH),
        )
        self._main = widgets.VBox(
            [canvas, self._sliders, self._status_row, self._bottom_docks]
        )
        self.widget = widgets.HBox([self._side, self._main, self._right_docks])
        self._own_widgets: list[widgets.Widget] = [
            self._title,
            self._ndisplay,
            self._reset,
            self._layers_title,
            self._layer_rows,
            self._left_docks,
            self._sliders,
            self._status,
            self._help,
            self._status_row,
            self._bottom_docks,
            self._right_docks,
            self._buttons_row,
            self._side,
            self._main,
            self.widget,
        ]

        # their messages are handled on the kernel's main shell, the
        # viewer's thread, not on a subshell (utils/_owner_thread.py)
        on_main_shell(*self._own_widgets)
        self._ndisplay.observe(
            self._owned(self._on_ndisplay_button), names='value'
        )
        self._reset.on_click(self._owned(self._on_reset_button))

        dims = viewer.dims
        layers = viewer.layers
        self._connect(viewer.events.title, self._update_title)
        self._connect(viewer.events.status, self._update_status)
        self._connect(viewer.events.help, self._update_status)
        self._connect(dims.events.ndisplay, self._update_ndisplay_button)
        for name in ('ndim', 'ndisplay', 'order', 'range', 'axis_labels'):
            self._connect(getattr(dims.events, name), self._rebuild_sliders)
        self._connect(dims.events.current_step, self._update_sliders)
        for name in ('inserted', 'removed', 'moved', 'reordered'):
            self._connect(getattr(layers.events, name), self._rebuild_layers)
        self._connect(layers.selection.events.changed, self._update_selection)
        self._connect(layers.selection.events.active, self._update_selection)

        # The model computes the status text on every cursor move; here at
        # most every 50 ms, the last position always shown, as the Qt
        # canvas does: each update is two widget messages to the browser.
        viewer.cursor.events.position.disconnect(
            viewer.update_status_from_cursor
        )
        viewer.cursor.events.position.connect(self._on_cursor_position)

        # napari's shortcuts (arrow keys through the slices, ...) bound to
        # their actions, as the Qt canvas does
        bind_shortcuts_from_settings()

        self._update_title()
        self._update_status()
        self._update_ndisplay_button()
        self._rebuild_sliders()
        self._rebuild_layers()
        JupyterWindow._instances.append(weakref.ref(self))
        if show:
            self.show()

    def _connect(self, emitter: Any, callback: Callable[..., Any]) -> None:
        emitter.connect(callback)
        self._connections.append((emitter, callback))

    def _owned(self, method: Callable[..., Any]) -> Callable[..., None]:
        """``method`` as a widget callback that runs on the window's own
        thread, wherever the widget message arrives."""

        def call(*args: Any) -> None:
            self._owner.call(method, *args)

        return call

    @classmethod
    def current_viewer(cls) -> ViewerModel | None:
        """The viewer of the notebook window shown or activated last."""
        for ref in reversed(cls._instances):
            window = ref()
            if window is not None:
                return window.viewer
        return None

    def _forget(self) -> None:
        JupyterWindow._instances[:] = [
            ref
            for ref in JupyterWindow._instances
            if ref() is not None and ref() is not self
        ]

    def _ipython_display_(self) -> None:
        from IPython.display import display

        display(self.widget)

    # the title, the status line and the buttons

    def _update_title(self, event: Any = None) -> None:
        self._title.value = f'<b>{html.escape(self.viewer.title)}</b>'

    def _update_status(self, event: Any = None) -> None:
        status = self.viewer.status
        if isinstance(status, dict):  # the dict napari builds for a layer
            text = ' '.join(
                part
                for part in (
                    status.get('layer_base', ''),
                    status.get('coordinates', ''),
                )
                if part
            )
        else:
            text = str(status)
        self._status.value = html.escape(text)
        self._help.value = html.escape(self.viewer.help)

    def _on_cursor_position(self) -> None:
        if self._status_due:
            self._status_dirty = True
            return
        self.viewer.update_status_from_cursor()
        self._status_due = self._owner.schedule(0.05, self._status_timeout)

    def _status_timeout(self) -> None:
        self._status_due = False
        if self._status_dirty:
            self._status_dirty = False
            self._on_cursor_position()

    def _update_ndisplay_button(self, event: Any = None) -> None:
        with self._quiet():
            self._ndisplay.value = self.viewer.dims.ndisplay == 3

    def _on_ndisplay_button(self, change: dict[str, Any]) -> None:
        if not self._updating:
            self.viewer.dims.ndisplay = 3 if change['new'] else 2

    def _on_reset_button(self, button: widgets.Button) -> None:
        self.viewer.reset_view()

    @contextlib.contextmanager
    def _quiet(self) -> Iterator[None]:
        """Within, the window's changes to its own widgets do not go back
        to the model."""
        before = self._updating
        self._updating = True
        try:
            yield
        finally:
            self._updating = before

    # the dims sliders

    def _rebuild_sliders(self, event: Any = None) -> None:
        """One slider with a play button per dimension that is not
        displayed and has more than one step, as napari's sliders."""
        dims = self.viewer.dims
        nsteps = dims.nsteps
        spec = [
            (axis, int(nsteps[axis]), str(dims.axis_labels[axis]))
            for axis in range(dims.ndim)
            if axis not in dims.displayed and int(nsteps[axis]) > 1
        ]
        if spec == self._slider_spec:
            self._update_sliders()  # the same sliders, maybe new values
            return
        self._slider_spec = spec
        rows: list[widgets.Widget] = []
        built: list[widgets.Widget] = []
        sliders: dict[int, widgets.IntSlider] = {}
        for axis, steps, _label in spec:
            slider = widgets.IntSlider(
                value=int(dims.current_step[axis]),
                min=0,
                max=steps - 1,
                description=str(dims.axis_labels[axis]),
                continuous_update=True,
                layout=widgets.Layout(width='100%'),
            )
            play = widgets.Play(
                value=slider.value,
                min=0,
                max=steps - 1,
                interval=100,
                show_repeat=False,
                layout=widgets.Layout(width='auto', min_width='120px'),
            )
            link = widgets.jslink((play, 'value'), (slider, 'value'))
            slider.observe(
                self._owned(partial(self._on_slider, axis)), names='value'
            )
            row = widgets.HBox([play, slider])
            rows.append(row)
            built += [slider, play, link, row]
            sliders[axis] = slider
        on_main_shell(*built)
        old = self._slider_widgets
        self._slider_widgets = built
        self._sliders_by_axis = sliders
        self._sliders.children = rows
        _close(old)

    def _on_slider(self, axis: int, change: dict[str, Any]) -> None:
        if not self._updating:
            self.viewer.dims.set_current_step(axis, change['new'])

    def _update_sliders(self, event: Any = None) -> None:
        step = self.viewer.dims.current_step
        with self._quiet():
            for axis, slider in self._sliders_by_axis.items():
                if axis < len(step) and slider.value != step[axis]:
                    slider.value = int(step[axis])

    # the layer list

    def _rebuild_layers(self, event: Any = None) -> None:
        """A row per layer, top layer first as in napari: a visibility box
        and the name, which selects the layer when clicked.  The same
        layers in the same order keep their rows."""
        if [id(layer) for layer in reversed(self.viewer.layers)] == list(
            self._name_buttons
        ):
            self._update_selection()
            return
        for connections in self._layer_connections.values():
            for emitter, callback in connections:
                emitter.disconnect(callback)
        self._layer_connections = {}
        rows: list[widgets.Widget] = []
        built: list[widgets.Widget] = []
        boxes: dict[int, widgets.Checkbox] = {}
        buttons: dict[int, widgets.Button] = {}
        for layer in reversed(self.viewer.layers):
            key = id(layer)
            ref = weakref.ref(layer)
            box = widgets.Checkbox(
                value=bool(layer.visible),
                indent=False,
                tooltip='Visible',
                layout=widgets.Layout(width='28px'),
            )
            button = widgets.Button(
                description=layer.name,
                tooltip=f'{type(layer).__name__} layer; click to select it',
                layout=widgets.Layout(width='auto', flex='1 1 auto'),
            )
            box.observe(
                self._owned(partial(self._on_visible_box, ref)), names='value'
            )
            button.on_click(self._owned(partial(self._on_name_button, ref)))
            on_visible = partial(self._on_layer_visible, key, ref)
            on_name = partial(self._on_layer_name, key, ref)
            layer.events.visible.connect(on_visible)
            layer.events.name.connect(on_name)
            self._layer_connections[key] = [
                (layer.events.visible, on_visible),
                (layer.events.name, on_name),
            ]
            row = widgets.HBox([box, button])
            rows.append(row)
            built += [box, button, row]
            boxes[key] = box
            buttons[key] = button
        on_main_shell(*built)
        old = self._row_widgets
        self._row_widgets = built
        self._visible_boxes = boxes
        self._name_buttons = buttons
        self._layer_rows.children = rows
        _close(old)
        self._update_selection()

    def _on_visible_box(
        self, ref: weakref.ref[Layer], change: dict[str, Any]
    ) -> None:
        layer = ref()
        if layer is not None and not self._updating:
            layer.visible = change['new']

    def _on_name_button(
        self, ref: weakref.ref[Layer], button: widgets.Button
    ) -> None:
        layer = ref()
        if layer is not None:
            self.viewer.layers.selection.active = layer

    def _on_layer_visible(
        self, key: int, ref: weakref.ref[Layer], event: Any = None
    ) -> None:
        layer = ref()
        box = self._visible_boxes.get(key)
        if layer is not None and box is not None:
            with self._quiet():
                box.value = bool(layer.visible)

    def _on_layer_name(
        self, key: int, ref: weakref.ref[Layer], event: Any = None
    ) -> None:
        layer = ref()
        button = self._name_buttons.get(key)
        if layer is not None and button is not None:
            button.description = layer.name

    def _update_selection(self, event: Any = None) -> None:
        selected = {id(layer) for layer in self.viewer.layers.selection}
        for key, button in self._name_buttons.items():
            button.button_style = 'info' if key in selected else ''

    # what a Viewer uses from its window (napari_lite.backends.Window)

    def show(self, *, block: bool = False) -> None:
        """Display the window in the output of the running cell (again, if
        it was displayed before: the views stay in step).  ``block`` is
        accepted for compatibility; a notebook does not block."""
        from IPython.display import display

        if self._closed:
            raise RuntimeError('this window was closed')
        self.activate()
        display(self.widget)

    def activate(self) -> None:
        """Make this the window ``current_viewer()`` returns."""
        if self._closed:
            return
        self._forget()
        JupyterWindow._instances.append(weakref.ref(self))

    def close(self) -> None:
        """Close the widgets and release the renderer."""
        if self._closed:
            return
        self._closed = True
        for emitter, callback in self._connections:
            emitter.disconnect(callback)
        for connections in self._layer_connections.values():
            for emitter, callback in connections:
                emitter.disconnect(callback)
        self._connections = []
        self._layer_connections = {}
        self.viewer.cursor.events.position.disconnect(self._on_cursor_position)
        self.viewer.cursor.events.position.connect(
            self.viewer.update_status_from_cursor
        )
        for wrapper, _inner in self._docks.values():
            wrapper.close()
        self._docks = {}
        _close(self._slider_widgets + self._row_widgets + self._own_widgets)
        self.backend.close()
        self._forget()

    # the two actions whose napari version opens a Qt dialog

    def show_shortcuts(self) -> None:
        """Ctrl+Alt+/: the key bindings as a table under the layer list;
        pressed again, it goes away."""
        if self._toggle_dock('Key bindings'):
            return
        from napari_lite.backends._actions import shortcuts_html

        self.add_dock_widget(
            widgets.HTML(shortcuts_html()), name='Key bindings', area='left'
        )

    def open_files(self) -> list[Layer]:
        """Ctrl+O: an upload box under the layer list; every file
        uploaded is opened with the built-in reader, one layer per file,
        as a file dropped on the canvas would be.  Pressed again, the
        box goes away.  Returns nothing: the layers come with the
        uploads."""
        if self._toggle_dock('Open files'):
            return []
        upload = widgets.FileUpload(
            accept='.png,.jpg,.jpeg,.bmp,.gif,.webp,.tif,.tiff,.npy,.npz',
            multiple=True,
            description='Upload',
        )
        upload.observe(self._owned(self._on_upload), names='value')
        self.add_dock_widget(upload, name='Open files', area='left')
        return []

    def _toggle_dock(self, name: str) -> bool:
        """Remove the dock called ``name`` if it is there."""
        if name in self._docks:
            self.remove_dock_widget(name)
            return True
        return False

    def _on_upload(self, change: dict[str, Any]) -> None:
        """Uploaded files, written to a temporary folder and opened; the
        box is emptied so that the same file can be chosen again."""
        from napari_lite.backends._actions import open_paths

        uploads = change['new']
        if not uploads:
            return
        folder = Path(tempfile.mkdtemp(prefix='napari-lite-upload-'))
        paths = []
        for item in uploads:
            path = folder / Path(item['name']).name
            path.write_bytes(bytes(item['content']))
            paths.append(str(path))
        open_paths(self.viewer, paths)
        change['owner'].value = ()

    def resize(self, width: int, height: int) -> None:
        """Size the canvas, in CSS pixels; the browser then reports the
        new size to the renderer."""
        if hasattr(self._canvas, 'css_width'):  # jupyter_rfb's widget
            self._canvas.css_width = f'{int(width)}px'
            self._canvas.css_height = f'{int(height)}px'
        else:
            self._canvas.layout.width = f'{int(width)}px'
            self._canvas.layout.height = f'{int(height)}px'

    def set_geometry(
        self, left: int, top: int, width: int, height: int
    ) -> None:
        """Size the canvas; where it sits is the notebook's to decide."""
        self.resize(width, height)

    def geometry(self) -> tuple[int, int, int, int]:
        """(0, 0, width, height) of the canvas, in CSS pixels."""

        def pixels(css: str, fallback: int) -> int:
            return int(float(css[:-2])) if css.endswith('px') else fallback

        width, height = self.viewer.canvas.size[::-1]
        return (
            0,
            0,
            pixels(getattr(self._canvas, 'css_width', ''), width),
            pixels(getattr(self._canvas, 'css_height', ''), height),
        )

    def screenshot(
        self,
        path: str | None = None,
        size: tuple[int, int] | None = None,
        scale: float | None = None,
        flash: bool = False,
        canvas_only: bool = False,
    ) -> np.ndarray:
        """The canvas as an RGBA array (and saved to ``path``).  The rest
        of the window is the browser's to draw, so ``canvas_only=False``
        gives the canvas too; ``flash`` is accepted and ignored."""
        img = self.backend.screenshot(
            size=size, scale=1.0 if scale is None else scale
        )
        if path is not None:
            imsave(str(path), img)
        return img

    def export_figure(
        self, path: str | None = None, *, scale: float = 1, flash: bool = False
    ) -> np.ndarray:
        """Screenshot tightly fitted around the data, one pixel per data
        pixel (times ``scale``)."""
        img = self.backend.screenshot(scale=scale, fit_to_data_extent=True)
        if path is not None:
            imsave(str(path), img)
        return img

    def clipboard(
        self, flash: bool = False, canvas_only: bool = False
    ) -> None:
        """Not available: the kernel cannot reach the browser's clipboard;
        ``screenshot()`` gives the picture."""
        raise NotImplementedError(
            'a notebook window has no clipboard the kernel can write to; '
            'use viewer.screenshot() or nbscreenshot(viewer)'
        )

    def add_dock_widget(
        self,
        widget: Any,
        *,
        name: str = '',
        area: str | None = None,
        allowed_areas: Sequence[str] | None = None,
        add_vertical_stretch: bool = True,
        tabify: bool = False,
        menu: Any = None,
    ) -> widgets.Box:
        """Put an ipywidget (or a magicgui widget made for ipywidgets) next
        to the canvas, under a title.  Its messages, and so its callbacks,
        are handled on the kernel's main shell, the viewer's thread, where
        they may change the viewer (JupyterLab would otherwise run them on a
        thread of their own).

        Parameters
        ----------
        widget : ipywidgets.Widget or magicgui Widget
            The widget; a magicgui widget's ``native`` widget is used.
        name : str
            The title; a generic name is made up if empty.
        area : {'left', 'right', 'bottom'}, optional
            Where: under the layer list, right of the canvas (default), or
            under the canvas ('top' counts as 'bottom').
        allowed_areas, add_vertical_stretch, tabify, menu
            Accepted for compatibility with the Qt window; ignored.

        Returns
        -------
        ipywidgets.VBox
            The title and the widget.
        """
        inner = getattr(widget, 'native', widget)
        if not isinstance(inner, widgets.Widget):
            raise TypeError(
                'a notebook window docks ipywidgets (or magicgui widgets '
                f'made with the ipywidgets backend), not {type(widget)!r}'
            )
        if not name:
            name = f'Dock widget {self._unnamed_dock_count}'
            self._unnamed_dock_count += 1
        area = area or 'right'
        column = {
            'left': self._left_docks,
            'right': self._right_docks,
            'bottom': self._bottom_docks,
            'top': self._bottom_docks,
        }.get(area)
        if column is None:
            raise ValueError(
                f"area must be 'left', 'right' or 'bottom', not {area!r}"
            )
        if name in self._docks:
            self.remove_dock_widget(name)
        wrapper = widgets.VBox(
            [widgets.HTML(f'<b>{html.escape(name)}</b>'), inner]
        )
        # its callbacks run on the viewer's thread, where the viewer may be
        # changed (not on a kernel subshell's thread)
        on_main_shell(wrapper)
        column.children = (*column.children, wrapper)
        self._docks[name] = (wrapper, widget)
        if hasattr(widget, 'reset_choices'):
            # keep magicgui layer dropdowns in step with the layer list
            layers_events = self.viewer.layers.events
            for emitter in (
                layers_events.inserted,
                layers_events.removed,
                layers_events.reordered,
                layers_events.renamed,
            ):
                self._connect(emitter, widget.reset_choices)
        return wrapper

    def remove_dock_widget(self, widget: Any, menu: Any = None) -> None:
        """Remove a widget added with ``add_dock_widget``: the box it
        returned, the widget itself, its name, or ``'all'``."""
        if isinstance(widget, str) and widget == 'all':
            for name in list(self._docks):
                self.remove_dock_widget(name)
            return
        for name, (wrapper, inner) in self._docks.items():
            if widget is wrapper or widget is inner or widget == name:
                break
        else:
            raise LookupError(
                f'Could not find a dock widget containing {widget!r}'
            )
        del self._docks[name]
        for column in (
            self._left_docks,
            self._right_docks,
            self._bottom_docks,
        ):
            column.children = tuple(
                c for c in column.children if c is not wrapper
            )
        if hasattr(inner, 'reset_choices'):
            kept = []
            for emitter, callback in self._connections:
                if callback == inner.reset_choices:
                    emitter.disconnect(callback)
                else:
                    kept.append((emitter, callback))
            self._connections = kept
        wrapper.children[0].close()  # the title
        wrapper.close()

    @property
    def dock_widgets(self) -> dict[str, Any]:
        """Name -> widget of each dock."""
        return {name: inner for name, (_wrapper, inner) in self._docks.items()}

    def register_task_status(
        self,
        provider: str,
        task_status: Status,
        description: str = '',
        cancel_callback: Callable[[], None] | None = None,
    ) -> uuid.UUID:
        """Register a long running task (used by thread workers)."""
        return self._task_status_manager.register_task_status(
            provider, task_status, description, cancel_callback
        )

    def update_task_status(
        self,
        task_status_id: uuid.UUID,
        status: Status,
        description: str = '',
    ) -> bool:
        return self._task_status_manager.update_task_status(
            task_status_id, status, description
        )

    # napari's names for the two, for code written for its window
    _register_task_status = register_task_status
    _update_task_status = update_task_status


def _close(items: Sequence[widgets.Widget]) -> None:
    for item in items:
        item.close()
