# napari-lite: own code
"""pytest configuration for the copied napari tests.

napari's root ``conftest.py`` and its ``napari.utils._testsupport``
pytest plugin provide the fixtures the copied tests use.  This file ports
the ones napari-lite can satisfy and skips, with a reason, the tests that
need the application: a ``Viewer`` with a window (issue 13), plugins, or
app-model.  The Qt leak detectors (dangling threads, timers, widgets) are
not ported yet.
"""

from __future__ import annotations

import inspect
import logging
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from multiprocessing.pool import ThreadPool
from typing import TYPE_CHECKING, Literal, TypedDict
from unittest.mock import MagicMock

import numpy as np
import pytest

from napari_lite._app_model._app import NoAppModel
from napari_lite.components import LayerList
from napari_lite.layers import Image, Labels, Points, Shapes, Vectors

if TYPE_CHECKING:
    from collections.abc import Callable

    from napari_lite.components import ViewerModel

# tests that cannot run without the application

NEEDS_VIEWER = 'needs napari_lite.Viewer with a window (issue 13)'
NEEDS_PLUGINS = 'needs npe2 plugins (napari-lite has none)'
NEEDS_APP_MODEL = 'needs app-model (napari-lite has none)'
NEEDS_INFO = 'needs napari.utils.info (application feature)'
NEEDS_MENUS = 'needs menus (napari-lite has none)'

# names in a test's source that mean napari's application side
_NOT_IN_LITE = {
    'get_app_model': NEEDS_APP_MODEL,
    'window_menu': NEEDS_MENUS,
}

# test modules that are not run (relative to this directory)
collect_ignore = [
    '_qt/_tests/test_open_file.py',  # plugins
    'utils/_tests/test_info.py',  # utils.info
    # asserts napari's wording of the Qt version error; _qt/__init__.py is
    # own code with its own message
    '_qt/_tests/test_qt_version_check.py',
    # npe2 theme plugins and napari's platform directories; utils/theme.py
    # and utils/_platformdirs.py are own code
    'utils/_tests/test_theme.py',
    'utils/_tests/test_appdirs.py',
]


def _skip_fixture(reason: str):
    @pytest.fixture
    def _fixture():
        pytest.skip(reason)

    return _fixture


qt_viewer = _skip_fixture("needs napari's QtViewer")
builtins = _skip_fixture(NEEDS_PLUGINS)
tmp_plugin = _skip_fixture(NEEDS_PLUGINS)
napari_svg_name = _skip_fixture(NEEDS_PLUGINS)
mock_app_model = _skip_fixture(NEEDS_APP_MODEL)


@pytest.fixture
def make_napari_viewer(qtbot, request):
    """Create ``Viewer``s that are closed and checked for leaks after the test
    (ported from napari's ``_testsupport.py``, without the plugin and
    app-model parts).  Takes the arguments of ``napari_lite.Viewer``;
    ``show`` defaults to False."""
    import gc
    from weakref import WeakSet

    from napari_lite import Viewer
    from napari_lite.qt import QtCanvas

    gc.collect(1)
    leaked_before = len(QtCanvas._instances)
    QtCanvas._instances.clear()
    assert leaked_before == 0, (
        'A QtCanvas of a previous test was not cleaned up'
    )

    viewers: WeakSet = WeakSet()
    request.node._viewer_weak_set = viewers

    def actual_factory(
        *model_args, ViewerClass=Viewer, strict_qt=None, **model_kwargs
    ):
        model_kwargs['show'] = model_kwargs.pop('show', False)
        model_kwargs.pop('show_welcome_screen', None)
        viewer = ViewerClass(*model_args, **model_kwargs)
        viewers.add(viewer)
        if model_kwargs['show']:
            qtbot.wait_exposed(viewer.window._qt_window, timeout=5000)
        return viewer

    yield actual_factory

    for viewer in list(viewers):
        with suppress(AttributeError, RuntimeError):
            viewer.close()
    gc.collect(1)
    if (
        getattr(request.node, 'rep_call', None)
        and request.node.rep_call.failed
    ):
        QtCanvas._instances.clear()  # a failed test may hold references
    leaked = len(QtCanvas._instances)
    QtCanvas._instances.clear()
    assert leaked == 0, 'a QtCanvas leaked from this test'


@pytest.fixture
def make_napari_viewer_proxy(make_napari_viewer, monkeypatch):
    """``make_napari_viewer`` returning viewers wrapped in PublicOnlyProxy."""
    from napari_lite.utils._proxies import PublicOnlyProxy

    proxies = []

    def actual_factory(*model_args, ensure_main_thread=True, **model_kwargs):
        monkeypatch.setenv(
            'NAPARI_ENSURE_PLUGIN_MAIN_THREAD', str(ensure_main_thread)
        )
        viewer = make_napari_viewer(*model_args, **model_kwargs)
        proxies.append(PublicOnlyProxy(viewer))
        return proxies[-1]

    proxies.clear()
    return actual_factory


# data fixtures (from napari's conftest.py)


@pytest.fixture
def layer_data_and_types():
    """Some image and points layers, their LayerData, types and filenames."""
    layers = [
        Image(np.random.rand(20, 20), name='ex_img'),
        Image(np.random.rand(20, 20)),
        Points(np.random.rand(20, 2), name='ex_pts'),
        Points(
            np.random.rand(20, 2), properties={'values': np.random.rand(20)}
        ),
    ]
    extensions = ['.tif', '.tif', '.csv', '.csv']
    layer_data = [layer.as_layer_data_tuple() for layer in layers]
    layer_types = [layer._type_string for layer in layers]
    filenames = [
        layer.name + e for layer, e in zip(layers, extensions, strict=False)
    ]
    return layers, layer_data, layer_types, filenames


@pytest.fixture
def surface_data() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    data = np.array([[0, 0], [0, 20], [10, 0], [10, 10]], dtype=np.float32)
    faces = np.array([[0, 1, 2], [1, 2, 3]], dtype=np.int32)
    values = np.linspace(0, 1, len(data), dtype=np.float32)
    return (data, faces, values)


class TrackDataDict(TypedDict):
    data: np.ndarray
    properties: dict[Literal['track_id', 'time', 'speed'], list]


@pytest.fixture
def tracks_data() -> TrackDataDict:
    data = np.array(
        [[0, 0, 0, 0], [0, 1, 0, 20], [1, 0, 10, 0], [1, 1, 10, 10]],
        dtype=np.float32,
    )
    properties: dict[Literal['track_id', 'time', 'speed'], list[int]] = {
        'track_id': [0, 0, 1, 1],
        'time': [0, 1, 0, 1],
        'speed': [50, 30, 20, 10],
    }
    return {'data': data, 'properties': properties}


@pytest.fixture
def vectors_data() -> np.ndarray:
    return np.array([[[0, 0], [0, 20]], [[10, 0], [10, 10]]], dtype=np.float32)


@pytest.fixture(
    params=[
        'image',
        'labels',
        'points',
        'shapes',
        'shapes-rectangles',
        'vectors',
    ]
)
def layer(request):
    """Parameterized fixture that supplies a layer for testing."""
    np.random.seed(0)
    if request.param == 'image':
        data = np.random.rand(20, 20)
        return Image(data)
    if request.param == 'labels':
        data = np.random.randint(10, size=(20, 20))
        return Labels(data)
    if request.param == 'points':
        data = np.random.rand(20, 2)
        return Points(data)
    if request.param == 'shapes':
        data = [
            np.random.rand(2, 2),
            np.random.rand(2, 2),
            np.random.rand(6, 2),
            np.random.rand(6, 2),
            np.random.rand(2, 2),
        ]
        shape_type = ['ellipse', 'line', 'path', 'polygon', 'rectangle']
        return Shapes(data, shape_type=shape_type)
    if request.param == 'shapes-rectangles':
        data = np.random.rand(7, 4, 2)
        return Shapes(data)
    if request.param == 'vectors':
        data = np.random.rand(20, 2, 2)
        return Vectors(data)

    return None


@pytest.fixture
def layers() -> LayerList:
    """A layer list with one layer of each of five types."""
    np.random.seed(0)
    list_of_layers = [
        Image(np.random.rand(20, 20)),
        Labels(np.random.randint(10, size=(20, 2))),
        Points(np.random.rand(20, 2)),
        Shapes(np.random.rand(10, 2, 2)),
        Vectors(np.random.rand(10, 2, 2)),
    ]
    return LayerList(list_of_layers)


@pytest.fixture
def viewer_model() -> ViewerModel:
    from napari_lite.components import ViewerModel

    return ViewerModel()


@pytest.fixture
def single_threaded_executor():
    executor = ThreadPoolExecutor(max_workers=1)
    yield executor
    executor.shutdown()


@pytest.fixture
def MouseEvent():
    """A dataclass for simulating vispy mouse events."""

    @dataclass
    class Event:
        type: str
        position: tuple[float]
        is_dragging: bool = False
        dims_displayed: tuple[int] = (0, 1)
        dims_point: list[float] = None
        view_direction: list[int] = None
        pos: list[int] = (0, 0)
        button: int = None
        handled: bool = False

    return Event


@pytest.fixture
def mock_qt_method(monkeypatch) -> Callable[..., MagicMock]:
    """Mock a method of a Qt object through a plain function.

    Since PySide6 6.10, mocking Qt methods with a MagicMock directly
    segfaults; wrapping the mock in a function avoids that.
    """

    def _mock_fun(obj: str | object, method: str | None = None) -> MagicMock:
        mock = MagicMock()

        def _mocked_method(_self, *args, **kwargs):
            return mock(*args, **kwargs)

        if method is None:
            monkeypatch.setattr(obj, _mocked_method)
        else:
            monkeypatch.setattr(obj, method, _mocked_method)
        return mock

    return _mock_fun


@pytest.fixture
def mock_qt_method_ctx(monkeypatch, qtbot):
    """Context-manager form of ``mock_qt_method``; see napari's conftest."""
    from qtpy.QtWidgets import QWidget

    @contextmanager
    def _mock_fun(obj: str | object, method: str | None = None):
        mock = MagicMock()

        def _mocked_method(*args, **kwargs):
            if (
                len(args) > 0
                and isinstance(args[0], QWidget)
                and args[0].parent() is None
            ):
                qtbot.add_widget(args[0])
                args = args[1:]

            return mock(*args, **kwargs)

        with monkeypatch.context() as m:
            if method is None:
                m.setattr(obj, _mocked_method)
            else:
                m.setattr(obj, method, _mocked_method)
            yield mock

    return _mock_fun


# test hygiene (autouse), from napari's conftest.py and _testsupport.py


@pytest.fixture(autouse=True)
def _fresh_settings() -> None:
    """Every test starts from default settings."""
    from napari_lite import settings

    settings._SETTINGS = None
    yield
    settings._SETTINGS = None


@pytest.fixture(autouse=True)
def _auto_shutdown_dask_threadworkers():
    """Shut down dask's thread pool after each test (dask is still a
    dependency until issue 18)."""
    try:
        import dask.threaded
    except ImportError:
        yield
        return
    assert dask.threaded.default_pool is None
    try:
        yield
    finally:
        if isinstance(dask.threaded.default_pool, ThreadPool):
            dask.threaded.default_pool.close()
            dask.threaded.default_pool.join()
        elif dask.threaded.default_pool:
            dask.threaded.default_pool.shutdown()
        dask.threaded.default_pool = None


@pytest.fixture(autouse=True)
def _prevent_thread(request, monkeypatch) -> None:
    """The dims animation thread may only start through the qt_dims fixture."""
    if 'allow_animation_thread' in request.keywords:
        return
    if 'qt_dims' in request.fixturenames or 'ref_view' in request.fixturenames:
        return
    if 'qtbot' not in request.fixturenames:
        return

    from napari_lite._qt.widgets.qt_dims_slider import AnimationThread

    def fake_start(self):
        raise RuntimeError(
            'QtDims animation thread should not be started outside of tests '
            "without using the 'qt_dims' fixture."
        )

    monkeypatch.setattr(AnimationThread, 'start', fake_start)


@pytest.fixture(autouse=True)
def _clean_themes():
    from napari_lite.utils import theme

    themes = set(theme.available_themes())
    yield
    for name in theme.available_themes():
        if name not in themes:
            del theme._themes[name]


@pytest.fixture(autouse=True)
def _fix_magic_name(monkeypatch, request) -> None:
    """Let magic_name treat the test file as an internal module."""
    from napari_lite.utils import naming

    monkeypatch.setitem(
        naming.magic_name.__kwdefaults__,
        'path_prefix',
        (naming.ROOT_DIR, str(request.fspath)),
    )


@pytest.fixture(autouse=True)
def _reset_colormaps():
    from napari_lite.utils.colormaps import colormap_utils

    prev = dict(colormap_utils.AVAILABLE_COLORMAPS)
    yield
    colormap_utils.AVAILABLE_COLORMAPS.clear()
    colormap_utils.AVAILABLE_COLORMAPS.update(prev)


class LeakSafeLogRecord(logging.LogRecord):
    """LogRecord that converts args to strings to prevent reference retention."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.args:
            self.args = tuple(
                str(arg) if not isinstance(arg, int | float) else arg
                for arg in self.args
            )


@pytest.fixture(autouse=True, scope='session')
def use_leak_safe_log_records():
    original_record_factory = logging.getLogRecordFactory()
    logging.setLogRecordFactory(LeakSafeLogRecord)
    yield
    logging.setLogRecordFactory(original_record_factory)


def _event_check(instance):
    """Yield one check per public property: the matching event exists."""

    def _prepare_check(name, no_event_) -> Callable[..., None]:
        def check(instance, no_event=no_event_) -> None:
            if name in no_event:
                assert not hasattr(instance.events, name), (
                    f'event {name} defined'
                )
            else:
                assert hasattr(instance.events, name), (
                    f'event {name} not defined'
                )

        return check

    no_event_set = set()
    if isinstance(instance, tuple):
        no_event_set = instance[1]
        instance = instance[0]

    for name, value in instance.__class__.__dict__.items():
        if isinstance(value, property) and name[0] != '_':
            yield _prepare_check(name, no_event_set), instance, name


def pytest_generate_tests(metafunc) -> None:
    """Generate separate test for each test toc check if all events are defined."""
    if 'event_define_check' in metafunc.fixturenames:
        res = []
        ids = []

        for obj in metafunc.cls.get_objects():
            for check, instance, name in _event_check(obj):
                res.append((check, instance))
                ids.append(f'{name}-{instance}')

        metafunc.parametrize('event_define_check,obj', res, ids=ids)


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Expose the report of each phase on the item (used by napari tests)."""
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f'rep_{rep.when}', rep)


def pytest_collection_modifyitems(session, config, items) -> None:
    """Skip the copied tests that call app-model, and run the rest in
    napari's order: utils, layers, components, then the vispy and Qt
    folders (napari's conftest does the same; the suite is tuned for it,
    e.g. timing tests run before Qt tests)."""
    for item in items:
        function = getattr(item, 'function', None)
        try:
            source = inspect.getsource(function) if function else ''
        except (OSError, TypeError):
            source = ''
        for marker, reason in _NOT_IN_LITE.items():
            if marker in source:
                item.add_marker(pytest.mark.skip(reason=reason))
    prefixes = [
        'napari_lite/utils',
        'napari_lite/layers',
        'napari_lite/components',
        'napari_lite/settings',
        'napari_lite/plugins',
        'napari_lite/_vispy',
        'napari_lite/_qt',
        'napari_lite/qt',
    ]
    buckets: list[list] = [[] for _ in prefixes]
    buckets.append([])  # everything else, in collection order
    for item in items:
        path = str(item.fspath).replace(chr(92), '/')
        index = -1
        for i, prefix in enumerate(prefixes):
            if prefix in path:
                index = i
        buckets[index].append(item)
    items[:] = [item for bucket in buckets for item in bucket]


@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item):
    """A copied test that reaches app-model while running is skipped."""
    try:
        return (yield)
    except NoAppModel:
        pytest.skip(NEEDS_APP_MODEL)
    except ModuleNotFoundError as e:
        if e.name == 'app_model':
            pytest.skip(NEEDS_APP_MODEL)
        raise


def pytest_runtest_setup(item) -> None:
    """Tests that use Qt get a qtbot so threads are waited for."""
    if 'qapp' in item.fixturenames and 'qtbot' not in item.fixturenames:
        item.fixturenames.append('qtbot')


with suppress(ImportError):
    # keep IPython from writing its history database during tests
    from IPython.core.history import HistoryManager

    HistoryManager.enabled = False
