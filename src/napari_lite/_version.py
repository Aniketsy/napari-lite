# napari-lite: own code
"""Package version, read from the installed distribution metadata.

napari generates ``_version.py`` with setuptools_scm at build time; copied
modules import ``__version__`` from here.  The lookup is deferred to first
access so that ``import napari_lite`` does not pay for importlib.metadata.
"""

from __future__ import annotations

_DIST = 'napari-lite'


def _lookup() -> str:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version(_DIST)
    except PackageNotFoundError:
        return '0.0.0+unknown'


def __getattr__(name: str) -> str:
    if name in {'__version__', 'version'}:
        value = _lookup()
        globals()['__version__'] = globals()['version'] = value
        return value
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
