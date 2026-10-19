# napari-lite: own code
"""``Viewer(gui=None)``: a viewer without a window (issue 5,
docs/backends.md), and the front-end lookup behind ``gui``.

On Linux with vispy's egl or osmesa application the headless viewer
draws with no Qt in the process; elsewhere the Qt binding draws into a
widget kept off the screen.  The tests here run on both; the last one
proves the Qt-free path where it exists.
"""

from __future__ import annotations

import gc
import json
import os
import subprocess
import sys
import textwrap

import numpy as np
import pytest

from napari_lite import backends

RED = (255, 0, 0, 255)


def red_image(height: int = 32, width: int = 48) -> np.ndarray:
    rgb = np.zeros((height, width, 3), np.uint8)
    rgb[..., 0] = 255
    return rgb


def centre(img: np.ndarray) -> tuple[int, ...]:
    return tuple(int(v) for v in img[img.shape[0] // 2, img.shape[1] // 2])


@pytest.fixture
def make_headless():
    from napari_lite import Viewer

    viewers = []

    def _make(**kwargs):
        viewer = Viewer(gui=None, **kwargs)
        viewers.append(viewer)
        return viewer

    yield _make
    for viewer in viewers:
        viewer.close()
    gc.collect()


def test_headless_viewer_draws_without_a_window(make_headless) -> None:
    viewer = make_headless(title='no window')
    assert viewer.headless
    viewer.add_image(red_image())
    shot = viewer.screenshot()
    assert shot.ndim == 3
    assert shot.shape[-1] == 4
    assert centre(shot) == RED
    # nothing to show, nothing to dock
    assert not hasattr(viewer, 'window')
    with pytest.raises(AttributeError, match='no window'):
        _ = viewer.window
    with pytest.raises(AttributeError, match='no window'):
        viewer.show()
    if 'qtpy' in sys.modules:  # Qt draws off the screen: nothing shows
        from qtpy.QtCore import Qt
        from qtpy.QtWidgets import QApplication

        on_screen = [
            w
            for w in QApplication.instance().topLevelWidgets()
            if w.isVisible()
            and not w.testAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
        ]
        assert on_screen == []


def test_headless_sizes_and_figure(make_headless, tmp_path) -> None:
    viewer = make_headless()
    viewer.add_image(red_image(32, 48))
    figure = viewer.export_figure()
    assert figure.shape == (32, 48, 4)
    assert centre(figure) == RED
    sized = viewer.screenshot(size=(20, 30))
    assert sized.shape[:2] == (20, 30)
    saved = tmp_path / 'shot.png'
    viewer.screenshot(str(saved))
    assert saved.exists()
    with pytest.raises(ValueError, match='canvas_only'):
        viewer.screenshot(canvas_only=False)


def test_headless_follows_the_model(make_headless) -> None:
    viewer = make_headless()
    # RGB only from 30 px a side (napari's guess); two slices, black and blue
    stack = np.zeros((2, 32, 48, 3), np.uint8)
    stack[1, ..., 2] = 255
    viewer.add_image(stack)
    assert viewer.dims.ndim == 3
    viewer.dims.current_step = (1, 0, 0)
    assert centre(viewer.screenshot()) == (0, 0, 255, 255)
    viewer.layers[0].visible = False
    assert centre(viewer.screenshot())[:3] == (0, 0, 0)
    viewer.layers.remove(viewer.layers[0])
    assert viewer._headless.backend.layer_to_visual == {}


def test_gui_from_the_environment(monkeypatch) -> None:
    from napari_lite import Viewer

    monkeypatch.setenv(backends.GUI_ENVIRONMENT_VARIABLE, 'none')
    viewer = Viewer()
    try:
        assert viewer.headless
    finally:
        viewer.close()
    assert backends.resolve_gui('default') is None
    monkeypatch.setenv(backends.GUI_ENVIRONMENT_VARIABLE, 'Qt')
    assert backends.resolve_gui('default') == 'qt'
    monkeypatch.delenv(backends.GUI_ENVIRONMENT_VARIABLE)
    assert backends.resolve_gui('default') == 'qt'
    # an explicit choice wins over the environment
    monkeypatch.setenv(backends.GUI_ENVIRONMENT_VARIABLE, 'none')
    assert backends.resolve_gui('qt') == 'qt'
    assert backends.resolve_gui(None) is None


def test_unknown_gui() -> None:
    from napari_lite import Viewer

    with pytest.raises(ValueError, match="no front end named 'nope'"):
        Viewer(gui='nope')
    with pytest.raises(ValueError, match="'qt'"):
        backends.get_gui('nope')
    assert backends.available_guis()[0] == 'qt'


def test_the_qt_window_meets_the_window_contract(qtbot) -> None:
    pytest.importorskip('qtpy')
    from napari_lite import Viewer

    assert backends.get_gui('qt').__name__ == 'Window'
    viewer = Viewer(show=False)
    try:
        assert not viewer.headless
        assert isinstance(viewer.window, backends.Window)
    finally:
        viewer.close()


BLOCK_QT = textwrap.dedent(
    """
    import importlib.abc
    import json
    import sys

    BLOCKED = {'qtpy', 'PyQt6', 'PySide6', 'PyQt5', 'PySide2', 'superqt'}

    class Block(importlib.abc.MetaPathFinder):
        def find_spec(self, name, path=None, target=None):
            if name.split('.')[0] in BLOCKED:
                raise ImportError(f'{name} is blocked in this test')
            return None

    sys.meta_path.insert(0, Block())
    """
)


def test_the_renderer_imports_without_qt() -> None:
    """The whole vispy renderer package and the headless canvas import
    with Qt blocked, on every platform (drawing needs an offscreen
    application or Qt; importing does not)."""
    proc = subprocess.run(
        [
            sys.executable,
            '-c',
            BLOCK_QT
            + textwrap.dedent(
                """
                import napari_lite._vispy
                import napari_lite.backends.headless
                from napari_lite._vispy._qt_optional import FontInfo
                print(json.dumps(sorted(
                    m for m in sys.modules if m.split('.')[0] in BLOCKED
                )))
                """
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr[-3000:]
    assert json.loads(proc.stdout.strip().splitlines()[-1]) == []


WITHOUT_QT = BLOCK_QT + textwrap.dedent(
    """
    import numpy as np
    from napari_lite import Viewer

    viewer = Viewer(gui=None)
    rgb = np.zeros((32, 48, 3), np.uint8)
    rgb[..., 0] = 255
    viewer.add_image(rgb)
    viewer.add_points([[16, 24]], size=4, face_color='blue', text='a point')
    shot = viewer.screenshot()
    figure = viewer.export_figure()
    viewer.close()
    print(json.dumps({
        'app': viewer._headless.backend.app_name,
        'centre': shot[shot.shape[0] // 2, shot.shape[1] // 2].tolist(),
        'figure_shape': list(figure.shape),
        'qt_loaded': any(m.split('.')[0] in BLOCKED for m in sys.modules),
    }))
    """
)


def test_headless_without_qt_in_the_process() -> None:
    """Linux with EGL or OSMesa: the viewer draws with Qt blocked.  Where
    vispy has no offscreen application the test is skipped, unless
    NAPARI_LITE_REQUIRE_OFFSCREEN is set (the CI job that installs the
    libraries), when it fails."""
    required = bool(os.environ.get('NAPARI_LITE_REQUIRE_OFFSCREEN'))
    proc = subprocess.run(
        [sys.executable, '-c', WITHOUT_QT],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        if not required and 'none of them is available' in proc.stderr:
            pytest.skip('vispy has no offscreen application here')
        pytest.fail(proc.stderr[-3000:])
    info = json.loads(proc.stdout.strip().splitlines()[-1])
    assert info['app'] in backends.headless.OFFSCREEN_APPS
    assert not info['qt_loaded']
    assert info['figure_shape'] == [32, 48, 4]
    assert tuple(info['centre'])[:3] != (0, 0, 0)  # the point, on the image
