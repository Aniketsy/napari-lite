# napari-lite: own code
"""No app-model.

napari builds its menus, command palette and dependency injection on
app-model.  napari-lite has none of those.  The ``context`` subpackage
exists because ``components/layerlist.py`` imports it; it hands back no
context, which is the path napari itself takes while the ``Viewer`` type
is being created.
"""
