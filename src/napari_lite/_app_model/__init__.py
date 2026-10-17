# napari-lite: own code
"""No app-model.

napari builds its menus, command palette and dependency injection on
app-model.  napari-lite has none of those.  The ``context`` subpackage
exists because ``components/layerlist.py`` imports it; it hands back a
plain dictionary, and the one menu napari-lite has (the layer list's)
reads the layer list directly.
"""

from napari_lite._app_model._app import get_app_model

__all__ = ['get_app_model']
