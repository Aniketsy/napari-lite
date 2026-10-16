# napari-lite: own code
"""Utilities shared by the layers, components and canvas.

napari's ``utils/__init__.py`` imports dask utilities, colormaps (and so
vispy), system information and the notebook screenshot helper eagerly.
Here the same public names are loaded on first use; ``sys_info``,
``citation_text`` and ``nbscreenshot`` are application features and are
not provided (a notebook helper returns with issue 15).
"""

from lazy_loader import attach as _attach

__getattr__, __dir__, __all__ = _attach(
    __name__,
    submod_attrs={
        '_check_numpy_version': ['NUMPY_VERSION_IS_THREADSAFE'],
        '_dask_utils': ['resize_dask_cache'],
        'colormaps.colormap': [
            'Colormap',
            'CyclicLabelColormap',
            'DirectLabelColormap',
        ],
        'progress': ['cancelable_progress', 'progrange', 'progress'],
    },
)
del _attach
