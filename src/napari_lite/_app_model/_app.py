# napari-lite: own code
"""napari's application object: not in napari-lite.

The copied tests of the layer list and the viewer buttons import
``get_app_model`` at module level; the tests that call it are skipped by
``conftest.py``.
"""

from __future__ import annotations

from typing import NoReturn

__all__ = ['NoAppModel', 'get_app_model']


class NoAppModel(RuntimeError):
    """Raised where napari would hand out its app-model application."""


def get_app_model() -> NoReturn:
    raise NoAppModel('napari-lite has no app-model')
