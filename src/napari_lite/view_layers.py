# napari-lite: own code
"""``imshow``: create a viewer and add an image in one call (as napari)."""

from __future__ import annotations

import inspect
from typing import Any

from napari_lite.components.dims import Dims
from napari_lite.layers import Image
from napari_lite.viewer import Viewer

__all__ = ['imshow']

_viewer_params = inspect.signature(Viewer).parameters


def _make_viewer_then(
    add_method: str,
    /,
    *args: Any,
    viewer: Viewer | None = None,
    **kwargs: Any,
) -> tuple[Viewer, Any]:
    """Create a viewer (or use ``viewer``), call ``add_method`` on it with
    the remaining arguments, and return ``(viewer, layer)``.

    Keyword arguments that the ``Viewer`` constructor takes go to it, the
    ``Dims`` fields are applied after the data is added, everything else
    goes to the ``add_*`` method.
    """
    vkwargs = {
        k: kwargs.pop(k)
        for k in list(kwargs)
        if k in _viewer_params
        if k != 'axis_labels'
    }
    if 'axis_labels' in kwargs:
        vkwargs['axis_labels'] = (
            kwargs['axis_labels'] if kwargs['axis_labels'] is not None else ()
        )
    # separate dims kwargs because we want to set those after adding data
    dims_kwargs = {
        k: vkwargs.pop(k) for k in list(vkwargs) if k in Dims.model_fields
    }
    if viewer is None:
        viewer = Viewer(**vkwargs)
    kwargs.update(kwargs.pop('kwargs', {}))
    method = getattr(viewer, add_method)
    added = method(*args, **kwargs)
    if isinstance(added, list):
        added = tuple(added)
    for arg_name, arg_val in dims_kwargs.items():
        setattr(viewer.dims, arg_name, arg_val)
    return viewer, added


def imshow(
    data: Any,
    *,
    viewer: Viewer | None = None,
    title: str = 'napari-lite',
    ndisplay: int = 2,
    order: tuple[int, ...] = (),
    axis_labels: tuple[str, ...] | None = None,
    show: bool = True,
    **kwargs: Any,
) -> tuple[Viewer, Image | tuple[Image, ...]]:
    """Load data into an Image layer and return the viewer and the layer.

    Parameters
    ----------
    data : array or list of arrays
        Image data, N >= 2 dimensional; a list of arrays of decreasing size
        is a multiscale image.
    viewer : Viewer, optional
        Add to this viewer instead of creating one.
    title, ndisplay, order, axis_labels, show
        Passed to ``Viewer`` when one is created.
    **kwargs
        Everything ``Viewer.add_image`` accepts (``name``, ``colormap``,
        ``contrast_limits``, ``channel_axis``, ``rgb``, ``scale``, ...).

    Returns
    -------
    viewer : Viewer
    layer : Image or tuple of Image
        A tuple when ``channel_axis`` splits the data into several layers.
    """
    return _make_viewer_then(
        'add_image',
        data,
        viewer=viewer,
        title=title,
        ndisplay=ndisplay,
        order=order,
        axis_labels=axis_labels,
        show=show,
        **kwargs,
    )
