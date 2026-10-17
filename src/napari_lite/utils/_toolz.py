# napari-lite: own code
"""``identity`` and ``pipe``: the two toolz functions the transforms use.

``utils/transforms/transforms.py`` builds a transform chain with
``toolz.pipe`` and marks the default transform with ``toolz.identity``.
toolz was a dependency for those two lines; dask still brings it with the
``dask`` extra.  Same behaviour: ``pipe(x, f, g)`` is ``g(f(x))``, and
``identity`` is one function object, so ``func is identity`` holds as with
toolz's.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def identity(x: Any) -> Any:
    """Return ``x`` unchanged."""
    return x


def pipe(data: Any, *funcs: Callable[[Any], Any]) -> Any:
    """Pass ``data`` through ``funcs`` in order."""
    for func in funcs:
        data = func(data)
    return data
