# napari-lite: own code
"""The viewer window: a ``QMainWindow`` around a ``QtCanvas``.

napari's main window carries menus, a status bar, the layer list and
layer-control docks, the console, a welcome screen and the command palette.
napari-lite's window has the canvas, the dims sliders and a status line,
plus ``add_dock_widget`` so users (and the opt-in layer list and controls
of issue 21) can dock their own widgets next to the canvas.

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
    QToolTip,
    QWidget,
)

from napari_lite._qt.qt_event_loop import get_qapp
from napari_lite._qt.utils import QImg2array
from napari_lite.qt.canvas import QtCanvas
from napari_lite.utils.io import imsave
from napari_lite.utils.misc import in_jupyter
from napari_lite.utils.task_status import Status, TaskStatusManager
from napari_lite.utils.theme import Theme, get_system_theme, get_theme

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from qtpy.QtGui import QCloseEvent, QImage, QKeyEvent

    from napari_lite.components import ViewerModel
    from napari_lite.utils.events import Event

__all__ = ['Window']

_DOCK_AREAS = {
    'left': Qt.DockWidgetArea.LeftDockWidgetArea,
    'right': Qt.DockWidgetArea.RightDockWidgetArea,
    'top': Qt.DockWidgetArea.TopDockWidgetArea,
    'bottom': Qt.DockWidgetArea.BottomDockWidgetArea,
}


class _NoThread:
    """Stand-in for napari's status thread (napari-lite computes the status
    on the main thread); ``_qt/utils.py`` asks it whether it is running."""

    def isRunning(self) -> bool:
        return False

    def close_terminate(self) -> None:
        return None

    def wait(self) -> None:
        return None


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
        self._qt_viewer = QtCanvas(viewer)
        self.status_thread = _NoThread()
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setCentralWidget(self._qt_viewer)
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
        area: str = 'right',
        allowed_areas: Sequence[str] | None = None,
        add_vertical_stretch: bool = True,
        tabify: bool = False,
        menu: Any = None,
    ) -> QDockWidget:
        """Dock ``widget`` (a QWidget or a magicgui widget) next to the canvas.

        Parameters
        ----------
        widget : QWidget or magicgui Widget
            The widget to dock; a magicgui widget's ``native`` widget is used.
        name : str
            Title of the dock; a generic name is made up if empty.
        area : {'left', 'right', 'top', 'bottom'}
            Where to dock (default 'right').
        allowed_areas : sequence of str, optional
            Areas the dock may be moved to; all by default.
        add_vertical_stretch : bool
            Accepted for compatibility with napari; ignored.
        tabify : bool
            Tab the new dock with the others in the same area.
        menu : object
            Accepted for compatibility with napari; ignored (no menus).

        Returns
        -------
        QDockWidget
        """
        if not name:
            with contextlib.suppress(AttributeError):
                name = widget.objectName()
            name = name or f'Dock widget {self._unnamed_dockwidget_count}'
            self._unnamed_dockwidget_count += 1
        inner = getattr(widget, 'native', widget)  # magicgui -> QWidget
        if not isinstance(inner, QWidget):
            raise TypeError(
                '"widget" must be a QWidget or a magicgui Widget, got '
                f'{type(widget).__name__}'
            )
        dock = QDockWidget(name, self._qt_window)
        dock.setObjectName(name)
        dock.setWidget(inner)
        if allowed_areas:
            flags = Qt.DockWidgetArea(0)
            for allowed in allowed_areas:
                flags |= _DOCK_AREAS[allowed]
            dock.setAllowedAreas(flags)
        qt_area = _DOCK_AREAS[area]
        self._qt_window.addDockWidget(qt_area, dock)
        if tabify:
            for other in self._wrapped_dock_widgets.values():
                if other is not dock and (
                    self._qt_window.dockWidgetArea(other) == qt_area
                ):
                    self._qt_window.tabifyDockWidget(other, dock)
                    break
        if hasattr(widget, 'reset_choices'):
            # keep magicgui layer dropdowns in sync with the layer list
            layers_events = self.viewer.layers.events
            layers_events.inserted.connect(widget.reset_choices)
            layers_events.removed.connect(widget.reset_choices)
            layers_events.reordered.connect(widget.reset_choices)
            layers_events.renamed.connect(widget.reset_choices)
        self._wrapped_dock_widgets[name] = dock
        return dock

    def remove_dock_widget(self, widget: Any, menu: Any = None) -> None:
        """Remove a dock added with ``add_dock_widget`` (the dock, or the
        widget inside it, or its name)."""
        if widget == 'all':
            for name in list(self._wrapped_dock_widgets):
                self._remove_dock(name)
            return
        inner = getattr(widget, 'native', widget)
        for name, dock in list(self._wrapped_dock_widgets.items()):
            if widget in (dock, name) or dock.widget() is inner:
                self._remove_dock(name)
                return
        raise LookupError(
            f'Could not find a dock widget containing {widget!r}'
        )

    def _remove_dock(self, name: str) -> None:
        dock = self._wrapped_dock_widgets.pop(name)
        self._qt_window.removeDockWidget(dock)
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
        """Color the window after the viewer's theme (a small stylesheet;
        napari builds its full QSS from ``_qt/qt_resources``)."""
        with contextlib.suppress(AttributeError, RuntimeError, ValueError):
            theme_name = self.viewer.theme
            if theme_name == 'system':
                theme_name = get_system_theme()
            self._qt_window.setStyleSheet(stylesheet(get_theme(theme_name)))

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


def stylesheet(theme: Theme) -> str:
    """A compact Qt stylesheet with the theme's colors."""
    background = theme.background.as_rgb()
    foreground = theme.foreground.as_rgb()
    primary = theme.primary.as_rgb()
    highlight = theme.highlight.as_rgb()
    current = theme.current.as_rgb()
    text = theme.text.as_rgb()
    return f"""
QWidget {{ background-color: {background}; color: {text}; }}
QLabel {{ background-color: transparent; }}
QToolTip {{ background-color: {foreground}; color: {text};
            border: 1px solid {primary}; padding: 2px; }}
QDockWidget::title {{ background-color: {foreground}; padding: 4px; }}
QSlider::groove:horizontal {{ background-color: {foreground}; height: 6px;
                              border-radius: 3px; }}
QSlider::handle:horizontal {{ background-color: {highlight}; width: 12px;
                              margin: -4px 0; border-radius: 6px; }}
QSlider::handle:horizontal:hover {{ background-color: {current}; }}
QScrollBar {{ background-color: {foreground}; }}
QPushButton {{ background-color: {primary}; border: none; padding: 4px;
               border-radius: 3px; }}
QPushButton:hover {{ background-color: {highlight}; }}
QPushButton:checked {{ background-color: {current}; }}
"""
