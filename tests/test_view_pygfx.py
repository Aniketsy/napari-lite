# napari-lite: own code
"""The pygfx renderer of the view-only canvas: the same model drawn by a
second renderer, and the proof that the split holds."""

from __future__ import annotations

import numpy as np
import pytest

from napari_lite.view import Renderer, View

pytest.importorskip('pygfx')
wgpu = pytest.importorskip('wgpu')
try:
    wgpu.gpu.request_adapter_sync()
except Exception:  # whatever wgpu raises without a GPU
    pytest.skip('no WGPU adapter on this machine', allow_module_level=True)


def stack() -> np.ndarray:
    data = np.zeros((5, 16, 24), dtype=np.uint16)
    for z in range(5):
        data[z] = z * 100
    data[:, 4:8, 6:12] = 1000
    return data


@pytest.fixture
def offscreen():
    """A pygfx renderer on an offscreen canvas, 400 by 240 pixels."""
    from rendercanvas.offscreen import RenderCanvas

    from napari_lite.view._pygfx import PygfxRenderer

    made = []

    def _make(view: View, size=(400, 240)) -> PygfxRenderer:
        canvas = RenderCanvas(size=size, pixel_ratio=1)
        renderer = PygfxRenderer(view, canvas=canvas, size=size, pixel_ratio=1)
        made.append(renderer)
        return renderer

    yield _make
    for renderer in made:
        renderer.close()


def test_pygfx_is_a_renderer(offscreen) -> None:
    view = View()
    view.add_image(stack())
    renderer = offscreen(view)
    assert isinstance(renderer, Renderer)


def test_pygfx_draws_and_follows_the_model(offscreen) -> None:
    view = View()
    image = view.add_image(stack(), contrast_limits=(0, 1000))
    points = view.add_points(
        np.array([[2.0, 4.0, 8.0], [0.0, 1.0, 1.0]]), size=3, color='red'
    )
    renderer = offscreen(view)
    shot = renderer.screenshot()
    assert shot.shape == (240, 400, 4)
    assert shot[..., :3].max() > 0
    rgb = shot[..., :3].astype(int)
    red = (rgb[..., 0] > 200) & (rgb[..., 1] < 80) & (rgb[..., 2] < 80)
    assert red.any()  # the point of the middle slice, over the image
    assert renderer.adapter(image).array[0, 0] == 200
    view.current_step = (4,)
    assert renderer.adapter(image).array[0, 0] == 400
    assert not renderer.node(points).visible  # no point in slice 4
    view.current_step = (2,)
    assert renderer.node(points).visible
    image.contrast_limits = (0, 2000)
    assert tuple(renderer.node(image).material.clim) == (0, 2000)
    image.colormap = 'magma'
    image.opacity = 0.5
    assert renderer.node(image).material.opacity == 0.5
    image.visible = False
    assert not renderer.node(image).visible
    view.remove(points)
    with pytest.raises(KeyError):
        renderer.node(points)


def test_pygfx_matches_vispy(offscreen, qtbot) -> None:
    """Both renderers draw the same model identically at pixel centres:
    the same orientation, pixel placement, colormap and contrast."""
    from napari_lite.view import VispyRenderer

    rng = np.random.default_rng(5)
    data = rng.integers(0, 1000, size=(60, 100), dtype=np.uint16)

    def make_view() -> View:
        view = View()
        view.add_image(data, colormap='gray', contrast_limits=(0, 1000))
        view.camera.rect = (-0.5, -0.5, 60, 100)
        return view

    with_pygfx = offscreen(make_view()).screenshot()
    vispy = VispyRenderer(make_view(), size=(400, 240))
    qtbot.addWidget(vispy.native)
    vispy.native.show()
    qtbot.waitExposed(vispy.native)
    with_vispy = vispy.screenshot()
    vispy.close()
    assert with_pygfx.shape == with_vispy.shape == (240, 400, 4)
    centres = (slice(2, None, 4), slice(2, None, 4))
    diff = np.abs(
        with_pygfx[centres][..., :3].astype(int)
        - with_vispy[centres][..., :3].astype(int)
    )
    assert diff.max() <= 1


def test_pygfx_camera_both_ways(offscreen) -> None:
    view = View()
    view.add_image(stack())
    renderer = offscreen(view)
    view.camera.rect = (2, 3, 8, 12)
    camera = renderer.camera
    assert (camera.width, camera.height) == (12, 8)
    assert tuple(camera.local.position[:2]) == pytest.approx((9, -6))
    # the controller moves the camera; the next draw tells the model
    camera.width, camera.height = 24, 16
    camera.local.position = (12, -8, 1)
    renderer._draw()
    assert view.camera.rect == pytest.approx((0, 0, 16, 24))


def test_pygfx_cursor_and_values(offscreen) -> None:
    view = View()
    view.add_image(stack(), contrast_limits=(0, 1000))
    renderer = offscreen(view)
    renderer.screenshot()  # a render sets the projection for this size
    seen = []
    renderer.cursor_moved.connect(seen.append)

    class Event:
        x, y = 200.0, 120.0  # the middle of the canvas

    renderer._on_pointer(Event())
    row, col = seen[-1]
    assert (row, col) == pytest.approx(view.camera.center, abs=0.05)
    assert renderer.value_at(4, 8) == 1000
    assert renderer.value_at(-1, 0) is None


def test_qtview_with_pygfx(qtbot) -> None:
    from napari_lite.view import QtView

    view = View()
    image = view.add_image(stack(), contrast_limits=(0, 1000))
    w = QtView(view, renderer='pygfx')
    qtbot.addWidget(w)
    w.resize(480, 400)
    w.show()
    qtbot.waitExposed(w)
    assert len(w.sliders) == 1
    w.sliders[0].setValue(4)
    assert w.renderer.adapter(image).array[0, 0] == 400
    shot = w.screenshot()
    assert shot[..., :3].max() > 0
    w.renderer.cursor_moved.emit((4.0, 8.0))
    assert w.readout == '[4 4 8]: 1000'
    w.close()
