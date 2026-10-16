# napari-lite: own code
"""Utilities shared by the layers, components and canvas.

napari's ``utils/__init__.py`` imports dask utilities, colormaps (and so
vispy), system information and the notebook screenshot helper eagerly.
Here the same public names are loaded on first use; ``sys_info``,
``citation_text`` and ``nbscreenshot`` are application features and are
not provided (a notebook helper returns with issue 15).
"""

from lazy_loader import attach as _attach

# ``progress`` is both a submodule and a class: once anything imports the
# submodule, the package attribute is the module and a lazy lookup would
# never run.  So, as in napari, the class is bound eagerly (the module is
# small: tqdm and the events package).
from napari_lite.utils.progress import (
    cancelable_progress,
    progrange,
    progress,
)

__getattr__, __dir__, _lazy_all = _attach(
    __name__,
    submod_attrs={
        '_check_numpy_version': ['NUMPY_VERSION_IS_THREADSAFE'],
        '_dask_utils': ['resize_dask_cache'],
        'colormaps.colormap': [
            'Colormap',
            'CyclicLabelColormap',
            'DirectLabelColormap',
        ],
    },
)
__all__ = [*_lazy_all, 'cancelable_progress', 'progrange', 'progress']
del _attach, _lazy_all
