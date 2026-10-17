# napari-lite: own code
"""The viewer window: a ``QMainWindow`` around a ``QtCanvas``.

napari's main window carries menus, a status bar, the layer list and
layer-control docks, the console, a welcome screen and the command palette.
napari-lite's window has the canvas, the dims sliders, a status bar and, in
napari's left column, the layer controls and the layer list with their
button rows (all built by ``QtCanvas`` on first access), plus
``add_dock_widget`` for users' own widgets.  No menus, console, welcome
screen or command palette.

``Window`` keeps the attribute names code written for napari relies on:
``viewer.window._qt_window`` (the QMainWindow), ``viewer.window.qt_viewer``
and ``viewer.window._qt_viewer`` (here the ``QtCanvas``).
"""

from __future__ import annotations

import contextlib
import uuid
from typing import TYPE_CHECKING, Any, ClassVar
from weakref import WeakValueDictionary

from qtpy.QtCore import QEvent, QEventLoop, Qt
from qtpy.QtWidgets import (
    QApplication,
    QDockWidget,
    QMainWindow,
    QStatusBar,
    QToolTip,
    QWidget,
)

from napari_lite._qt.qt_event_loop import get_qapp, register_theme_icons
from napari_lite._qt.qt_resources import get_stylesheet
from napari_lite._qt.utils import QImg2array
from napari_lite._qt.widgets.qt_viewer_dock_widget import (
    QtViewerDockWidget,
)
from napari_lite.qt.canvas import QtCanvas, QtStatusLine
from napari_lite.settings import get_settings
from napari_lite.utils.interactions import Shortcut
from napari_lite.utils.io import imsave
from napari_lite.utils.misc import in_jupyter
from napari_lite.utils.task_status import Status, TaskStatusManager
from napari_lite.utils.theme import get_system_theme

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from qtpy.QtGui import QCloseEvent, QImage, QKeyEvent

    from napari_lite.components import ViewerModel
    from napari_lite.utils.events import Event

__all__ = ['Window']


def _empty_canvas_hint() -> str:
    """What the canvas says while there are no layers: how to get data in.

    napari shows a welcome screen here; napari-lite has no file dialog and
    no readers, so the hint names the command line and ``add_image``.
    """
    lines = [
        'No layers',
        '',
        'Open files from the command line:   napari-lite image.png stack.npy',
        'Add layers from Python:   viewer.add_image(array)',
    ]
    keys = get_settings().shortcuts.shortcuts.get('napari:show_shortcuts')
    if keys:
        lines.append(f'List the key bindings:   {Shortcut(keys[0])}')
    return '\n'.join(lines)


class _NoThread:
    """Stand-in for napari's status thread (napari-lite computes the status
    on the main thread); ``_qt/utils.py`` asks it whether it is running."""

    def isRunning(self) -> bool:
        return False

    def close_terminate(self) -> None:
        return None

    def wait(self) -> None:
        return None


class ViewerStatusBar(QStatusBar):
    """The window's status bar: napari-lite's status line (status text,
    cursor coordinates, help) in a ``QStatusBar``, with the attribute and
    method names of napari's ``ViewerStatusBar``."""

    def __init__(self, viewer: ViewerModel, parent: QWidget | None = None):
        super().__init__(parent)
        self._line = QtStatusLine(viewer, self)
        self.addWidget(self._line, 1)
        self.setSizeGripEnabled(False)

    @property
    def _status(self):
        return self._line._status

    @property
    def _coordinates(self):
        return self._line._coordinates

    @property
    def _help(self):
        return self._line._help

    def setHelpText(self, text: str) -> None:
        self._line._help.setText(text)

    def setStatusText(
        self,
        text: str = '',
        layer_base: str = '',
        source_type: str | None = None,
        plugin: str = '',
        coordinates: str = '',
    ) -> None:
        self._line._status.setText(text or layer_base)
        self._line._coordinates.setText(coordinates)


class _QtMainWindow(QMainWindow):
    """The QMainWindow; ``_instances`` is ordered by last activation so
    ``current_viewer()`` returns the viewer the user worked with last."""

    _instances: ClassVar[list[_QtMainWindow]] = []

    def __init__(
        self,
        viewer: ViewerModel,
        window: Window,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._ev: QEventLoop | None = None
        self._window = window
        # the status line is the window's status bar, not part of the canvas
        self._qt_viewer = QtCanvas(
            viewer, show_status=False, hint=_empty_canvas_hint()
        )
        self.status_thread = _NoThread()
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setCentralWidget(self._qt_viewer)
        # napari's left column: the layer controls above the layer list
        for dock in (
            self._qt_viewer.dockLayerControls,
            self._qt_viewer.dockLayerList,
        ):
            self.addDockWidget(dock.qt_area, dock)
        self._qt_viewer.viewerButtons.consoleButton.hide()  # no console
        self.setStatusBar(ViewerStatusBar(viewer, self))
        self.setWindowTitle(viewer.title)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        _QtMainWindow._instances.append(self)

    @classmethod
    def current(cls) -> _QtMainWindow | None:
        return cls._instances[-1] if cls._instances else None

    @classmethod
    def current_viewer(cls) -> ViewerModel | None:
        window = cls.current()
        return window._qt_viewer.viewer if window else None

    def event(self, e: QEvent) -> bool:
        if e.type() == QEvent.Type.WindowActivate and self in self._instances:
            # most recently active window last
            self._instances.remove(self)
            self._instances.append(self)
        if (
            e.type() == QEvent.Type.ToolTip
            and self._qt_viewer.viewer.tooltip.visible
        ):
            pnt = e.globalPosition().toPoint()
            QToolTip.showText(pnt, self._qt_viewer.viewer.tooltip.text, self)
            return True
        return super().event(e)

    def show(self, block: bool = False) -> None:
        super().show()
        self._qt_viewer.setFocus()
        if block:
            self._ev = QEventLoop()
            self._ev.exec()

    def keyPressEvent(self, event: QKeyEvent | None) -> None:
        if event is not None:
            self._qt_viewer.keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent | None) -> None:
        if event is not None:
            self._qt_viewer.keyReleaseEvent(event)

    def closeEvent(self, event: QCloseEvent | None) -> None:
        if self._ev is not None and self._ev.isRunning():
            self._ev.quit()
        self._qt_viewer.dims.stop()
        with contextlib.suppress(ValueError):
            self._instances.remove(self)
        if event is not None:
            event.accept()


class Window:
    """The window of a ``Viewer``.

    Parameters
    ----------
    viewer : ViewerModel
        The viewer shown in the window.
    show : bool
        Show the window right away (default True).
    """

    def __init__(self, viewer: ViewerModel, *, show: bool = True) -> None:
        get_qapp()  # create the QApplication if there is none
        self._task_status_manager = TaskStatusManager()
        self._wrapped_dock_widgets: WeakValueDictionary[str, QDockWidget] = (
            WeakValueDictionary()
        )
        self._unnamed_dockwidget_count = 1
        self._qt_window = _QtMainWindow(viewer, self)

        viewer.events.title.connect(self._title_changed)
        viewer.events.theme.connect(self._update_theme)
        self._update_theme()

        if show:
            self.show()

    # ------------------------------------------------------------------
    # accessors kept from napari's Window
    # ------------------------------------------------------------------

    @property
    def qt_viewer(self) -> QtCanvas:
        """The ``QtCanvas`` (napari: the ``QtViewer``)."""
        return self._qt_window._qt_viewer

    @property
    def _qt_viewer(self) -> QtCanvas:
        return self._qt_window._qt_viewer

    @property
    def viewer(self) -> ViewerModel:
        return self._qt_window._qt_viewer.viewer

    @property
    def _status_bar(self) -> ViewerStatusBar:
        return self._qt_window.statusBar()

    def _register_task_status(
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

    def _update_task_status(
        self,
        task_status_id: uuid.UUID,
        status: Status,
        description: str = '',
    ) -> bool:
        return self._task_status_manager.update_task_status(
            task_status_id, status, description
        )

    # ------------------------------------------------------------------
    # dock widgets
    # ------------------------------------------------------------------

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
    ) -> QtViewerDockWidget:
        """Dock ``widget`` (a QWidget or a magicgui widget) next to the canvas.

        Parameters
        ----------
        widget : QWidget or magicgui Widget
            The widget to dock; a magicgui widget's ``native`` widget is used.
        name : str
            Title of the dock; a generic name is made up if empty.
        area : {'left', 'right', 'top', 'bottom'}, optional
            Where to dock; default: the ``application.plugin_widget_positions``
            setting for ``name``, else 'right'.
        allowed_areas : sequence of str, optional
            Areas the dock may be moved to; all by default.
        add_vertical_stretch : bool
            Push a short widget to the top of a left or right dock.
        tabify : bool
            Tab the new dock with the others in the same area.
        menu : object
            Accepted for compatibility with napari; ignored (no menus).

        Returns
        -------
        QtViewerDockWidget
            napari's dock widget: its title bar floats and hides it, keys
            pressed in it reach the viewer.
        """
        if not name:
            with contextlib.suppress(AttributeError):
                name = widget.objectName()
            name = name or f'Dock widget {self._unnamed_dockwidget_count}'
            self._unnamed_dockwidget_count += 1
        if area is None:
            positions = get_settings().application.plugin_widget_positions
            area = positions.get(name, 'right')
        dock = QtViewerDockWidget(
            self._qt_viewer,
            widget,
            name=name,
            area=area,
            allowed_areas=allowed_areas,
            add_vertical_stretch=add_vertical_stretch,
        )
        self._add_viewer_dock_widget(dock, tabify=tabify)
        if hasattr(widget, 'reset_choices'):
            # keep magicgui layer dropdowns in sync with the layer list
            layers_events = self.viewer.layers.events
            layers_events.inserted.connect(widget.reset_choices)
            layers_events.removed.connect(widget.reset_choices)
            layers_events.reordered.connect(widget.reset_choices)
            layers_events.renamed.connect(widget.reset_choices)
        self._wrapped_dock_widgets[dock.name] = dock
        return dock

    def _add_viewer_dock_widget(
        self, dock: QtViewerDockWidget, tabify: bool = False
    ) -> None:
        """Add ``dock`` to the main window with napari's placement rules."""
        others = [
            dw
            for dw in self._qt_window.findChildren(QDockWidget)
            if self._qt_window.dockWidgetArea(dw) == dock.qt_area
        ]
        self._qt_window.addDockWidget(dock.qt_area, dock)
        if others:
            if tabify:
                self._qt_window.tabifyDockWidget(others[-1], dock)
                dock.show()
                dock.raise_()
            elif dock.area in ('right', 'left'):
                docks = [*others, dock]
                # sizes that push the lower docks up
                sizes = list(range(1, len(docks) * 4, 4))
                self._qt_window.resizeDocks(
                    docks, sizes, Qt.Orientation.Vertical
                )
        dock.setFloating(False)  # napari #3663

    def remove_dock_widget(self, widget: Any, menu: Any = None) -> None:
        """Remove a dock added with ``add_dock_widget``: the dock itself,
        the widget inside it, its name, or ``'all'``."""
        if widget == 'all':
            for dock in list(self._wrapped_dock_widgets.values()):
                self.remove_dock_widget(dock)
            return
        if isinstance(widget, QDockWidget):
            dock = widget
        elif isinstance(widget, str) and widget in self._wrapped_dock_widgets:
            dock = self._wrapped_dock_widgets[widget]
        else:
            inner = getattr(widget, 'native', widget)
            for dock in self._qt_window.findChildren(QDockWidget):
                if dock.widget() is inner:
                    break
            else:
                raise LookupError(
                    f'Could not find a dock widget containing {widget!r}'
                )
        if dock.widget():
            dock.widget().setParent(None)
        self._qt_window.removeDockWidget(dock)
        name = getattr(dock, 'name', dock.objectName())
        self._wrapped_dock_widgets.pop(name, None)
        dock.deleteLater()

    @property
    def dock_widgets(self) -> dict[str, QWidget]:
        """Name -> widget inside each dock."""
        return {
            name: dock.widget()
            for name, dock in self._wrapped_dock_widgets.items()
        }

    # ------------------------------------------------------------------
    # geometry, show, close
    # ------------------------------------------------------------------

    def resize(self, width: int, height: int) -> None:
        self._qt_window.resize(width, height)

    def set_geometry(
        self, left: int, top: int, width: int, height: int
    ) -> None:
        self._qt_window.setGeometry(left, top, width, height)

    def geometry(self) -> tuple[int, int, int, int]:
        geometry = self._qt_window.geometry()
        return geometry.x(), geometry.y(), geometry.width(), geometry.height()

    def show(self, *, block: bool = False) -> None:
        """Show and raise the window; ``block`` runs a nested event loop."""
        try:
            self._qt_window.show(block=block)
        except (AttributeError, RuntimeError) as e:
            raise RuntimeError(
                'This viewer has already been closed and deleted. '
                'Please create a new one.'
            ) from e
        self._qt_viewer.dims._resize_axis_labels()
        # the controls dock takes its minimum height, the layer list the rest
        self._qt_window.resizeDocks(
            [self._qt_viewer.dockLayerControls, self._qt_viewer.dockLayerList],
            [self._qt_viewer.dockLayerControls.minimumHeight(), 10000],
            Qt.Orientation.Vertical,
        )
        app = QApplication.instance()
        if (
            app is not None
            and (app.applicationName() == 'napari-lite' or in_jupyter())
            and self._qt_window.isActiveWindow()
        ):
            self.activate()

    def activate(self) -> None:
        """Make this the active window."""
        self._qt_window.raise_()
        self._qt_window.activateWindow()

    def close(self) -> None:
        """Close the window and release its widgets."""
        if hasattr(self, '_qt_window'):
            self._qt_viewer.close()
            self._qt_window.close()
            del self._qt_window

    # ------------------------------------------------------------------
    # theme and title
    # ------------------------------------------------------------------

    def _update_theme(self, event: Event | None = None) -> None:
        """Apply napari's stylesheet in the viewer's theme, with the
        theme's icons in place."""
        with contextlib.suppress(AttributeError, RuntimeError, ValueError):
            theme_name = self.viewer.theme
            if theme_name == 'system':
                theme_name = get_system_theme()
            register_theme_icons(theme_name)
            self._qt_window.setStyleSheet(get_stylesheet(theme_name))

    def _title_changed(self, event: Event) -> None:
        if hasattr(self, '_qt_window'):
            self._qt_window.setWindowTitle(event.value)

    # ------------------------------------------------------------------
    # screenshots
    # ------------------------------------------------------------------

    def _screenshot(
        self,
        size: tuple[int, int] | None = None,
        scale: float | None = None,
        flash: bool = False,
        canvas_only: bool = False,
        fit_to_data_extent: bool = False,
    ) -> QImage:
        if not canvas_only and (
            fit_to_data_extent or size is not None or scale is not None
        ):
            raise ValueError(
                'scale, size, and fit_to_data_extent can only be set for '
                'canvas_only screenshots.'
            )
        if canvas_only:
            return self._qt_viewer._screenshot(
                flash=flash,
                size=size,
                scale=scale if scale is not None else 1.0,
                fit_to_data_extent=fit_to_data_extent,
            )
        img = self._qt_window.grab().toImage()
        if flash:
            from napari_lite._qt.utils import add_flash_animation

            add_flash_animation(self._qt_window)
        return img

    def screenshot(
        self,
        path: str | None = None,
        size: tuple[int, int] | None = None,
        scale: float | None = None,
        flash: bool = False,
        canvas_only: bool = False,
    ):
        """Render the window (or only the canvas) to an RGBA array."""
        img = QImg2array(self._screenshot(size, scale, flash, canvas_only))
        if path is not None:
            imsave(path, img)
        return img

    def export_figure(
        self, path: str | None = None, *, scale: float = 1, flash: bool = False
    ):
        """Screenshot of the full data extent, one pixel per data pixel."""
        img = QImg2array(
            self._screenshot(
                scale=scale,
                flash=flash,
                canvas_only=True,
                fit_to_data_extent=True,
            )
        )
        if path is not None:
            imsave(path, img)
        return img

    def clipboard(
        self, flash: bool = False, canvas_only: bool = False
    ) -> None:
        img = self._screenshot(flash=flash, canvas_only=canvas_only)
        QApplication.clipboard().setImage(img)
