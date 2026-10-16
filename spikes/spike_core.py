# napari-lite: own code
"""Smoke check: the core works with napari blocked.

    python spikes/spike_core.py

Blocks every ``import napari``, imports ``napari_lite.components`` (timing
it), builds a ``ViewerModel`` with one layer of each of the seven types,
imports the dims widget, and prints which forbidden packages (napari,
npe2, magicgui, lxml) ended up in ``sys.modules``.  Exit code 1 on any
failure.  ``STUBS`` is False: napari-lite's own shims are in place; set it
to True to get throwaway stand-ins for the app modules instead (useful
when a resync adds a new crossing and the shim does not exist yet).
"""

from __future__ import annotations

import importlib.abc
import sys
import time
import types

STUBS = False
FORBIDDEN = {'napari', 'npe2', 'magicgui', 'lxml'}
APP_MODULES = [
    'napari_lite.settings',
    'napari_lite.utils.theme',
    'napari_lite.utils.action_manager',
    'napari_lite.plugins',
    'napari_lite.utils._magicgui',
    'napari_lite._app_model',
]


class BlockNapari(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name.split('.')[0] == 'napari':
            raise ImportError(
                f'{name} is blocked: napari-lite must not need it'
            )
        return None


def install_stubs() -> None:
    """Replace the app modules by empty modules that return None for every
    attribute (a stand-in, only to measure what the core needs)."""

    class Stub(types.ModuleType):
        def __getattr__(self, name):
            if name.startswith('__'):
                raise AttributeError(name)
            return lambda *a, **k: None

    for name in APP_MODULES:
        sys.modules[name] = Stub(name)


def main() -> int:
    sys.meta_path.insert(0, BlockNapari())
    if STUBS:
        install_stubs()

    t0 = time.perf_counter()
    import numpy as np

    t_numpy = time.perf_counter()
    import napari_lite.components  # noqa: F401

    t_components = time.perf_counter()
    from napari_lite.components import ViewerModel

    viewer = ViewerModel()
    viewer.add_image(np.zeros((4, 8, 8)))
    viewer.add_labels(np.zeros((8, 8), dtype=np.uint8))
    viewer.add_points(np.zeros((3, 2)))
    viewer.add_shapes(
        [np.array([[0, 0], [1, 1], [2, 0]])], shape_type='polygon'
    )
    viewer.add_vectors(np.zeros((2, 2, 2)))
    viewer.add_surface((np.zeros((3, 2)), np.array([[0, 1, 2]])))
    viewer.add_tracks(np.array([[0, 0, 0, 0], [0, 1, 1, 1]]))
    t_layers = time.perf_counter()
    from napari_lite._qt.widgets.qt_dims import QtDims  # noqa: F401

    t_qt = time.perf_counter()

    print(f'import numpy                 {t_numpy - t0:6.2f} s')
    print(f'import napari_lite.components {t_components - t_numpy:6.2f} s')
    print(f'ViewerModel + 7 layers        {t_layers - t_components:6.2f} s')
    print(f'import QtDims                 {t_qt - t_layers:6.2f} s')
    print('layers:', [type(layer).__name__ for layer in viewer.layers])
    loaded = sorted(m for m in sys.modules if m.split('.')[0] in FORBIDDEN)
    if loaded:
        print('FORBIDDEN packages loaded:', loaded)
        return 1
    print('no forbidden package loaded')
    return 0


if __name__ == '__main__':
    sys.exit(main())
