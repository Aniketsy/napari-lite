# napari-lite: own code
"""Utilities shared by the layers, components and canvas.

napari's ``utils/__init__.py`` imports dask utilities, colormaps (and so
vispy), system information, the progress bars (and so tqdm) and the
notebook screenshot helper eagerly.  Here every public name is loaded on
first use; ``sys_info`` and ``citation_text`` are application features
and are not provided.
"""

from importlib import import_module as _import_module

from lazy_loader import attach as _attach

_lazy_getattr, _lazy_dir, _lazy_all = _attach(
    __name__,
    submod_attrs={
        '_check_numpy_version': ['NUMPY_VERSION_IS_THREADSAFE'],
        '_dask_utils': ['resize_dask_cache'],
        'colormaps.colormap': [
            'Colormap',
            'CyclicLabelColormap',
            'DirectLabelColormap',
        ],
        'notebook_display': ['NotebookScreenshot', 'nbscreenshot'],
    },
)

# ``progress`` is both a submodule and a class, which lazy_loader cannot
# serve: importing the submodule makes ``napari_lite.utils.progress`` the
# module.  napari imports it eagerly and rebinds the name to the class.
# Here the submodule (and tqdm with it, about 50 modules) is imported on
# the first access to one of these names, which are rebound right then.
_PROGRESS_NAMES = ('cancelable_progress', 'progrange', 'progress')


def __getattr__(name: str) -> object:
    if name in _PROGRESS_NAMES:
        module = _import_module(f'{__name__}.progress')
        for attr in _PROGRESS_NAMES:
            globals()[attr] = getattr(module, attr)
        return globals()[name]
    return _lazy_getattr(name)


def __dir__() -> list[str]:
    return sorted({*_lazy_dir(), *_PROGRESS_NAMES})


__all__ = [*_lazy_all, *_PROGRESS_NAMES]
del _attach, _lazy_all
