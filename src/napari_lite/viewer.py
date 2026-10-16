# napari-lite: own code
"""The viewer.

``Viewer`` (a ``ViewerModel`` with a window) arrives with milestone M2,
issue 13.  ``current_viewer`` is here already because the copied thread
worker code asks for it: with no viewer open it returns None.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from napari_lite.components import ViewerModel

__all__ = ['current_viewer']


def current_viewer() -> ViewerModel | None:
    """Return the most recently created viewer, or None."""
    viewer_cls = globals().get('Viewer')
    if viewer_cls is None:
        return None
    instances = getattr(viewer_cls, '_instances', ())
    return next(iter(reversed(list(instances))), None)
