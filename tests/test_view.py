# napari-lite: own code
"""The view-only canvas (napari_lite.view): the model, the vispy renderer
and the Qt widget, built without napari's layers."""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap

import numpy as np
import pytest

from napari_lite.view import ImageItem, PointsItem, View


def stack() -> np.ndarray:
    data = np.zeros((5, 16, 24), dtype=np.uint16)
    for z in range(5):
        data[z] = z * 100
    data[:, 4:8, 6:12] = 1000
    return data


def test_image_item_axes_and_slices() -> None:
    item = ImageItem(stack(), name='stack')
    assert item.ndim == 3
    assert item.shape == (5, 16, 24)
    assert item.contrast_limits == (200.0, 1000.0)  # the middle slice
    sliced = item.slice((3,))
    assert sliced.shape == (16, 24)
    assert sliced.dtype == np.float32
    assert sliced[0, 0] == 300
    assert item.slice((99,))[0, 0] == 400  # clipped to the last slice
    rgb = ImageItem(np.zeros((8, 8, 3), dtype=np.uint8), rgb=True)
    assert rgb.ndim == 2
    assert rgb.contrast_limits is None
    assert rgb.slice(()).shape == (8, 8, 3)
    with pytest.raises(ValueError, match='RGB'):
        ImageItem(np.zeros((8, 8, 5)), rgb=True)
    with pytest.raises(ValueError, match='increase'):
        item.contrast_limits = (5, 5)


def test_points_item_slices_by_rounded_coordinate() -> None:
    coords = np.array([[0.0, 1.0, 2.0], [1.4, 3.0, 4.0], [1.6, 5.0, 6.0]])
    item = PointsItem(coords, size=3)
    assert item.ndim == 3
    assert item.shape == (2, 6, 7)
    assert list(item.slice((1,))) == [1]
    assert list(item.slice((2,))) == [2]
    assert list(item.slice((0,))) == [0]
    assert item.size.tolist() == [3.0, 3.0, 3.0]
    flat = PointsItem(coords[:, 1:])
    assert list(flat.slice(())) == [0, 1, 2]
    with pytest.raises(ValueError, match='positive'):
        item.size = 0


def test_view_steps_align_items_on_the_right() -> None:
    view = View()
    assert view.ndim == 2
    assert view.nsteps == ()
    image = view.add_image(stack())
    assert view.nsteps == (5,)
    assert view.current_step == (2,)  # the middle, as in napari
    points = view.add_points(np.array([[2.0, 3.0, 4.0]]))
    assert view.items == (image, points)
    four = view.add_image(np.zeros((3, 7, 16, 24)))
    assert view.ndim == 4
    assert view.nsteps == (3, 7)
    assert view.current_step == (1, 2)  # new axis in the middle, old kept
    assert image.slice(view.current_step)[0, 0] == 200
    view.current_step = (0, 4)
    assert image.slice(view.current_step)[0, 0] == 400
    assert list(points.slice(view.current_step)) == []
    view.current_step = (0, 2)
    assert list(points.slice(view.current_step)) == [0]
    view.remove(four)
    assert view.nsteps == (5,)
    assert view.current_step == (2,)
    with pytest.raises(ValueError, match='needs 1 values'):
        view.current_step = (1, 2)


def test_view_signals_and_camera() -> None:
    view = View()
    seen: list[str] = []
    view.changed.connect(seen.append)
    image = view.add_image(stack())
    assert seen == ['items', 'current_step']  # items first, then the step
    assert view.extent == ((-0.5, 15.5), (-0.5, 23.5))
    _row, _col, height, width = view.camera.rect
    assert (height, width) == pytest.approx((16 * 1.04, 24 * 1.04))
    assert view.camera.center == pytest.approx((7.5, 11.5))
    view.camera.zoom(2)
    assert view.camera.rect[2:] == pytest.approx((16 * 0.52, 24 * 0.52))
    assert view.camera.center == pytest.approx((7.5, 11.5))
    view.camera.center = (0, 0)
    assert view.camera.center == (0, 0)
    changes: list[str] = []
    image.changed.connect(changes.append)
    image.contrast_limits = (0, 500)
    image.colormap = 'magma'
    image.opacity = 0.5
    assert changes == ['contrast_limits', 'colormap', 'opacity']
    with pytest.raises(ValueError, match='between 0 and 1'):
        image.opacity = 2


@pytest.fixture
def widget(qtbot):
    from napari_lite.view import QtView

    view = View()
    view.add_image(stack(), name='stack')
    view.add_points(
        np.array([[2.0, 4.0, 8.0], [2.0, 12.0, 20.0], [0.0, 1.0, 1.0]]),
        size=2,
        color='yellow',
    )
    w = QtView(view)
    qtbot.addWidget(w)
    w.resize(480, 400)
    w.show()
    qtbot.waitExposed(w)
    return w


def test_renderer_draws_and_follows_the_model(widget, qtbot) -> None:
    from vispy.scene import visuals

    view = widget.view
    image, points = view.items
    renderer = widget.renderer
    assert isinstance(renderer.visual(image), visuals.Image)
    assert isinstance(renderer.visual(points), visuals.Markers)
    shot = widget.screenshot()
    assert shot.shape[-1] == 4
    assert shot[..., :3].max() > 0  # something is drawn
    rgb = shot[..., :3].astype(int)
    yellow = (rgb[..., 0] > 200) & (rgb[..., 1] > 200) & (rgb[..., 2] < 80)
    assert yellow.any()  # the points, over the image
    # the slice follows the step
    assert renderer.visual(image)._data[0, 0] == 200
    view.current_step = (4,)
    assert renderer.visual(image)._data[0, 0] == 400
    # points outside the slice are not drawn
    assert not renderer.visual(points).visible
    view.current_step = (2,)
    assert renderer.visual(points).visible
    # appearance
    image.contrast_limits = (0, 2000)
    assert tuple(renderer.visual(image).clim) == (0, 2000)
    image.colormap = 'green'
    image.opacity = 0.25
    assert renderer.visual(image).opacity == 0.25
    image.visible = False
    assert not renderer.visual(image).visible
    with pytest.raises(ValueError, match='unknown colormap'):
        image.colormap = 'no-such-map'
    # removing an item removes its visual
    view.remove(points)
    assert points not in renderer._visuals


def test_colormaps_resolve_without_matplotlib() -> None:
    from vispy.color.colormap import BaseColormap

    from napari_lite.view import COLORMAPS
    from napari_lite.view._vispy import vispy_colormap

    for name in ('gray', 'viridis', 'magma', 'turbo', 'green'):
        assert name in COLORMAPS
        assert isinstance(vispy_colormap(name), BaseColormap)
    assert len(vispy_colormap('magma').colors) == 256  # napari's listed data
    assert vispy_colormap('green').colors.rgb[-1].tolist() == pytest.approx(
        [0, 128 / 255, 0], abs=1e-6
    )
    assert isinstance(vispy_colormap(['black', 'red']), BaseColormap)
    with pytest.raises(ValueError, match='unknown colormap'):
        vispy_colormap('no-such-map')


def test_camera_syncs_both_ways(widget, qtbot) -> None:
    view = widget.view
    renderer = widget.renderer
    view.camera.rect = (2, 3, 8, 12)
    rect = renderer.camera.rect
    # the model's rectangle is shown at least; vispy keeps the aspect
    assert rect.pos[0] <= 3 and rect.pos[1] <= 2
    assert rect.size[0] >= 12 and rect.size[1] >= 8
    renderer.camera.rect = (0, 0, 24, 16)  # x, y, width, height
    assert view.camera.rect == (0, 0, 16, 24)
    view.reset_view()
    assert view.camera.center == pytest.approx((7.5, 11.5))


def test_sliders_follow_the_axes(widget, qtbot) -> None:
    view = widget.view
    assert len(widget.sliders) == 1
    slider = widget.sliders[0]
    assert (slider.minimum(), slider.maximum(), slider.value()) == (0, 4, 2)
    slider.setValue(4)
    assert view.current_step == (4,)
    view.current_step = (1,)
    assert slider.value() == 1
    view.add_image(np.zeros((3, 5, 16, 24)))
    assert len(widget.sliders) == 2
    assert [s.maximum() for s in widget.sliders] == [2, 4]
    view.clear()
    assert widget.sliders == ()


def test_show_opens_a_window(qtbot) -> None:
    from napari_lite.view import show

    w = show(stack(), np.array([[2.0, 1.0, 1.0]]), colormap='magma', run=False)
    qtbot.addWidget(w)
    assert w.windowTitle() == 'napari-lite view'
    assert w.isVisible()
    assert [type(i).__name__ for i in w.view.items] == [
        'ImageItem',
        'PointsItem',
    ]
    assert w.view.items[0].colormap == 'magma'
    w.close()


def test_model_imports_without_qt_or_vispy() -> None:
    code = textwrap.dedent(
        """
        import json, sys
        import napari_lite.view
        from napari_lite.view import View
        View().add_image(__import__('numpy').zeros((4, 4)))
        heavy = [m for m in ('qtpy', 'PyQt6', 'PySide6', 'vispy', 'pydantic')
                 if m in sys.modules]
        print(json.dumps(heavy))
        """
    )
    proc = subprocess.run(
        [sys.executable, '-c', code],
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(proc.stdout.strip().splitlines()[-1]) == []
