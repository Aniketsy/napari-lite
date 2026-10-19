# napari-lite: own code
"""The renderer contract (issue 5): a renderer that is
not vispy, made of nothing but the ``CanvasBackend`` methods, drives the
viewer with a window and without one; the lookup by name and by
environment variable."""

from __future__ import annotations

import gc
import os
import sys
from types import SimpleNamespace
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


def test_the_contract_is_met_by_both(qapp) -> None:
    from napari_lite._vispy._qt_optional import use_vispy_app

    assert isinstance(FakeBackend(_model(), gui=None), backends.CanvasBackend)
    vispy_class = backends.get_renderer('vispy')
    assert vispy_class.__name__ == 'VispyBackend'
    use_vispy_app('qt')  # Qt draws off the screen in this process
    renderer = vispy_class(_model(), gui=None)
    try:
        assert isinstance(renderer, backends.CanvasBackend)
        assert renderer.native is None  # no window, nothing to place
    finally:
        renderer.close()


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


def test_egl_resize_events_once_per_change() -> None:
    """vispy's egl backend sends no resize events, so the renderer sends
    them, once per change.  napari's canvas writes each resize back through
    the model: the same size again, which must send nothing (vispy refuses
    a resize event inside another; Linux CI caught it)."""
    from vispy.util.event import EmitterGroup

    from napari_lite._vispy.backend import VispyBackend

    class EglLikeBackend:
        """vispy's egl canvas backend, as far as sizes go."""

        def __init__(self) -> None:
            self._size = (800, 600)
            self.surfaces = 0

        def _vispy_set_size(self, width: int, height: int) -> None:
            self._size = (width, height)  # a new surface, no event
            self.surfaces += 1

        def _vispy_get_size(self) -> tuple[int, int]:
            return self._size

    class SceneCanvas:
        def __init__(self) -> None:
            self._backend = EglLikeBackend()
            self.events = EmitterGroup(source=self, resize=None)

        @property
        def size(self) -> tuple[int, int]:
            return self._backend._vispy_get_size()

        @size.setter
        def size(self, size: tuple[int, int]) -> None:
            self._backend._vispy_set_size(*size)

    scene_canvas = SceneCanvas()
    sizes = []

    def write_back(event) -> None:  # napari's canvas, through the model
        sizes.append(tuple(event.size))
        scene_canvas.size = tuple(event.size)

    scene_canvas.events.resize.connect(write_back)
    renderer = VispyBackend.__new__(VispyBackend)
    renderer.canvas = SimpleNamespace(_scene_canvas=scene_canvas)
    renderer._fill_in_for_egl()  # tells the canvas its first size
    scene_canvas.size = (200, 100)
    scene_canvas.size = (200, 100)  # the size it has: nothing happens
    assert sizes == [(800, 600), (200, 100)]
    assert scene_canvas._backend.surfaces == 1
    assert scene_canvas._backend._double_click_supported


def test_pyopengl_is_readied_for_egl(monkeypatch) -> None:
    """napari's GL calls go through PyOpenGL, which settles its platform
    when first imported (GLX on Linux) and then refuses functions in an
    EGL context (Linux CI caught it).  Before vispy is imported for a
    viewer without a Qt window, PYOPENGL_PLATFORM becomes egl on Linux
    where vispy's egl application loads; nothing changes otherwise."""
    from napari_lite.utils import _pyopengl

    variable = _pyopengl.PLATFORM_VARIABLE
    # recorded first, so that the variable is as before once the test ends
    # (delenv records nothing for a variable that is not set)
    monkeypatch.setenv(variable, 'set by the test')

    def outcome(**conditions) -> str | None:
        monkeypatch.delenv(variable, raising=False)
        monkeypatch.setattr(sys, 'platform', conditions.get('os', 'linux'))
        monkeypatch.delitem(sys.modules, 'OpenGL.platform', raising=False)
        if conditions.get('pyopengl_loaded'):
            monkeypatch.setitem(sys.modules, 'OpenGL.platform', object())
        if conditions.get('variable'):
            monkeypatch.setenv(variable, conditions['variable'])
        chosen = conditions.get('app_chosen', False)
        loads = conditions.get('egl_loads', True)
        monkeypatch.setattr(_pyopengl, '_vispy_app_chosen', lambda: chosen)
        monkeypatch.setattr(_pyopengl, '_egl_app_loads', lambda: loads)
        _pyopengl.prefer_egl()
        return os.environ.get(variable)

    assert outcome() == 'egl'
    assert outcome(os='win32') is None
    assert outcome(os='darwin') is None
    assert outcome(egl_loads=False) is None
    assert outcome(app_chosen=True) is None
    assert outcome(pyopengl_loaded=True) is None
    assert outcome(variable='glx') == 'glx'


def test_the_renderer_lookup_readies_pyopengl(monkeypatch) -> None:
    """Only for vispy, and only without a Qt window."""
    from napari_lite.utils import _pyopengl

    calls = []
    monkeypatch.setattr(_pyopengl, 'prefer_egl', lambda: calls.append(1))
    monkeypatch.delenv(backends.RENDERER_ENVIRONMENT_VARIABLE, raising=False)
    for gui, expected in [(None, 1), ('jupyter', 1), ('qt', 0)]:
        calls.clear()
        backends.resolve_renderer('default', gui=gui)
        assert len(calls) == expected, gui
    calls.clear()
    backends.resolve_renderer(FakeBackend, gui=None)
    backends.resolve_renderer('vispy')  # a Qt window by default
    assert calls == []


def test_egl_drawing_needs_pyopengl_on_egl(monkeypatch) -> None:
    """vispy's egl application is chosen only where PyOpenGL draws
    through EGL too; otherwise Qt draws off the screen."""
    from vispy import app

    from napari_lite._vispy._qt_optional import available_offscreen_app
    from napari_lite.utils import _pyopengl

    monkeypatch.setattr(app, 'Application', lambda name: None)  # it loads
    monkeypatch.setattr(_pyopengl, 'pyopengl_on_egl', lambda: False)
    assert available_offscreen_app() is None
    monkeypatch.setattr(_pyopengl, 'pyopengl_on_egl', lambda: True)
    assert available_offscreen_app() == 'egl'


def test_the_vispy_renderer_draws_for_its_front_ends_only() -> None:
    from napari_lite._vispy.backend import VispyBackend

    with pytest.raises(ValueError, match="'qt' or 'jupyter' toolkit"):
        VispyBackend(_model(), gui='something else')
