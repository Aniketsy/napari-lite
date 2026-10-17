# napari-lite: own code
"""napari-lite must import with napari blocked and without the heavy
application dependencies.

Each check runs in a fresh interpreter: a meta-path finder makes every
``import napari`` fail, the module under test is imported, and the set of
loaded top-level packages is reported back as JSON.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap

import pytest

# Packages that must never be loaded by importing napari-lite's core.
FORBIDDEN = {'napari', 'npe2', 'magicgui', 'lxml', 'app_model'}

# Imported one by one in a clean interpreter.
MODULES = [
    'napari_lite',
    'napari_lite.utils',
    'napari_lite.settings',
    'napari_lite.utils.theme',
    'napari_lite.utils.action_manager',
    'napari_lite.components',
    'napari_lite.layers',
    'napari_lite._vispy',
    'napari_lite._qt.widgets.qt_dims',
    'napari_lite._qt.qt_event_loop',
]

BLOCKED = {'napari'}

SCRIPT = textwrap.dedent(
    """
    import importlib.abc
    import json
    import os
    import sys
    import time

    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    BLOCKED = set(json.loads(sys.argv[2]))

    class Block(importlib.abc.MetaPathFinder):
        def find_spec(self, name, path=None, target=None):
            if name.split('.')[0] in BLOCKED:
                raise ImportError(f'{name} is blocked in this test')
            return None

    sys.meta_path.insert(0, Block())
    before = set(sys.modules)
    start = time.perf_counter()
    importlib.import_module(sys.argv[1])
    elapsed = time.perf_counter() - start
    loaded = {m.split('.')[0] for m in set(sys.modules) - before}
    print(json.dumps({'loaded': sorted(loaded), 'seconds': elapsed}))
    """
)


def import_in_subprocess(module: str, blocked: set[str] = BLOCKED) -> dict:
    proc = subprocess.run(
        [sys.executable, '-c', SCRIPT, module, json.dumps(sorted(blocked))],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert proc.returncode == 0, (
        f'import {module} failed with napari blocked:\n{proc.stderr}'
    )
    return json.loads(proc.stdout.strip().splitlines()[-1])


@pytest.mark.parametrize('module', MODULES)
def test_imports_without_napari(module: str) -> None:
    info = import_in_subprocess(module)
    found = FORBIDDEN & set(info['loaded'])
    assert not found, f'import {module} loaded forbidden packages: {found}'


FIRST_IMAGE = textwrap.dedent(
    """
    import importlib.abc
    import json
    import sys
    import traceback

    import numpy as np

    BLOCKED = set(json.loads(sys.argv[2]))
    WATCHED = set(json.loads(sys.argv[3]))
    direct = {}

    class Spy(importlib.abc.MetaPathFinder):
        # Who asks for a watched package first?  Walking the stack from the
        # import statement outwards, if a napari_lite file comes before any
        # third-party file, napari-lite's own code imported it.
        def find_spec(self, name, path=None, target=None):
            top = name.split('.')[0]
            if top in BLOCKED:
                raise ImportError(f'{name} is blocked in this test')
            if top in WATCHED and top not in direct:
                for frame in reversed(traceback.extract_stack()[:-1]):
                    file = frame.filename.replace(chr(92), '/')
                    if 'importlib' in file or '<frozen' in file:
                        continue
                    if '/napari_lite/' in file:
                        direct[top] = f'{file.rsplit("/", 1)[-1]}:{frame.lineno}'
                    break
                direct.setdefault(top, None)
            return None

    sys.meta_path.insert(0, Spy())
    from napari_lite.components import ViewerModel

    viewer = ViewerModel()
    viewer.add_image(np.zeros((4, 8, 8)))
    loaded = {m.split('.')[0] for m in sys.modules}
    print(json.dumps({'loaded': sorted(loaded), 'direct': direct}))
    """
)

# Needed only for dask data (dask, cachey, psutil) or Labels colors and
# Shapes masks (skimage): issue 18.  Dependencies may import them for their
# own reasons (pint imports dask when it is installed); napari-lite's own
# modules must not, before a dask array or a Labels layer shows up.
ON_FIRST_USE = {'dask', 'cachey', 'psutil', 'skimage'}


def test_heavy_dependencies_wait_for_first_use() -> None:
    proc = subprocess.run(
        [
            sys.executable,
            '-c',
            FIRST_IMAGE,
            'unused',
            json.dumps(sorted(BLOCKED)),
            json.dumps(sorted(ON_FIRST_USE)),
        ],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    info = json.loads(proc.stdout.strip().splitlines()[-1])
    assert not (FORBIDDEN & set(info['loaded'])), FORBIDDEN & set(
        info['loaded']
    )
    direct = {k: v for k, v in info['direct'].items() if v}
    assert not direct, f'imported by napari-lite before first use: {direct}'


def test_bare_import_is_light() -> None:
    """``import napari_lite`` loads no Qt, vispy or pydantic (issue 03)."""
    info = import_in_subprocess('napari_lite')
    heavy = {'qtpy', 'PyQt6', 'PySide6', 'vispy', 'pydantic', 'numpy'}
    found = heavy & set(info['loaded'])
    assert not found, f'import napari_lite eagerly loaded {found}'
