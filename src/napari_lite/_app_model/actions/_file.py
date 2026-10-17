# napari-lite: own code
"""New empty layers: same behaviour as napari's "File > New Layer" actions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from napari_lite.layers import Points, Shapes

if TYPE_CHECKING:
    from napari_lite.components import LayerList, ViewerModel
    from napari_lite.layers import Layer

__all__ = ['new_labels', 'new_points', 'new_shapes']


def add_new_points(viewer: ViewerModel) -> None:
    """Add an empty Points layer sized after the selection (or the dims)."""
    if not viewer.layers.selection:
        ndim = max(viewer.dims.ndim, 2)
        viewer.add_points(
            ndim=ndim,
            scale=(1,) * ndim,
            units=viewer.layers.extent.units,
        )
    else:
        extent = viewer.layers.get_extent(viewer.layers.selection)
        viewer.add_points(
            ndim=len(extent.step),
            scale=extent.step,
            units=viewer.layers.extent.units,
        )


def add_new_shapes(viewer: ViewerModel) -> None:
    """Add an empty Shapes layer sized after the selection (or the dims)."""
    if not viewer.layers.selection:
        ndim = max(viewer.dims.ndim, 2)
        viewer.add_shapes(
            ndim=ndim,
            scale=(1,) * ndim,
            units=viewer.layers.extent.units,
        )
    else:
        extent = viewer.layers.get_extent(viewer.layers.selection)
        viewer.add_shapes(
            ndim=len(extent.step),
            scale=extent.step,
            units=viewer.layers.extent.units,
        )


def _create_single_layer(
    source_layer: Layer,
    layer_class: type[Points] | type[Shapes],
    layer_name: str,
) -> Points | Shapes:
    """A Points or Shapes layer with the transform of ``source_layer``."""
    return layer_class(
        name=layer_name,
        ndim=source_layer.ndim,
        scale=source_layer.scale,
        translate=source_layer.translate,
        rotate=source_layer.rotate,
        shear=source_layer.shear,
        units=source_layer.units,
        axis_labels=source_layer.axis_labels,
        affine=source_layer.affine.affine_matrix,
    )


def get_layer_name(base_name: str, existing_names: set[str]) -> str:
    """``base_name``, or ``base_name N`` if the name is taken."""
    if base_name not in existing_names:
        return base_name
    index = 1
    while f'{base_name} {index}' in existing_names:
        index += 1
    return f'{base_name} {index}'


def new_labels(viewer: ViewerModel) -> None:
    """Add an empty Labels layer covering the current data."""
    viewer._new_labels()


def _new_layer_from_active(
    layer_list: LayerList, layer_class: type[Points] | type[Shapes]
) -> Points | Shapes:
    if layer_list.selection.active is None:
        raise ValueError('No active layer to create new layer from.')
    source_layer = layer_list.selection.active
    new_layer_name = get_layer_name(
        f'{source_layer.name} - {layer_class.__name__}',
        existing_names={layer.name for layer in layer_list},
    )
    return _create_single_layer(source_layer, layer_class, new_layer_name)


def new_points(viewer: ViewerModel) -> None:
    """Add an empty Points layer, with the active layer's transform if any."""
    if viewer.layers.selection.active is not None:
        viewer.add_layer(_new_layer_from_active(viewer.layers, Points))
    else:
        add_new_points(viewer)


def new_shapes(viewer: ViewerModel) -> None:
    """Add an empty Shapes layer, with the active layer's transform if any."""
    if viewer.layers.selection.active is not None:
        viewer.add_layer(_new_layer_from_active(viewer.layers, Shapes))
    else:
        add_new_shapes(viewer)
