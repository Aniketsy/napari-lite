# napari-lite: own code
"""PyOpenGL for vispy's egl application (issue 5).

napari makes its GL calls through PyOpenGL (vispy's ``gl+`` backend), and
PyOpenGL settles its platform once, when it is first imported: on Linux
GLX, unless ``PYOPENGL_PLATFORM`` or a Wayland session says otherwise.
vispy's egl application, which draws the headless and notebook viewers on
Linux without Qt, makes an EGL context, and PyOpenGL on GLX finds no
current context there: it refuses every function it looks up by name
(``glGenFramebuffers``, ...).  So the two go together:

- ``prefer_egl`` runs before the vispy renderer is first imported for a
  viewer without a Qt window: where vispy's egl application loads and
  nothing has settled PyOpenGL's platform yet, it sets
  ``PYOPENGL_PLATFORM=egl``, for this process and the ones it starts.
- ``pyopengl_on_egl`` says whether PyOpenGL draws through EGL; vispy's
  egl application is chosen only then (``_vispy/_qt_optional.py``),
  otherwise Qt draws into a widget kept off the screen.
"""

from __future__ import annotations

import os
import sys

__all__ = ['PLATFORM_VARIABLE', 'prefer_egl', 'pyopengl_on_egl']

PLATFORM_VARIABLE = 'PYOPENGL_PLATFORM'


def pyopengl_on_egl() -> bool:
    """Whether PyOpenGL makes its GL calls through EGL in this process.
    Asking imports it, which settles its platform, as napari's first GL
    call would."""
    try:
        from OpenGL import platform
    except ImportError:
        return False
    return type(platform.PLATFORM).__name__ == 'EGLPlatform'


def _vispy_app_chosen() -> bool:
    """Whether vispy's application is selected already: it then decides
    how this process draws."""
    default_app = sys.modules.get('vispy.app._default_app')
    return getattr(default_app, 'default_app', None) is not None


def _egl_app_loads() -> bool:
    """Whether vispy's egl application loads here (Linux with EGL).  The
    check imports vispy's EGL binding, not PyOpenGL."""
    try:
        from vispy.app.backends import _egl
    except Exception:  # any failure means it does not load here
        return False
    return bool(getattr(_egl, 'available', False))


def prefer_egl() -> None:
    """Ready PyOpenGL for vispy's egl application, before the vispy
    renderer is first imported for a viewer without a Qt window: on Linux,
    where that application loads, unless PyOpenGL is imported already,
    the environment names its platform, or vispy's application is chosen
    (by a Qt window, say)."""
    if not sys.platform.startswith('linux'):
        return
    if 'OpenGL.platform' in sys.modules or os.environ.get(PLATFORM_VARIABLE):
        return
    if _vispy_app_chosen() or not _egl_app_loads():
        return
    os.environ[PLATFORM_VARIABLE] = 'egl'
