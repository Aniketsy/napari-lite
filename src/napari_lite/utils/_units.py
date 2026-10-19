"""Units utilities."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pint

# define preferred scale bar values
PREFERRED_VALUES = [
    1,
    2,
    5,
    10,
    15,
    20,
    25,
    50,
    75,
    100,
    125,
    150,
    200,
    500,
    750,
]


def get_unit_registry() -> 'pint.UnitRegistry':
    """Get pint's UnitRegistry.

    Pint greedily imports many libraries, (including dask, xarray, pandas, and
    babel) to check for compatibility.  Some of those libraries may be slow to
    import.  This accessor function should be used (and only when units are
    actually necessary) to avoid incurring a large import time penalty.

    See comment for details:
    https://github.com/napari/napari/pull/2617#issuecomment-827747792
    """
    import pint

    registry = pint.get_application_registry()
    # napari-lite: the first registry of the process is built from pint's
    # definition cache (0.02 s against 0.2 s of parsing); a registry made
    # elsewhere before is used as it is
    inner = getattr(registry, '_registry', None)  # None: a plain registry
    if inner is not None and type(inner).__name__ == 'LazyRegistry':
        from pathlib import Path

        from napari_lite.utils._platformdirs import user_cache_dir

        cache = Path(user_cache_dir()) / 'pint'
        try:
            cache.mkdir(parents=True, exist_ok=True)
            pint.set_application_registry(
                pint.UnitRegistry(cache_folder=str(cache))
            )
        except Exception:  # an unwritable cache: the default registry
            pint.set_application_registry(pint.UnitRegistry())
        registry = pint.get_application_registry()
    return registry
