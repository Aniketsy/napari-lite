# napari-lite: own code
"""Qt widgets and plumbing.

Importing this package checks that a supported Qt binding is available and
nothing else: napari's ``_qt/__init__.py`` also imports the main window
and the event loop, which napari-lite does not have.  Use
``napari_lite._qt.qt_event_loop`` for ``get_qapp`` and ``run``.
"""

from __future__ import annotations

try:
    from qtpy import API_NAME, QtCore
except Exception as e:
    if 'No Qt bindings could be found' in str(e):
        from inspect import cleandoc

        from napari_lite.utils._env_detection import (
            detect_installed_qt_bindings,
        )

        installed = detect_installed_qt_bindings()
        found = (
            'Installed bindings: '
            + ', '.join(f'{k}={v}' for k, v in installed.items())
            + '.\n'
            if installed
            else ''
        )
        raise ImportError(
            cleandoc(
                f"""
                No Qt bindings could be found for napari-lite.
                {found}
                napari-lite needs PyQt6 (default) or PySide6:
                    $ pip install -U 'napari-lite[pyqt6]'
                    $ pip install -U 'napari-lite[pyside6]'
                With conda:
                    $ conda install -c conda-forge pyqt6
                """
            )
        ) from e
    raise


MIN_QT_VERSION = (6, 7)


def _check_qt_version(qt_version: str, api_name: str) -> None:
    """Raise ImportError if the Qt version used by qtpy is not supported."""
    if tuple(int(x) for x in qt_version.split('.')[:2]) >= MIN_QT_VERSION:
        return

    min_version = '.'.join(map(str, MIN_QT_VERSION))
    raise ImportError(
        f'napari-lite requires Qt >= {min_version}, but {api_name} with '
        f'Qt {qt_version} was imported. If PyQt6 or PySide6 is also '
        'installed, select it with the QT_API environment variable '
        '(for example QT_API=pyqt6).'
    )


_check_qt_version(QtCore.__version__, API_NAME)

__all__ = ['API_NAME', 'MIN_QT_VERSION']
