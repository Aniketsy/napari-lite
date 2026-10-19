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

``napari_lite.Viewer`` wraps one in a window (issue 13).  The drawing
itself is a renderer's, behind the ``CanvasBackend`` contract
(``napari_lite.backends``): vispy by default, the one ``renderer`` names
otherwise; the headless viewer uses the same renderer without any widget
(docs/backends.md).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Any, ClassVar, Literal
from weakref import WeakSet

import numpy as np
from qtpy.QtCore import QCoreApplication, QEvent, Qt
from qtpy.QtGui import QGuiApplication, QImage
from qtpy.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget
from superqt import QElidingLabel
from superqt.utils import qthrottled

import napari_lite.qt._viewer_actions  # noqa: F401  (re-registers two actions)
from napari_lite._qt.utils import use_tabular_numerals
from napari_lite._qt.widgets.qt_dims import QtDims
from napari_lite.backends import CanvasBackend, resolve_renderer
from napari_lite.qt._hint import HintRow, QtCanvasHint
from napari_lite.utils.action_manager import bind_shortcuts_from_settings
from napari_lite.utils.io import imsave

if TYPE_CHECKING:
    from pathlib import Path

    from qtpy.QtCore import QObject
    from qtpy.QtGui import (
        QCloseEvent,
        QDragEnterEvent,
        QDropEvent,
        QKeyEvent,
    )

    from napari_lite._qt.containers import QtLayerList
    from napari_lite._qt.layer_controls import QtLayerControlsContainer
    from napari_lite._qt.widgets.qt_viewer_buttons import (
        QtLayerButtons,
        QtViewerButtons,
    )
    from napari_lite._qt.widgets.qt_viewer_dock_widget import (
        QtViewerDockWidget,
    )
    from napari_lite._vispy import VispyCanvas
    from napari_lite._vispy.layers.base import VispyBaseLayer
    from napari_lite.components import ViewerModel
    from napari_lite.layers import Layer
    from napari_lite.utils.events import Event
    from napari_lite.utils.key_bindings import KeymapHandler

__all__ = ['QtCanvas', 'QtStatusLine']


def _array_to_qimage(img: np.ndarray) -> QImage:
    """An RGBA uint8 array as a QImage that owns its pixels."""
    rgba: Any = np.ascontiguousarray(img, dtype=np.uint8)
    height, width = rgba.shape[:2]
    return QImage(
        rgba.data, width, height, width * 4, QImage.Format.Format_RGBA8888
    ).copy()


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
    hint : str
        Text shown in the middle of the canvas while there are no layers
        (default '': nothing; the viewer window passes how to load data).
    renderer : str or callable
        The renderer's name or class (``napari_lite.backends``); by
        default the one ``NAPARI_LITE_RENDERER`` names, else vispy.

    Attributes
    ----------
    backend : CanvasBackend
        The renderer, with the layers kept in step.
    canvas : VispyCanvas or None
        napari's vispy canvas when vispy draws (``canvas.native`` is the
        Qt widget); None with another renderer.
    dims : QtDims
        The dimension sliders.
    status : QtStatusLine or None
        The status line.
    controls, layers, layerButtons, viewerButtons : QWidget
        napari's layer controls, layer list and the two button rows,
        built on first access; ``dockLayerControls`` and ``dockLayerList``
        wrap them in dock widgets the way the viewer window shows them.
    """

    _instances: ClassVar[WeakSet[QtCanvas]] = WeakSet()

    def __init__(
        self,
        viewer: ViewerModel,
        parent: QWidget | None = None,
        *,
        show_status: bool = True,
        hint: str = '',
        renderer: str | Callable[..., CanvasBackend] = 'default',
    ) -> None:
        super().__init__(parent)
        self._instances.add(self)
        self._closed = False
        # with a stylesheet active, fonts (e.g. tabular numerals) only
        # propagate from parent to child widgets with this attribute
        QCoreApplication.setAttribute(
            Qt.ApplicationAttribute.AA_UseStyleSheetPropagationInWidgetStyles,
            True,
        )
        self.viewer = viewer
        self._controls: QtLayerControlsContainer | None = None
        self._layers: QtLayerList | None = None
        self._layersButtons: QtLayerButtons | None = None
        self._viewerButtons: QtViewerButtons | None = None
        self._dockLayerList: QtViewerDockWidget | None = None
        self._dockLayerControls: QtViewerDockWidget | None = None

        self.backend: CanvasBackend = resolve_renderer(renderer)(
            viewer, gui='qt', parent=self
        )
        self.canvas: VispyCanvas | None = getattr(self.backend, 'canvas', None)
        self.dims: QtDims = QtDims(viewer.dims)
        self.status: QtStatusLine | None = (
            QtStatusLine(viewer) if show_status else None
        )
        self._hint = QtCanvasHint(self)
        self._hint.set_content(hint)
        self._hint.link_activated.connect(self._hint_link)
        self._hint.apply_theme(viewer.theme)
        viewer.events.theme.connect(self._on_theme_change)
        # the hint lies over the canvas widget, outside the layout (a
        # label in the layout would size the canvas by its text):
        # eventFilter keeps it at the canvas widget's geometry
        self.backend.native.installEventFilter(self)
        self._hint.raise_()
        self.setAcceptDrops(True)  # files: dropEvent

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(0)
        layout.addWidget(self.backend.native, stretch=1)
        layout.addWidget(self.dims)
        if self.status is not None:
            layout.addWidget(self.status)
        self.setLayout(layout)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        viewer.layers.events.inserted.connect(self._update_hint)
        viewer.layers.events.removed.connect(self._update_hint)
        # The model computes the status text (value under the cursor,
        # coordinates, help) on every cursor move, and every slice step
        # moves the cursor.  napari's window takes that off the model and
        # computes it in a thread, which also throttles it.  Here it stays
        # on the main thread but runs at most every 50 ms, the last
        # position always shown: a slice step or a mouse move no longer
        # pays for the status and the relayout of its labels each time.
        viewer.cursor.events.position.disconnect(
            viewer.update_status_from_cursor
        )
        self._status_update = qthrottled(
            viewer.update_status_from_cursor, timeout=50, leading=True
        )
        viewer.cursor.events.position.connect(self._on_cursor_position)

        # shortcuts from the settings, bound to the registered actions
        bind_shortcuts_from_settings()

        self._update_hint()

    # layers

    @property
    def layer_to_visual(self) -> dict[Layer, VispyBaseLayer]:
        """Mapping of napari layer to its vispy visual (the vispy
        renderer's; another renderer has no such thing)."""
        return self.backend.layer_to_visual  # type: ignore[attr-defined]

    @property
    def _key_map_handler(self) -> KeymapHandler:
        return self.backend.key_map_handler  # type: ignore[attr-defined]

    # the layer panel: napari's layer list, layer controls, button rows

    @property
    def controls(self) -> QtLayerControlsContainer:
        """The controls of the selected layer."""
        if self._controls is None:
            from napari_lite._qt.layer_controls import (
                QtLayerControlsContainer,
            )

            self._controls = QtLayerControlsContainer(self.viewer)
        return self._controls

    @property
    def layers(self) -> QtLayerList:
        """The layer list."""
        if self._layers is None:
            from napari_lite._qt.containers import QtLayerList

            self._layers = QtLayerList(self.viewer.layers)
        return self._layers

    @property
    def layerButtons(self) -> QtLayerButtons:
        """New points, shapes and labels layers; delete the selected."""
        if self._layersButtons is None:
            from napari_lite._qt.widgets.qt_viewer_buttons import (
                QtLayerButtons,
            )

            self._layersButtons = QtLayerButtons(self.viewer)
        return self._layersButtons

    @property
    def viewerButtons(self) -> QtViewerButtons:
        """2D/3D, roll, transpose, grid and home (napari's console button
        too, which the viewer window hides)."""
        if self._viewerButtons is None:
            from napari_lite._qt.widgets.qt_viewer_buttons import (
                QtViewerButtons,
            )

            self._viewerButtons = QtViewerButtons(self.viewer)
        return self._viewerButtons

    @property
    def dockLayerList(self) -> QtViewerDockWidget:
        """Layer buttons, layer list and viewer buttons in a dock widget."""
        if self._dockLayerList is None:
            from napari_lite._qt.widgets.qt_viewer_dock_widget import (
                QtViewerDockWidget,
            )

            panel = QWidget()
            panel.setObjectName('layerList')
            layout = QVBoxLayout()
            layout.addWidget(self.layerButtons)
            layout.addWidget(self.layers)
            layout.addWidget(self.viewerButtons)
            layout.setContentsMargins(8, 4, 8, 6)
            panel.setLayout(layout)
            self._dockLayerList = QtViewerDockWidget(
                self,
                panel,
                name='layer list',
                area='left',
                allowed_areas=['left', 'right'],
                object_name='layer list',
                close_btn=False,
            )
        return self._dockLayerList

    @property
    def dockLayerControls(self) -> QtViewerDockWidget:
        """The layer controls in a dock widget."""
        if self._dockLayerControls is None:
            from napari_lite._qt.widgets.qt_viewer_dock_widget import (
                QtViewerDockWidget,
            )

            self._dockLayerControls = QtViewerDockWidget(
                self,
                self.controls,
                name='layer controls',
                area='left',
                allowed_areas=['left', 'right'],
                object_name='layer controls',
                close_btn=False,
            )
        return self._dockLayerControls

    # the hint in the empty canvas

    @property
    def hint(self) -> str:
        """What the canvas shows while there are no layers, as plain text
        (the headline, the line under it and the rows of ``set_hint``);
        '' shows nothing."""
        return self._hint.text()

    @hint.setter
    def hint(self, text: str) -> None:
        self._hint.set_content(text)
        self._update_hint()

    def set_hint(
        self,
        title: str,
        rows: Sequence[HintRow] = (),
        *,
        lead: str = '',
    ) -> None:
        """The empty canvas as the viewer window shows it: a headline, a
        line under it, rows of label and content (commands, links); see
        ``HintRow``."""
        self._hint.set_content(title, tuple(rows), lead=lead)
        self._update_hint()

    def _update_hint(self) -> None:
        self._hint.setVisible(
            bool(self._hint.text()) and len(self.viewer.layers) == 0
        )

    def _on_theme_change(self) -> None:
        self._hint.apply_theme(self.viewer.theme)

    def eventFilter(self, obj: QObject | None, event: QEvent | None) -> bool:
        """Move the hint with the canvas widget."""
        if (
            obj == self.backend.native
            and event is not None
            and event.type() in (QEvent.Type.Resize, QEvent.Type.Move)
        ):
            self._hint.setGeometry(self.backend.native.geometry())
        return super().eventFilter(obj, event)

    def _hint_link(self, href: str) -> None:
        """Links in the empty-canvas hint: ``open-files`` (a file dialog)
        and ``sample:<name>`` (a built-in sample)."""
        from napari_lite.qt._viewer_actions import open_files, open_sample

        if href == 'open-files':
            open_files(self.viewer)
        elif href.startswith('sample:'):
            open_sample(self.viewer, href.partition(':')[2])

    # files dropped on the canvas

    def dragEnterEvent(self, event: QDragEnterEvent | None) -> None:
        """Files can be dropped on the canvas."""
        if event is None:
            return
        mime = event.mimeData()
        if mime is not None and mime.hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent | None) -> None:
        """Dropped files open with the built-in reader, one layer each, or
        as one stack with Shift held; a failure goes to the status bar."""
        if event is None:
            return
        mime = event.mimeData()
        if mime is None:
            return
        paths = [url.toLocalFile() for url in mime.urls() if url.isLocalFile()]
        if not paths:
            return
        # QDropEvent.modifiers() is Qt 6; Qt 5 has keyboardModifiers()
        modifiers = (
            event.modifiers()
            if hasattr(event, 'modifiers')
            else event.keyboardModifiers()
        )
        stack = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
        from napari_lite.qt._viewer_actions import open_paths

        open_paths(self.viewer, paths, stack=stack)
        event.acceptProposedAction()

    # mouse and keyboard

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
        self.backend.key_event(event)
        event.accept()

    def keyReleaseEvent(self, event: QKeyEvent | None) -> None:
        if event is None:
            return
        self.backend.key_event(event, release=True)
        event.accept()

    # screenshots

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
        img = self.backend.screenshot(
            size=size,
            scale=scale,
            fit_to_data_extent=fit_to_data_extent,
            device_pixel_ratio=self.devicePixelRatio(),
        )
        if flash:
            from napari_lite._qt.utils import add_flash_animation

            add_flash_animation(self)
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
        """The screenshot as a QImage, for the clipboard and the window."""
        return _array_to_qimage(
            self.screenshot(
                flash=flash,
                size=size,
                scale=scale,
                fit_to_data_extent=fit_to_data_extent,
            )
        )

    def clipboard(self, flash: bool = False) -> None:
        """Copy a screenshot of the canvas to the clipboard."""
        cb = QGuiApplication.clipboard()
        if cb is not None:
            cb.setImage(self._screenshot(flash))

    # lifecycle

    def _on_cursor_position(self) -> None:
        self._status_update()

    def _restore_status_updates(self) -> None:
        """Give the status back to the model: computed on every cursor
        move, as without a canvas."""
        viewer = self.viewer
        viewer.cursor.events.position.disconnect(self._on_cursor_position)
        if not any(
            other is not self and other.viewer is viewer
            for other in self._instances
        ):
            viewer.cursor.events.position.connect(
                viewer.update_status_from_cursor
            )

    def closeEvent(self, event: QCloseEvent | None) -> None:
        """Stop the animation thread and release the vispy canvas (once:
        a widget closed by hand is closed again when it is deleted)."""
        if not self._closed:
            self._closed = True
            self.dims.stop()
            self.backend.close()
            self._restore_status_updates()
        if event is not None:
            event.accept()
