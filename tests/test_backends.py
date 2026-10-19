# napari-lite: own code
"""The renderer contract (issue 5, docs/backends.md): a renderer that is
not vispy, made of nothing but the ``CanvasBackend`` methods, drives the
viewer with a window and without one; the lookup by name and by
environment variable."""

from __future__ import annotations

import gc
from typing import ClassVar

import numpy as np
import pytest

from napari_lite import backends


class FakeBackend:
    """Records what the front ends ask of a renderer; draws nothing."""

    made: ClassVar[list[FakeBackend]] = []

    def __init__(self, viewer, *, gui=None, parent=None):
        self.viewer = viewer
        self.gui = gui
        self.parent = parent
        self.calls: list[tuple] = []
        self.closed = False
        if gui == 'qt':
            from qtpy.QtWidgets import QWidget

            self.native = QWidget(parent)
        else:
            self.native = None
        viewer.layers.events.inserted.connect(
            lambda event: self.calls.append(('layer added', event.value.name))
        )
        viewer.layers.events.removed.connect(
            lambda event: self.calls.append(
                ('layer removed', event.value.name)
            )
        )
        FakeBackend.made.append(self)

    def screenshot(
        self,
        *,
        size=None,
        scale=1.0,
        fit_to_data_extent=False,
        device_pixel_ratio=1.0,
    ):
        self.calls.append(('screenshot', size, scale, fit_to_data_extent))
        height, width = (10, 20) if size is None else size
        img = np.zeros((height, width, 4), np.uint8)
        img[..., 1] = 255  # green, so it is plainly not vispy's drawing
        img[..., 3] = 255
        return img

    def key_event(self, event, *, release=False):
        self.calls.append(('key', event.key(), release))

    def close(self):
        self.closed = True


@pytest.fixture(autouse=True)
def _forget_fakes():
    FakeBackend.made.clear()
    yield
    FakeBackend.made.clear()
    gc.collect()


def test_the_contract_is_met_by_both() -> None:
    assert isinstance(FakeBackend(_model(), gui=None), backends.CanvasBackend)
    assert backends.get_renderer('vispy').__name__ == 'VispyBackend'


def _model():
    from napari_lite.components import ViewerModel

    return ViewerModel()


def test_headless_viewer_runs_on_another_renderer() -> None:
    from napari_lite import Viewer

    viewer = Viewer(gui=None, renderer=FakeBackend)
    try:
        (fake,) = FakeBackend.made
        assert fake.gui is None
        assert fake.native is None
        viewer.add_image(np.zeros((4, 4)), name='img')
        viewer.layers.remove('img')
        shot = viewer.screenshot(size=(6, 8))
        assert shot.shape == (6, 8, 4)
        assert tuple(shot[3, 4]) == (0, 255, 0, 255)
        figure = viewer.export_figure()
        assert figure.shape == (10, 20, 4)
        assert fake.calls == [
            ('layer added', 'img'),
            ('layer removed', 'img'),
            ('screenshot', (6, 8), 1.0, False),
            ('screenshot', None, 1.0, True),
        ]
    finally:
        viewer.close()
    assert fake.closed


def test_window_runs_on_another_renderer(qtbot) -> None:
    pytest.importorskip('qtpy')
    from qtpy.QtCore import Qt
    from qtpy.QtTest import QTest

    from napari_lite import Viewer

    viewer = Viewer(show=False, renderer=FakeBackend)
    try:
        (fake,) = FakeBackend.made
        assert fake.gui == 'qt'
        canvas = viewer.window._qt_viewer
        assert fake.parent is canvas
        assert fake.native.parent() is canvas
        assert canvas.canvas is None  # no vispy canvas anywhere
        viewer.add_image(np.zeros((4, 4)), name='img')
        shot = viewer.screenshot()
        assert shot.shape == (10, 20, 4)
        assert tuple(shot[5, 10]) == (0, 255, 0, 255)
        QTest.keyClick(canvas, Qt.Key.Key_A)
        assert ('key', Qt.Key.Key_A.value, False) in fake.calls
        assert ('key', Qt.Key.Key_A.value, True) in fake.calls
    finally:
        viewer.close()
    assert fake.closed


def test_qt_canvas_takes_a_renderer(qtbot) -> None:
    pytest.importorskip('qtpy')
    from napari_lite.qt import QtCanvas

    canvas = QtCanvas(_model(), renderer=FakeBackend)
    qtbot.addWidget(canvas)
    (fake,) = FakeBackend.made
    assert canvas.backend is fake
    assert canvas.screenshot(size=(3, 5)).shape == (3, 5, 4)
    canvas.close()
    assert fake.closed


def test_renderer_lookup(monkeypatch) -> None:
    assert backends.resolve_renderer(FakeBackend) is FakeBackend
    assert backends.resolve_renderer('default').__name__ == 'VispyBackend'
    assert backends.resolve_renderer('Vispy').__name__ == 'VispyBackend'
    assert backends.available_renderers()[0] == 'vispy'
    with pytest.raises(ValueError, match="no renderer named 'nope'"):
        backends.get_renderer('nope')
    monkeypatch.setenv(backends.RENDERER_ENVIRONMENT_VARIABLE, 'nope')
    with pytest.raises(ValueError, match="'nope'"):
        backends.resolve_renderer('default')
    # an explicit choice wins over the environment
    assert backends.resolve_renderer('vispy').__name__ == 'VispyBackend'


def test_the_vispy_renderer_draws_for_its_front_ends_only() -> None:
    from napari_lite._vispy.backend import VispyBackend

    with pytest.raises(ValueError, match="'qt' or 'jupyter' front end"):
        VispyBackend(_model(), gui='something else')
