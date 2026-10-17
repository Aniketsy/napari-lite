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


def test_bare_import_is_light() -> None:
    """``import napari_lite`` loads no Qt, vispy or pydantic (issue 03)."""
    info = import_in_subprocess('napari_lite')
    heavy = {'qtpy', 'PyQt6', 'PySide6', 'vispy', 'pydantic', 'numpy'}
    found = heavy & set(info['loaded'])
    assert not found, f'import napari_lite eagerly loaded {found}'
