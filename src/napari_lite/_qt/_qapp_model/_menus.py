# napari-lite: own code
"""The layer list's right-click menu, without app-model.

napari fills this menu from app-model actions whose enablement rules are
context-key expressions over the layer selection.  napari-lite keeps the
same entries, calls the same layer operations (``layers/_layer_actions``)
and writes the rules as plain functions of the layer list, evaluated each
time the menu opens.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import TYPE_CHECKING, Any

from qtpy.QtGui import QAction
from qtpy.QtWidgets import QMenu, QWidget

from napari_lite._app_model.constants import MenuId
from napari_lite._qt._qapp_model.qactions import _layerlist_context as clip
from napari_lite.layers import (
    Image,
    Labels,
    Points,
    Shapes,
    _layer_actions as ops,
)
from napari_lite.utils.notifications import show_error

if TYPE_CHECKING:
    from napari_lite.components import LayerList

__all__ = ['QtLayerListContextMenu', 'build_qmodel_menu']

Rule = Callable[['LayerList'], bool]
Operation = Callable[['LayerList'], Any]
# (title, operation or submenu items, enabled rule, checked rule or None);
# None is a separator
Item = tuple[str, Any, Rule, Rule | None] | None


# rules
def _n(ll: LayerList) -> int:
    return len(ll.selection)


def _selected(ll: LayerList) -> bool:
    return _n(ll) > 0


def _one(ll: LayerList) -> bool:
    return _n(ll) == 1


def _unselected(ll: LayerList) -> bool:
    return len(ll) > _n(ll)


def _only(ll: LayerList, cls: type) -> bool:
    return _n(ll) > 0 and all(isinstance(x, cls) for x in ll.selection)


def _images(ll: LayerList) -> bool:
    return _only(ll, Image)


def _labels(ll: LayerList) -> bool:
    return _only(ll, Labels)


def _active_rgb(ll: LayerList) -> bool:
    return bool(getattr(ll.selection.active, 'rgb', False))


def _deletion_locked(ll: LayerList) -> bool:
    from napari_lite.layers.base._base_constants import LayerLock

    return any(bool(x.locked & LayerLock.DELETION) for x in ll.selection)


def _no_empty_shapes(ll: LayerList) -> bool:
    return not any(
        isinstance(x, Shapes) and not len(x.data) for x in ll.selection
    )


def _to_labels(ll: LayerList) -> bool:
    """Images, or shapes layers with shapes in them; none locked."""
    return (
        _images(ll) or (_only(ll, Shapes) and _no_empty_shapes(ll))
    ) and not _deletion_locked(ll)


def _to_image(ll: LayerList) -> bool:
    return _labels(ll) and not _deletion_locked(ll)


def _same_shape(ll: LayerList) -> bool:
    shapes = {tuple(getattr(x.data, 'shape', ())) for x in ll.selection}
    return len(shapes) == 1


def _stack(ll: LayerList) -> bool:
    return (
        _n(ll) > 1
        and _images(ll)
        and _same_shape(ll)
        and not _deletion_locked(ll)
    )


def _rgb_stack(ll: LayerList) -> bool:
    return (
        _n(ll) in (3, 4)
        and _images(ll)
        and _same_shape(ll)
        and not _deletion_locked(ll)
    )


def _active_nd(ll: LayerList, cls: type) -> bool:
    active = ll.selection.active
    return isinstance(active, cls) and active.ndim > 2


def _image_nd(ll: LayerList) -> bool:
    return _active_nd(ll, Image)


def _points_nd(ll: LayerList) -> bool:
    return _active_nd(ll, Points)


def _projectable(ll: LayerList) -> bool:
    return _image_nd(ll) or _points_nd(ll)


def _split_rgb(ll: LayerList) -> bool:
    return (
        isinstance(ll.selection.active, Image)
        and _active_rgb(ll)
        and not _deletion_locked(ll)
    )


def _splittable(ll: LayerList) -> bool:
    return _image_nd(ll) and not _deletion_locked(ll)


def _any_linked(ll: LayerList) -> bool:
    from napari_lite.layers.utils._link_layers import layer_is_linked

    return any(layer_is_linked(x) for x in ll.selection)


def _linkable(ll: LayerList) -> bool:
    from napari_lite.layers.utils._link_layers import layer_is_linked

    return _n(ll) > 1 and not all(layer_is_linked(x) for x in ll.selection)


def _unselected_links(ll: LayerList) -> bool:
    from napari_lite.layers.utils._link_layers import get_linked_layers

    return bool(get_linked_layers(*ll.selection) - set(ll.selection))


def _all_have(ll: LayerList, attr: str) -> bool:
    return _n(ll) > 0 and all(hasattr(x, attr) for x in ll.selection)


def _bounding_boxes_visible(ll: LayerList) -> bool:
    return _n(ll) > 0 and all(x.bounding_box.visible for x in ll.selection)


def _paste_possible(ll: LayerList) -> bool:
    return _n(ll) > 0 and clip.is_valid_spatial_in_clipboard()


# entries
_DTYPES = ('int8', 'int16', 'int32', 'int64')
_DTYPES += tuple('u' + d for d in _DTYPES)
_PROJECTIONS = ('max', 'min', 'mean', 'median', 'sum', 'std')


def _items() -> list[Item]:
    """napari's layer context menu, group by group."""
    return [
        ('Toggle visibility', ops._toggle_visibility, _selected, None),
        ('Show All Selected Layers', ops._show_selected, _selected, None),
        ('Hide All Selected Layers', ops._hide_selected, _selected, None),
        (
            'Show All Unselected Layers',
            ops._show_unselected,
            _unselected,
            None,
        ),
        (
            'Hide All Unselected Layers',
            ops._hide_unselected,
            _unselected,
            None,
        ),
        ('Toggle lock', ops._toggle_lock, _selected, None),
        None,
        ('Convert to Labels', ops._convert_to_labels, _to_labels, None),
        ('Convert to Image', ops._convert_to_image, _to_image, None),
        (
            'Convert data type',
            [
                (
                    f'Convert to {d}',
                    partial(ops._convert_dtype, mode=d),
                    _labels,
                    None,
                )
                for d in _DTYPES
            ],
            _labels,
            None,
        ),
        None,
        ('Duplicate Layer', ops._duplicate_layer, _selected, None),
        ('Split Stack', ops._split_stack, _splittable, None),
        ('Split RGB', ops._split_rgb, _split_rgb, None),
        ('Merge to Stack', ops._merge_stack, _stack, None),
        (
            'Merge to RGB',
            partial(ops._merge_stack, rgb=True),
            _rgb_stack,
            None,
        ),
        (
            'Projections',
            [
                *(
                    (
                        f'{m} projection',
                        partial(ops._project, mode=m),
                        _image_nd,
                        None,
                    )
                    for m in _PROJECTIONS
                ),
                ('Drop first axis', ops._project_points, _points_nd, None),
            ],
            _projectable,
            None,
        ),
        None,
        ('Link Layers', ops._link_selected_layers, _linkable, None),
        ('Unlink Layers', ops._unlink_selected_layers, _any_linked, None),
        (
            'Select Linked Layers',
            ops._select_linked_layers,
            _unselected_links,
            None,
        ),
        None,
        (
            'Copy scale and transforms',
            [
                ('Copy all to clipboard', clip.copy_to_clipboard, _one, None),
                *(
                    (
                        f'Copy {k} to clipboard',
                        partial(clip.copy_to_clipboard, keys=(k,)),
                        _one,
                        None,
                    )
                    for k in clip.SPATIAL_KEYS
                ),
                None,
                (
                    'Apply scale/transforms from Clipboard',
                    clip.paste_from_clipboard,
                    _paste_possible,
                    None,
                ),
            ],
            _selected,
            None,
        ),
        (
            'Visualization',
            [
                (
                    'Bounding Box',
                    ops._toggle_bounding_box,
                    _selected,
                    _bounding_boxes_visible,
                ),
                (
                    'Name Overlay',
                    ops._toggle_name_overlay,
                    _selected,
                    ops._are_name_overlays_visible,
                ),
                (
                    'Colorbar',
                    ops._toggle_colorbar,
                    partial(_all_have, attr='colorbar'),
                    ops._are_colorbars_visible,
                ),
                (
                    'Border Colorbar',
                    ops._toggle_border_colorbar,
                    partial(_all_have, attr='border_colorbar'),
                    ops._are_border_colorbars_visible,
                ),
                (
                    'Face Colorbar',
                    ops._toggle_face_colorbar,
                    partial(_all_have, attr='face_colorbar'),
                    ops._are_face_colorbars_visible,
                ),
            ],
            _selected,
            None,
        ),
    ]


class QtLayerListContextMenu(QMenu):
    """The right-click menu of the layer list; ``parent`` is the list view.

    The entries are enabled (and the visualization toggles checked) by
    rules on the current selection each time the menu is updated, which
    the layer list's delegate does right before showing it.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rules: list[tuple[QAction, Rule, Rule | None]] = []
        self._build(self, _items())

    def _build(self, menu: QMenu, items: list[Item]) -> None:
        for item in items:
            if item is None:
                menu.addSeparator()
                continue
            title, target, rule, checked = item
            if isinstance(target, list):
                submenu = menu.addMenu(title)
                self._rules.append((submenu.menuAction(), rule, None))
                self._build(submenu, target)
                continue
            action = menu.addAction(title)
            if checked is not None:
                action.setCheckable(True)
            action.triggered.connect(partial(self._run, target))
            self._rules.append((action, rule, checked))

    def _run(self, operation: Operation, checked: bool = False) -> None:
        ll = self._layer_list()
        if ll is None:
            return
        try:
            operation(ll)
        except (AssertionError, NotImplementedError, ValueError) as e:
            show_error(str(e))

    def _layer_list(self) -> LayerList | None:
        """The layer list behind the view this menu belongs to."""
        return getattr(self.parent(), '_root', None)

    def update_from_context(self, ctx: Any = None) -> None:
        """Enable the entries whose rule holds for the current selection.

        napari passes its app-model context here; napari-lite reads the
        layer list instead and ignores ``ctx``.
        """
        ll = self._layer_list()
        for action, rule, checked in self._rules:
            enabled = ll is not None and bool(rule(ll))
            action.setEnabled(enabled)
            if checked is not None:
                action.setChecked(enabled and bool(checked(ll)))


def build_qmodel_menu(
    menu_id: str,
    title: str | None = None,
    parent: QWidget | None = None,
) -> QtLayerListContextMenu:
    """napari builds any registered menu from app-model; napari-lite has
    one menu, the layer list's."""
    if menu_id != MenuId.LAYERLIST_CONTEXT:
        raise ValueError(f'napari-lite has no menu {menu_id!r}')
    menu = QtLayerListContextMenu(parent)
    if title:
        menu.setTitle(title)
    return menu
