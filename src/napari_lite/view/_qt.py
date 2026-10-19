# napari-lite: own code
"""The Qt widget of the view-only canvas: the vispy canvas and one slider
per non-displayed axis; ``show`` opens it in a window."""

from __future__ import annotations

from typing import Any

from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QGridLayout,
    QLabel,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from napari_lite._qt.qt_event_loop import get_qapp
from napari_lite.view._model import View
from napari_lite.view._vispy import VispyRenderer

__all__ = ['QtView', 'show']

_windows: list[QtView] = []  # windows opened by show(), kept alive


def _slider_slot(widget: QtView, axis: int) -> Any:
    """The slot of the slider of ``axis``."""

    def _set(value: int) -> None:
        widget._step_from_slider(axis, value)

    return _set


class QtView(QWidget):
    """A ``View`` drawn by vispy, with a slider for every non-displayed
    axis under the canvas.

    Parameters
    ----------
    view : View, optional
        The model; a new empty one by default (``add_image`` on
        ``widget.view``).
    parent : QWidget, optional
    background : colour
        Canvas colour (default black).
    """

    def __init__(
        self,
        view: View | None = None,
        parent: QWidget | None = None,
        *,
        background: Any = 'black',
    ) -> None:
        get_qapp()
        super().__init__(parent)
        self.view = view if view is not None else View()
        self.renderer = VispyRenderer(self.view, background=background)
        self.renderer.native.setParent(self)
        self._sliders: list[QSlider] = []
        self._values: list[QLabel] = []

        self._axes = QWidget(self)
        self._axes_layout = QGridLayout(self._axes)
        self._axes_layout.setContentsMargins(8, 2, 8, 4)
        self._axes_layout.setHorizontalSpacing(8)
        self._axes_layout.setVerticalSpacing(2)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.renderer.native, stretch=1)
        layout.addWidget(self._axes)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._rebuild_sliders()
        self.view.changed.connect(self._on_view_change)

    # ------------------- model  -----------------------
    def _on_view_change(self, what: str) -> None:
        if what == 'items':
            self._rebuild_sliders()
        elif what == 'current_step':
            self._sliders_from_step()

    @property
    def sliders(self) -> tuple[QSlider, ...]:
        """One per non-displayed axis, in axis order."""
        return tuple(self._sliders)

    def _rebuild_sliders(self) -> None:
        while self._axes_layout.count():
            item = self._axes_layout.takeAt(0)
            if item is not None and (widget := item.widget()) is not None:
                widget.deleteLater()
        self._sliders = []
        self._values = []
        nsteps = self.view.nsteps
        for axis, n in enumerate(nsteps):
            label = QLabel(f'axis {axis}')
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(0, max(n - 1, 0))
            slider.setValue(self.view.current_step[axis])
            slider.valueChanged.connect(_slider_slot(self, axis))
            value = QLabel()
            value.setMinimumWidth(40)
            value.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self._axes_layout.addWidget(label, axis, 0)
            self._axes_layout.addWidget(slider, axis, 1)
            self._axes_layout.addWidget(value, axis, 2)
            self._sliders.append(slider)
            self._values.append(value)
        self._axes_layout.setColumnStretch(1, 1)
        self._axes.setVisible(bool(nsteps))
        self._sliders_from_step()

    def _sliders_from_step(self) -> None:
        nsteps = self.view.nsteps
        for axis, (slider, value) in enumerate(
            zip(self._sliders, self._values, strict=True)
        ):
            step = self.view.current_step[axis]
            slider.blockSignals(True)
            slider.setValue(step)
            slider.blockSignals(False)
            value.setText(f'{step}/{nsteps[axis] - 1}')

    def _step_from_slider(self, axis: int, value: int) -> None:
        step = list(self.view.current_step)
        step[axis] = value
        self.view.current_step = step

    def screenshot(self) -> Any:
        """The canvas as an RGBA uint8 array."""
        return self.renderer.screenshot()

    def closeEvent(self, event: Any) -> None:
        self.view.changed.disconnect(self._on_view_change)
        self.renderer.close()
        if self in _windows:
            _windows.remove(self)
        super().closeEvent(event)


def show(
    image: Any = None,
    points: Any = None,
    *,
    colormap: Any = 'gray',
    contrast_limits: Any = None,
    opacity: float = 1.0,
    rgb: bool = False,
    size: Any = 10.0,
    color: Any = 'cyan',
    title: str = 'napari-lite view',
    run: bool = True,
) -> QtView:
    """Open a window showing ``image`` and/or ``points``.

    Returns the widget (``widget.view`` is the model: more items, the
    current step, the camera).  ``run=False`` returns without starting the
    Qt event loop, for use from IPython or an application of your own.
    """
    get_qapp()
    view = View()
    if image is not None:
        view.add_image(
            image,
            colormap=colormap,
            contrast_limits=contrast_limits,
            opacity=opacity,
            rgb=rgb,
        )
    if points is not None:
        view.add_points(points, size=size, color=color)
    widget = QtView(view)
    widget.setWindowTitle(title)
    widget.resize(800, 640)
    _windows.append(widget)
    widget.show()
    if run:
        from napari_lite._qt.qt_event_loop import run as _run

        _run()
    return widget
