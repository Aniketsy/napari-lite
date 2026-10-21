# napari-lite: own code
"""``Viewer(gui='jupyter')``: the viewer as widgets in a notebook cell
(issue 5).

The canvas widget streams frames of the renderer's off-screen canvas and
hands browser events back to it; these tests play the browser by calling
the widget the way jupyter_rfb does.  In-process tests draw with Qt off
the screen; the last test proves the Qt-free path where vispy has an
offscreen application (Linux with EGL).
"""

from __future__ import annotations

import asyncio
import gc
import json
import logging
import os
import subprocess
import sys
import textwrap
import threading
import time
from datetime import UTC
from types import SimpleNamespace

import numpy as np
import pytest

pytest.importorskip('jupyter_rfb')
widgets = pytest.importorskip('ipywidgets')


from napari_lite import backends  # noqa: E402


def centre(img: np.ndarray) -> tuple[int, ...]:
    return tuple(int(v) for v in img[img.shape[0] // 2, img.shape[1] // 2])


def pointer(kind: str, x: float, y: float, buttons=(), **extra) -> dict:
    return {
        'type': kind,
        'x': x,
        'y': y,
        'button': extra.pop('button', 0),
        'buttons': list(buttons),
        'modifiers': extra.pop('modifiers', []),
        'ntouches': 0,
        'touches': {},
        **extra,
    }


@pytest.fixture
def make_notebook_viewer(qapp):
    """Notebook viewers drawn by Qt off the screen in this process; Qt is
    vispy's application here (one per process), whatever else exists."""
    from napari_lite import Viewer
    from napari_lite._vispy._qt_optional import use_vispy_app

    use_vispy_app('qt')
    viewers = []

    def _make(**kwargs):
        kwargs.setdefault('show', False)
        viewer = Viewer(gui='jupyter', **kwargs)
        viewers.append(viewer)
        return viewer

    yield _make
    for viewer in viewers:
        viewer.close()
    gc.collect()


def test_window_layout_and_contract(make_notebook_viewer) -> None:
    from jupyter_rfb import RemoteFrameBuffer

    from napari_lite.backends.jupyter import JupyterWindow

    viewer = make_notebook_viewer(title='in a cell')
    window = viewer.window
    assert backends.get_gui('jupyter') is JupyterWindow
    assert isinstance(window, JupyterWindow)
    assert isinstance(window, backends.Window)
    assert isinstance(window.widget, widgets.HBox)
    assert isinstance(window.backend.native, RemoteFrameBuffer)
    assert 'in a cell' in window._title.value
    viewer.title = 'renamed'
    assert 'renamed' in window._title.value
    assert not viewer.headless


def test_frames_follow_the_model(make_notebook_viewer, monkeypatch) -> None:
    viewer = make_notebook_viewer()
    rfb = viewer.window.backend.native
    requested = []
    monkeypatch.setattr(rfb, 'request_draw', lambda: requested.append(1))
    # vispy passes changes on to the widget once a frame has been drawn
    rfb.get_frame()
    stack = np.zeros((2, 32, 48, 3), np.uint8)
    stack[0, ..., 0] = 255  # red, then blue
    stack[1, ..., 2] = 255
    viewer.add_image(stack)
    assert requested  # the scene changed: the browser is asked for a frame
    frame = rfb.get_frame()
    assert frame.shape == (600, 800, 4)
    assert centre(frame) == (255, 0, 0, 255)
    requested.clear()
    viewer.dims.current_step = (1, 0, 0)
    assert requested
    assert centre(rfb.get_frame()) == (0, 0, 255, 255)
    # changes made while a frame is drawn are in that frame: no new request
    requested.clear()
    rfb.get_frame()
    assert not requested


def test_sliders_and_buttons(make_notebook_viewer) -> None:
    viewer = make_notebook_viewer()
    window = viewer.window
    viewer.add_image(np.zeros((5, 16, 16)))
    assert list(window._sliders_by_axis) == [0]
    slider = window._sliders_by_axis[0]
    assert (slider.min, slider.max) == (0, 4)
    slider.value = 3
    assert viewer.dims.current_step[0] == 3
    viewer.dims.set_current_step(0, 1)
    assert slider.value == 1
    window._ndisplay.value = True
    assert viewer.dims.ndisplay == 3
    assert window._sliders_by_axis == {}
    viewer.dims.ndisplay = 2
    assert window._ndisplay.value is False
    assert list(window._sliders_by_axis) == [0]
    viewer.camera.zoom = 50
    window._reset.click()
    assert viewer.camera.zoom < 50


def test_layer_list(make_notebook_viewer) -> None:
    viewer = make_notebook_viewer()
    window = viewer.window
    image = viewer.add_image(np.zeros((16, 16)), name='image')
    points = viewer.add_points([[2, 2]], name='points')
    names = [
        row.children[1].description for row in window._layer_rows.children
    ]
    assert names == ['points', 'image']  # top layer first, as in napari
    box = window._visible_boxes[id(image)]
    box.value = False
    assert image.visible is False
    image.visible = True
    assert box.value is True
    window._name_buttons[id(image)].click()
    assert viewer.layers.selection.active is image
    assert window._name_buttons[id(image)].button_style == 'info'
    assert window._name_buttons[id(points)].button_style == ''
    image.name = 'renamed'
    assert window._name_buttons[id(image)].description == 'renamed'
    viewer.layers.remove(points)
    assert len(window._layer_rows.children) == 1
    # the removed layer's events no longer reach the window
    points.visible = False
    points.name = 'gone'
    assert [b.description for b in window._name_buttons.values()] == [
        'renamed'
    ]
    assert list(window._visible_boxes) == [id(image)]


def test_browser_events(make_notebook_viewer) -> None:
    viewer = make_notebook_viewer()
    rfb = viewer.window.backend.native
    viewer.add_image(np.random.random((3, 64, 96)))
    viewer.layers.selection.active = viewer.layers[0]
    rfb.get_frame()
    rfb.handle_event(pointer('pointer_enter', 400, 300))
    assert viewer.mouse_over_canvas
    assert viewer.status == 'Ready'
    center = viewer.camera.center
    rfb.handle_event(pointer('pointer_down', 400, 300, [1], button=1))
    for i in range(1, 6):
        time.sleep(0.02)  # vispy skips moves closer than 10 ms
        rfb.handle_event(pointer('pointer_move', 400 + 20 * i, 300, [1]))
    rfb.handle_event(pointer('pointer_up', 500, 300, button=1))
    rfb.get_frame()  # napari takes the camera into the model as it draws
    assert viewer.camera.center[-1] < center[-1]  # dragged right: panned
    zoom = viewer.camera.zoom
    rfb.handle_event(pointer('wheel', 400, 300, dx=0, dy=-100))
    rfb.get_frame()
    assert viewer.camera.zoom > zoom
    step = viewer.dims.current_step[0]
    rfb.handle_event(
        pointer('wheel', 400, 300, dx=0, dy=100, modifiers=['Control'])
    )
    assert viewer.dims.current_step[0] != step  # Control + wheel: slices
    pressed = []
    viewer.bind_key('k', lambda v: pressed.append('k'), overwrite=True)
    for kind in ('key_down', 'key_up'):
        rfb.handle_event({'type': kind, 'key': 'k', 'modifiers': []})
    assert pressed == ['k']
    viewer.dims.set_current_step(0, 0)
    for kind in ('key_down', 'key_up'):  # napari's shortcut for the slider
        rfb.handle_event({'type': kind, 'key': 'ArrowRight', 'modifiers': []})
    assert viewer.dims.current_step[0] == 1
    rfb.handle_event(
        {'type': 'resize', 'width': 320, 'height': 200, 'ratio': 1}
    )
    assert viewer.canvas.size == (200, 320)
    assert rfb.get_frame().shape == (200, 320, 4)
    rfb.handle_event(pointer('pointer_leave', 0, 0))
    assert not viewer.mouse_over_canvas


def test_widget_messages_from_another_thread() -> None:
    """JupyterLab runs widget callbacks on a kernel subshell's thread;
    canvas work must happen on the viewer's thread (Qt ends the process
    when a GL context is made current elsewhere)."""
    pytest.importorskip('qtpy')
    from napari_lite import Viewer
    from napari_lite._vispy._qt_optional import use_vispy_app

    use_vispy_app('qt')
    main = threading.get_ident()

    async def scenario() -> None:
        # made inside the running loop, as a notebook cell makes it
        viewer = Viewer(gui='jupyter', show=False)
        try:
            viewer.add_image(np.zeros((4, 16, 16)))
            window = viewer.window
            rfb = window.backend.native
            handled, sent, results = set(), [], {}
            handle = rfb._handle

            def record(event):
                handled.add(threading.get_ident())
                handle(event)

            rfb._handle = record
            rfb.send_frame = lambda array: sent.append(
                (threading.get_ident(), array.shape)
            )
            # async slicing reports from the slicer's thread too; where the
            # result is applied shows in the renderer's debug line
            applied: list[int] = []

            class Recorder(logging.Handler):
                def emit(self, record: logging.LogRecord) -> None:
                    if '_apply_slice_ready' in record.getMessage():
                        applied.append(record.thread)

            logger = logging.getLogger('napari_lite')
            recorder, level = Recorder(), logger.level
            logger.addHandler(recorder)
            logger.setLevel(logging.DEBUG)

            def subshell() -> None:
                rfb.handle_event(pointer('pointer_enter', 10, 10))
                results['frame'] = rfb.get_frame()
                window._sliders_by_axis[0].value = 2
                window.backend._on_slice_ready(SimpleNamespace(value={}))

            try:
                worker = threading.Thread(target=subshell)
                worker.start()
                worker.join()
                await asyncio.sleep(0.3)  # the loop runs what was handed over
            finally:
                logger.removeHandler(recorder)
                logger.setLevel(level)
            assert handled == {main}
            assert results['frame'] is None  # drawn on the viewer's thread
            assert sent and sent[0][0] == main
            assert viewer.mouse_over_canvas
            assert viewer.dims.current_step[0] == 2
            assert applied == [main]
        finally:
            viewer.close()

    asyncio.run(scenario())


def test_ipython_running_qt(make_notebook_viewer, qtbot, monkeypatch) -> None:
    """With IPython's Qt loop on (``%gui qt``) the kernel's asyncio loop
    waits for the next message to the main shell: calls handed over from
    another thread, and the draws jupyter_rfb asks for, go through Qt."""
    from napari_lite._vispy import _jupyter
    from napari_lite.utils import _owner_thread

    monkeypatch.setattr(_owner_thread, 'ipython_runs_qt', lambda: True)
    monkeypatch.setattr(_jupyter, 'ipython_runs_qt', lambda: True)
    main = threading.get_ident()

    owner = _owner_thread.OwnerThread()  # no asyncio loop here at all
    ran = []
    worker = threading.Thread(
        target=owner.call, args=(lambda: ran.append(threading.get_ident()),)
    )
    worker.start()
    worker.join()
    qtbot.waitUntil(lambda: bool(ran), timeout=3000)
    assert ran == [main]

    viewer = make_notebook_viewer()
    rfb = viewer.window.backend.native
    rfb._has_visible_views = True  # the browser shows it
    drawn = []
    capture = viewer.window.backend.capture

    def record():
        drawn.append(threading.get_ident())
        return capture()

    viewer.window.backend.capture = record
    rfb.request_draw()  # no asyncio loop to schedule it: Qt draws it
    qtbot.waitUntil(lambda: bool(drawn), timeout=3000)
    assert drawn == [main]


def test_cursor(make_notebook_viewer) -> None:
    viewer = make_notebook_viewer()
    rfb = viewer.window.backend.native
    brush = viewer.canvas.overlays._brush_circle
    points = viewer.add_points([[2, 2]])
    points.mode = 'add'
    assert rfb.cursor == 'crosshair'
    labels = viewer.add_labels(np.zeros((64, 64), np.uint8))
    viewer.camera.zoom = 2  # brush sizes are data pixels times the zoom
    labels.mode = 'paint'
    labels.brush_size = 20
    assert rfb.cursor == 'none'  # napari draws the brush circle itself
    assert brush.visible
    labels.brush_size = 2  # 4 screen pixels: too small to see as a circle
    assert rfb.cursor == 'crosshair'
    labels.mode = 'pan_zoom'
    assert rfb.cursor == 'default'
    assert not brush.visible


def test_screenshots(make_notebook_viewer, tmp_path) -> None:
    from napari_lite.utils import nbscreenshot

    viewer = make_notebook_viewer()
    viewer.add_image(np.zeros((32, 48)))
    assert viewer.screenshot().shape == (600, 800, 4)
    # the rest of the window is the browser's: the canvas either way
    assert viewer.screenshot(canvas_only=False).shape == (600, 800, 4)
    assert viewer.export_figure().shape == (32, 48, 4)
    path = tmp_path / 'shot.png'
    viewer.window.screenshot(str(path), canvas_only=True)
    assert path.exists()
    assert nbscreenshot(viewer)._repr_png_()[:8] == b'\x89PNG\r\n\x1a\n'
    with pytest.raises(NotImplementedError, match='clipboard'):
        viewer.window.clipboard()


def test_dock_widgets(make_notebook_viewer) -> None:
    viewer = make_notebook_viewer()
    window = viewer.window
    button = widgets.Button(description='go')
    box = window.add_dock_widget(button, name='tools')
    assert box in window._right_docks.children
    assert window.dock_widgets == {'tools': button}

    class MagicguiLike:
        native = widgets.IntSlider()

    window.add_dock_widget(MagicguiLike(), area='left')
    window.add_dock_widget(widgets.Label('below'), name='note', area='bottom')
    assert len(window._left_docks.children) == 1
    assert len(window._bottom_docks.children) == 1
    window.remove_dock_widget(button)
    assert 'tools' not in window.dock_widgets
    window.remove_dock_widget('note')
    window.remove_dock_widget('all')
    assert window.dock_widgets == {}
    with pytest.raises(TypeError, match='ipywidgets'):
        window.add_dock_widget(object())
    with pytest.raises(ValueError, match='area must be'):
        window.add_dock_widget(widgets.Label(), area='middle')
    with pytest.raises(LookupError):
        window.remove_dock_widget('missing')


def test_geometry_close_and_current_viewer(make_notebook_viewer) -> None:
    from napari_lite import current_viewer
    from napari_lite.backends.jupyter import JupyterWindow

    first = make_notebook_viewer()
    second = make_notebook_viewer()
    assert current_viewer() is second
    first.window.activate()
    assert current_viewer() is first
    first.window.resize(300, 200)
    assert first.window.geometry() == (0, 0, 300, 200)
    window = first.window
    rfb = window.backend.native
    first.close()
    assert all(ref() is not window for ref in JupyterWindow._instances)
    assert window.widget.comm is None  # closed in the browser too
    assert rfb.comm is None
    assert current_viewer() is second
    # the model no longer reaches the closed window, nor its canvas
    first.title = 'after close'
    assert 'after close' not in window._title.value
    first.add_image(np.zeros((8, 8)))
    first.layers.clear()


def test_messages_handled_on_the_main_shell(make_notebook_viewer) -> None:
    """ipykernel 7 routes a widget's messages by its comm; the viewer's
    widgets, and the ones docked next to it, stay on the main shell."""
    viewer = make_notebook_viewer()
    viewer.add_image(np.zeros((3, 8, 8)))
    window = viewer.window
    button = widgets.Button(description='go')
    window.add_dock_widget(widgets.VBox([button]), name='tools')

    def routed_to(widget):
        route = widget.comm._reply_subshell_for
        return route({}, 'a-subshell')

    for widget in (
        window.backend.native,  # the canvas
        window._reset,
        window._sliders_by_axis[0],
        next(iter(window._visible_boxes.values())),
        button,  # inside a docked box
    ):
        assert routed_to(widget) is None  # None: the main shell


def test_screenshots_from_another_thread() -> None:
    """A screenshot asked on another thread (a widget callback on a
    subshell) is drawn on the viewer's thread; without a loop to hand it
    to, it is refused with a clear error instead of Qt ending the
    process."""
    pytest.importorskip('qtpy')
    from napari_lite import Viewer
    from napari_lite._vispy._qt_optional import use_vispy_app

    use_vispy_app('qt')

    async def scenario() -> None:
        viewer = Viewer(gui='jupyter', show=False)
        try:
            viewer.add_image(np.zeros((16, 16)))
            shot = await asyncio.to_thread(viewer.screenshot)
            assert shot.shape == (600, 800, 4)
        finally:
            viewer.close()

    asyncio.run(scenario())

    viewer = Viewer(gui='jupyter', show=False)  # no loop: nothing to hand to
    try:
        errors = []

        def worker() -> None:
            try:
                viewer.screenshot()
            except RuntimeError as e:
                errors.append(str(e))

        thread = threading.Thread(target=worker)
        thread.start()
        thread.join()
        assert errors and 'thread that made the viewer' in errors[0]
    finally:
        viewer.close()


def test_gui_from_the_environment(qapp, monkeypatch) -> None:
    from napari_lite import Viewer
    from napari_lite._vispy._qt_optional import use_vispy_app
    from napari_lite.backends.jupyter import JupyterWindow

    use_vispy_app('qt')
    monkeypatch.setenv(backends.GUI_ENVIRONMENT_VARIABLE, 'jupyter')
    viewer = Viewer(show=False)
    try:
        assert isinstance(viewer.window, JupyterWindow)
    finally:
        viewer.close()


def test_a_renderer_without_a_notebook_widget(qapp) -> None:
    from napari_lite import Viewer

    closed = []

    class NoWidget:
        def __init__(self, viewer, *, gui=None, parent=None):
            self.native = None

        def screenshot(self, **kwargs):
            return np.zeros((1, 1, 4), np.uint8)

        def key_event(self, event, *, release=False):
            pass

        def close(self):
            closed.append(True)

    with pytest.raises(TypeError, match='no notebook widget'):
        Viewer(gui='jupyter', renderer=NoWidget, show=False)
    assert closed == [True]


WITHOUT_QT = textwrap.dedent(
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

    import importlib.util
    import numpy as np
    from napari_lite import Viewer

    viewer = Viewer(gui='jupyter', show=False)
    rgb = np.zeros((32, 48, 3), np.uint8)
    rgb[..., 0] = 255
    viewer.add_image(rgb)
    # text without Qt needs freetype-py, the headless extra
    text = importlib.util.find_spec('freetype') is not None
    viewer.add_points(
        [[16, 24]], size=4, face_color='blue',
        **({'text': 'a point'} if text else {}),
    )
    rfb = viewer.window.backend.native
    frame = rfb.get_frame()
    rfb.handle_event({'type': 'resize', 'width': 200, 'height': 100, 'ratio': 1})
    canvas_size = viewer.canvas.size  # the model follows the browser
    small = rfb.get_frame()
    # after a frame, a change asks the browser for the next one
    requests = []
    rfb.request_draw = lambda: requests.append(1)
    viewer.camera.zoom *= 2
    viewer.close()
    print(json.dumps({
        'app': viewer.window.backend.app_name,
        'frame': list(frame.shape),
        'small': list(small.shape),
        'canvas_size': list(canvas_size),
        'requests': len(requests),
        'centre': frame[frame.shape[0] // 2, frame.shape[1] // 2].tolist(),
        'small_centre': small[50, 100].tolist(),
        'qt_loaded': any(m.split('.')[0] in BLOCKED for m in sys.modules),
    }))
    """
)


def test_notebook_viewer_without_qt_in_the_process() -> None:
    """Linux with EGL: the notebook viewer draws with Qt blocked.  Skipped
    where vispy has no offscreen application, unless
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
    assert info['app'] == 'egl'
    assert not info['qt_loaded']
    assert info['frame'] == [600, 800, 4]
    assert info['small'] == [100, 200, 4]
    assert info['canvas_size'] == [100, 200]
    assert info['requests'] > 0
    assert tuple(info['centre'])[:3] != (0, 0, 0)
    assert tuple(info['small_centre'])[:3] != (0, 0, 0)  # laid out anew


def test_shortcuts_and_open_files_in_the_notebook(
    make_notebook_viewer,
) -> None:
    """Ctrl+Alt+/ and Ctrl+O have no Qt dialog to open in a notebook: the
    key bindings dock as a table, files come in through an upload box."""
    import io
    from datetime import datetime

    import imageio.v3 as iio

    viewer = make_notebook_viewer()
    window = viewer.window
    rfb = window.backend.native
    rfb.get_frame()
    for kind in ('key_down', 'key_up'):
        rfb.handle_event(
            {'type': kind, 'key': '/', 'modifiers': ['Control', 'Alt']}
        )
    table = window.dock_widgets['Key bindings']
    assert isinstance(table, widgets.HTML)
    assert 'Toggle 2D/3D view' in table.value
    window.show_shortcuts()  # again: gone
    assert 'Key bindings' not in window.dock_widgets

    for kind in ('key_down', 'key_up'):
        rfb.handle_event({'type': kind, 'key': 'o', 'modifiers': ['Control']})
    upload = window.dock_widgets['Open files']
    assert isinstance(upload, widgets.FileUpload)
    red = np.zeros((8, 12, 3), np.uint8)
    red[..., 0] = 255
    buffer = io.BytesIO()
    iio.imwrite(buffer, red, extension='.png')
    png = buffer.getvalue()
    upload.value = (
        {
            'name': 'red.png',
            'type': 'image/png',
            'size': len(png),
            'content': memoryview(png),
            'last_modified': datetime.now(UTC),
        },
    )
    assert [layer.name for layer in viewer.layers] == ['red']
    assert viewer.layers[0].data.shape == (8, 12, 3)
    assert upload.value == ()  # ready for the next file
    window.open_files()  # again: gone
    assert 'Open files' not in window.dock_widgets
