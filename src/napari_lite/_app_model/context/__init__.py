# napari-lite: own code
"""Contexts for menu enablement, reduced to a dictionary.

napari keeps an app-model ``Context`` per layer list; its menus read their
enablement rules from it.  napari-lite's one menu, the layer list's
(``_qt/_qapp_model/_menus.py``), reads the layer list directly.
``create_context`` hands out a plain dictionary so the copied code can
still store the few callables it puts there.
"""

from __future__ import annotations

from typing import Any

__all__ = ['Context', 'create_context', 'get_context']


class Context(dict[str, Any]):
    """A dictionary standing in for app-model's ``Context``."""


def create_context(obj: Any, *args: Any, **kwargs: Any) -> Context:
    return Context()


def get_context(obj: Any) -> Context | None:
    """The context created for ``obj`` (the layer list keeps it as ``_ctx``)."""
    return getattr(obj, '_ctx', None)
