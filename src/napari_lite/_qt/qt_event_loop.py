# napari-lite: own code
"""The Qt application and event loop.

``get_qapp()`` returns the one ``QApplication`` (creating it if needed),
``run()`` starts the event loop, ``quit_app()`` closes napari-lite's
windows.  Compared with napari's module there is no app-model wiring, no
notification dialog, no perf tracing, no theme search paths and no icon.
"""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING
from warnings import warn

from qtpy.QtWidgets import QApplication

from napari_lite._qt.qthreading import wait_for_workers_to_quit
from napari_lite._qt.utils import _maybe_allow_interrupt, use_tabular_numerals
from napari_lite._wayland_fix import _nvidia_driver_loaded
from napari_lite.utils.notifications import (
    notification_manager,
    show_console_notification,
)

if TYPE_CHECKING:
    from IPython import InteractiveShell

__all__ = ['get_qapp', 'quit_app', 'register_theme_icons', 'run']

APP_NAME = 'napari-lite'
ORG_NAME = 'napari-lite'
ORG_DOMAIN = 'napari-lite.local'

# themes whose icons are written and registered as a Qt search path
_theme_icons_registered: set[str] = set()

# store reference to QApplication to prevent garbage collection
_app_ref: QApplication | None = None
_IPYTHON_WAS_HERE_FIRST = 'IPython' in sys.modules


def _version() -> str:
    from napari_lite._version import __version__

    return __version__


def set_app_id(app_id: str | None) -> None:
    """Group napari-lite windows under one taskbar entry on Windows."""
    if os.name == 'nt' and app_id and not getattr(sys, 'frozen', False):
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)


def get_qapp(
    *,
    app_name: str | None = None,
    app_version: str | None = None,
    icon: str | None = None,
    org_name: str | None = None,
    org_domain: str | None = None,
    app_id: str | None = None,
    ipy_interactive: bool | None = None,
    ipython_loop: bool = True,
) -> QApplication:
    """Get or create the Qt QApplication.

    The keyword arguments are applied only when the application is created
    here; when one already exists (for example through IPython's
    ``%gui qt``) they are ignored with a warning.  ``ipy_interactive``
    turns on IPython's Qt event loop integration when running inside an
    interactive IPython session (default: the ``application.ipy_interactive``
    setting).  ``ipython_loop=False`` leaves that integration as it is:
    a canvas drawn off the screen needs no event loop, and in a notebook
    its frames are scheduled on asyncio.
    """
    set_values = {k for k, v in locals().items() if v and k != 'ipython_loop'}
    global _app_ref

    app = QApplication.instance()
    if app:
        set_values.discard('ipy_interactive')
        if set_values:
            warn(
                'QApplication already existed, these arguments to '
                f"'get_qapp' were ignored: {set_values}",
                stacklevel=2,
            )
        if (
            sys.platform == 'linux'
            and app.platformName() == 'wayland'
            and _nvidia_driver_loaded()
        ):
            # A QApplication created before napari-lite was imported (e.g.
            # via IPython's "%gui qt") locks the Qt platform plugin to
            # Wayland before _wayland_fix.py could run.  Gated on Nvidia
            # since that is the only setup the workaround helps.
            warn(
                'A Qt application was already running on the Wayland '
                'platform before napari-lite was imported, so the Wayland '
                'startup workaround could not be applied. If the viewer '
                'fails to launch or throws repeated rendering errors, see '
                'https://napari.org/stable/troubleshooting.html#wayland-and-nvidia '
                'for the workaround.',
                stacklevel=2,
            )
    else:
        argv = sys.argv.copy()
        if sys.platform == 'darwin' and not argv[0].endswith(APP_NAME):
            # the name in the macOS application menu comes from argv[0]
            argv[0] = APP_NAME
        app = QApplication(argv)
        app.setApplicationName(app_name or APP_NAME)
        app.setApplicationVersion(app_version or _version())
        app.setOrganizationName(org_name or ORG_NAME)
        app.setOrganizationDomain(org_domain or ORG_DOMAIN)
        set_app_id(app_id or f'{APP_NAME}.viewer.{_version()}')
        use_tabular_numerals(app)

    if icon and app.windowIcon().isNull():
        from qtpy.QtGui import QIcon

        app.setWindowIcon(QIcon(icon))

    if ipy_interactive is None:
        from napari_lite.settings import get_settings

        ipy_interactive = get_settings().application.ipy_interactive
    if _IPYTHON_WAS_HERE_FIRST and ipython_loop:
        _try_enable_ipython_gui('qt' if ipy_interactive else None)

    if not _app_ref:  # running for first time
        # see docstring of `wait_for_workers_to_quit` for caveats on killing
        # workers at shutdown.
        app.aboutToQuit.connect(wait_for_workers_to_quit)
        notification_manager.notification_ready.connect(
            show_console_notification
        )
        from napari_lite.settings import get_settings

        register_theme_icons(get_settings().appearance.theme)

    _app_ref = app  # prevent garbage collection
    return app


def register_theme_icons(theme_id: str) -> str:
    """Write the icons in the colors of ``theme_id`` (once per napari-lite
    version and color set) and register the directory as the Qt search
    path ``theme_<id>:/`` that napari's stylesheet refers to.

    Returns the directory.  napari writes these icons to its cache
    directory when a theme is registered; napari-lite writes them under
    the temp directory when a Qt application first needs them.
    """
    from qtpy.QtCore import QDir

    from napari_lite._version import __version__
    from napari_lite.resources._icons import (
        ICONS,
        _theme_path,
        build_theme_svgs,
    )
    from napari_lite.utils.theme import get_theme

    path = _theme_path(theme_id)
    if theme_id not in _theme_icons_registered:
        stamp = path / 'napari-lite.txt'
        colors = sorted(get_theme(theme_id).to_rgb_dict().items())
        wanted = f'{__version__} {len(ICONS)} {colors}'
        current = stamp.read_text(encoding='utf-8') if stamp.exists() else ''
        if current != wanted:
            build_theme_svgs(theme_id, 'builtin')
            stamp.write_text(wanted, encoding='utf-8')
        QDir.addSearchPath(f'theme_{theme_id}', str(path))
        _theme_icons_registered.add(theme_id)
    return str(path)


def quit_app() -> None:
    """Close all windows and quit the QApplication if napari-lite started it."""
    from napari_lite import viewer as _viewer

    for v in list(getattr(getattr(_viewer, 'Viewer', None), '_instances', ())):
        v.close()
    QApplication.closeAllWindows()
    if (
        QApplication.applicationName() == APP_NAME
        and not _ipython_has_eventloop()
    ):
        QApplication.quit()


def _ipython_has_eventloop() -> bool:
    """Return True if IPython %gui qt is active."""
    ipy_module = sys.modules.get('IPython')
    if not ipy_module:
        return False

    shell: InteractiveShell = ipy_module.get_ipython()
    if not shell:
        return False

    return shell.active_eventloop == 'qt'


def _pycharm_has_eventloop(app: QApplication) -> bool:
    """Return true if running in PyCharm and eventloop is active."""
    in_pycharm = 'PYCHARM_HOSTED' in os.environ
    in_event_loop = getattr(app, '_in_event_loop', False)
    return in_pycharm and in_event_loop


def _try_enable_ipython_gui(gui: str | None = 'qt') -> None:
    """Start %gui qt the eventloop."""
    ipy_module = sys.modules.get('IPython')
    if not ipy_module:
        return

    shell: InteractiveShell = ipy_module.get_ipython()
    if not shell:
        return
    if shell.active_eventloop != gui:
        shell.enable_gui(gui)


def run(
    *,
    force: bool = False,
    max_loop_level: int = 1,
    _func_name: str = 'run',
) -> None:
    """Start the Qt event loop.

    Parameters
    ----------
    force : bool, optional
        Start the event loop even if there are no top level widgets to show.
    max_loop_level : int, optional
        Refuse to start if the application already runs this many event
        loops (default 1).
    _func_name : str, optional
        Name of the calling function, used in the warning messages.
    """
    if _ipython_has_eventloop():
        # If %gui qt is active, we don't need to block again.
        return

    app = QApplication.instance()

    if app is not None and _pycharm_has_eventloop(app):
        return

    if not app:
        raise RuntimeError(
            'No Qt app has been created. One can be created by calling '
            '`get_qapp()` or `qtpy.QtWidgets.QApplication([])`'
        )
    if not app.topLevelWidgets() and not force:
        warn(
            'Refusing to run a QApplication with no topLevelWidgets. To run '
            f'the app anyway, use `{_func_name}(force=True)`',
            stacklevel=2,
        )
        return

    if app.thread().loopLevel() >= max_loop_level:
        loops = app.thread().loopLevel()
        warn(
            'A QApplication is already running with 1 event loop. To enter '
            f'*another* event loop, use `{_func_name}(max_loop_level='
            f'{loops + 1})`',
            stacklevel=2,
        )
        return
    with notification_manager, _maybe_allow_interrupt(app):
        app.exec_()
