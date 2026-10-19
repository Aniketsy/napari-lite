# napari-lite: own code
"""napari-lite: the napari viewer core without the application.

``import napari_lite`` is cheap on purpose: every public name below is
loaded on first use through ``lazy_loader``, so Qt, vispy and pydantic are
imported only when a viewer, a layer or a canvas is actually created.

Most of the code in this package is copied from napari (BSD-3) by
``tools/vendor.py``; see VENDORED.json and SYNC.md.
"""

import os as _os
import sys as _sys

from lazy_loader import attach as _attach

from napari_lite._wayland_fix import _fix_wayland_opengl

# Allows pydata/sparse arrays as layer data (same as napari).
_os.environ.setdefault('SPARSE_AUTO_DENSIFY', '1')

# Must run before any module that imports vispy/PyOpenGL: PyOpenGL caches
# its platform at first import.  Cheap: returns at once off Linux+Wayland.
_fix_wayland_opengl()

# numpy<2 wheels crash on Apple Silicon when used from several threads.
# napari applies the OpenBLAS workaround at import; napari-lite only where
# it matters (Apple Silicon with numpy 1.x), so importing napari_lite does
# not import numpy anywhere else.
if _sys.platform == 'darwin':  # pragma: no cover
    import platform as _platform
    from importlib.metadata import version as _version

    if (
        _platform.machine() == 'arm64'
        and int(_version('numpy').split('.')[0]) < 2
    ):
        from napari_lite._check_numpy_version import (
            limit_numpy1x_threads_on_macos_arm,
        )

        limit_numpy1x_threads_on_macos_arm()
        del limit_numpy1x_threads_on_macos_arm
    del _platform, _version

del _fix_wayland_opengl

# Public submodules, imported on first attribute access.
_submodules = [
    'components',
    'layers',
    'qt',
    'types',
    'utils',
    'view',
    'viewer',
]

# Public names and the submodule each one comes from.  ``Viewer``,
# ``imshow`` and ``run`` arrive with milestone M2 (issues 10 and 13);
# until then accessing them raises ModuleNotFoundError.
_submod_attrs = {
    '_version': ['__version__'],
    '_qt.qt_event_loop': ['run'],
    'view_layers': ['imshow'],
    'viewer': ['Viewer', 'current_viewer'],
}

__getattr__, __dir__, __all__ = _attach(
    __name__, submodules=_submodules, submod_attrs=_submod_attrs
)
del _attach, _os, _sys
