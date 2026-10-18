# Keyboard and mouse

napari-lite keeps napari's default key bindings.  They are stored in
`get_settings().shortcuts.shortcuts` (action name -> list of shortcuts) and
can be changed in code for the session, before the first window is created:

```python
from napari_lite.settings import get_settings
from napari_lite.utils.action_manager import bind_shortcuts_from_settings

get_settings().shortcuts.shortcuts['napari:toggle_ndisplay'] = ['F3']
bind_shortcuts_from_settings()  # the viewer window does this too
```

`Ctrl` means `Cmd` on macOS.  Layer shortcuts work while that layer is the
active (selected) one.

## Mouse

| Action | 2D | 3D |
|---|---|---|
| Pan | drag | drag with Shift |
| Zoom | wheel | wheel |
| Rotate | | drag |
| Zoom to a box | Alt + drag | |
| Step through a slice dimension | Ctrl + wheel over the canvas | |
| Layer-specific tools (paint, pick, add point, draw shape) | click / drag in the layer's mode | |


## Viewer

| Shortcut | Action | Name |
|---|---|---|
| `Ctrl+O` | Open files (png, jpg, tif, npy, npz) | `napari-lite:open_files` |
| `Ctrl+⇧+C` | Show/Hide IPython console (napari-lite has none) | `napari:toggle_console_visibility` |
| `Ctrl+Y` | Toggle 2D/3D view | `napari:toggle_ndisplay` |
| `Ctrl+⇧+T` | Toggle current viewer theme | `napari:toggle_theme` |
| `Ctrl+R` | Reset view to original state | `napari:reset_view` |
| `Ctrl+⌦`, `Ctrl+⌫` | Delete selected layers | `napari:delete_selected_layers` |
| `Ctrl+Alt+/` | Show all key bindings | `napari:show_shortcuts` |
| `←` | Increment dimensions slider to the left | `napari:increment_dims_left` |
| `→` | Increment dimensions slider to the right | `napari:increment_dims_right` |
| `Alt+↑` | Move focus of dimensions slider up | `napari:focus_axes_up` |
| `Alt+↓` | Move focus of dimensions slider down | `napari:focus_axes_down` |
| `Ctrl+E` | Change order of the visible axes, e.g. [-3, -2, -1] ‑> [-1, -3, -2] | `napari:roll_axes` |
| `Ctrl+T` | Transpose order of the last two visible axes, e.g. [-2, -1] ‑> [-1, -2] | `napari:transpose_axes` |
| `Ctrl+Alt+T` | Rotate layers 90 degrees counter-clockwise | `napari:rotate_layers` |
| `Ctrl+G` | Toggle grid mode | `napari:toggle_grid` |
| `V` | Toggle visibility of selected layers | `napari:toggle_selected_visibility` |
| `⇧+V` | Toggle visibility of unselected layers | `napari:toggle_unselected_visibility` |
| `Ctrl+↑` | Select layer above | `napari:select_layer_above` |
| `Ctrl+↓` | Select layer below | `napari:select_layer_below` |
| `⇧+Alt+↑` | Select and show only layer above | `napari:show_only_layer_above` |
| `⇧+Alt+↓` | Select and show only layer below | `napari:show_only_layer_below` |
| `␣` | Press and hold for move camera mode | `napari:hold_for_pan_zoom` |

## Image

| Shortcut | Action | Name |
|---|---|---|
| `X` | Orient plane normal along x-axis | `napari:orient_plane_normal_along_x` |
| `Y` | Orient plane normal along y-axis | `napari:orient_plane_normal_along_y` |
| `Z` | Orient plane normal along z-axis | `napari:orient_plane_normal_along_z` |
| `O` | Orient plane normal along view direction
Hold down to have plane follow camera | `napari:orient_plane_normal_along_view_direction` |
| `C` | Apply auto-contrast | `napari:auto_contrast_once` |
| `1` | Move camera | `napari:activate_image_pan_zoom_mode` |
| `2` | Transform | `napari:activate_image_transform_mode` |

## Labels

| Shortcut | Action | Name |
|---|---|---|
| `1`, `E` | Activate the label eraser | `napari:activate_labels_erase_mode` |
| `2`, `P` | Activate the paint brush | `napari:activate_labels_paint_mode` |
| `3` | Activate the polygon tool | `napari:activate_labels_polygon_mode` |
| `4`, `F` | Activate the fill bucket | `napari:activate_labels_fill_mode` |
| `5`, `L` | Pick mode | `napari:activate_labels_picker_mode` |
| `6`, `Z` | Move camera | `napari:activate_labels_pan_zoom_mode` |
| `7` | Transform | `napari:activate_labels_transform_mode` |
| `M` | Set the currently selected label to the largest used label plus one | `napari:new_label` |
| `X` | Swap between the selected label and the background label | `napari:swap_selected_and_background_labels` |
| `-` | Decrease the currently selected label by one | `napari:decrease_label_id` |
| `=` | Increase the currently selected label by one | `napari:increase_label_id` |
| `[` | Decrease the paint brush size by one | `napari:decrease_brush_size` |
| `]` | Increase the paint brush size by one | `napari:increase_brush_size` |
| `B` | Toggle preserve labels | `napari:toggle_preserve_labels` |
| `⎋` | Reset the current polygon | `napari:reset_polygon` |
| `↵` | Complete the current polygon | `napari:complete_polygon` |

## Points

| Shortcut | Action | Name |
|---|---|---|
| `2`, `P` | Add points | `napari:activate_points_add_mode` |
| `3`, `S` | Select points | `napari:activate_points_select_mode` |
| `4`, `Z` | Move camera | `napari:activate_points_pan_zoom_mode` |
| `5` | Transform | `napari:activate_points_transform_mode` |
| `A` | Select/Deselect all points in the current view slice | `napari:select_all_in_slice` |
| `⇧+A` | Select/Deselect all points in the current view slice | `napari:select_append_all_in_slice` |
| `Ctrl+A` | Select/Deselect all points in the layer | `napari:select_all_data` |
| `1`, `⌦`, `⌫` | Delete selected points | `napari:delete_selected_points` |

## Shapes

| Shortcut | Action | Name |
|---|---|---|
| `R` | Add rectangles | `napari:activate_add_rectangle_mode` |
| `E` | Add ellipses | `napari:activate_add_ellipse_mode` |
| `L` | Add lines | `napari:activate_add_line_mode` |
| `T` | Add path | `napari:activate_add_path_mode` |
| `⇧+L` | Add polylines | `napari:activate_add_polyline_mode` |
| `P` | Add polygons | `napari:activate_add_polygon_mode` |
| `⇧+P` | Add polygons lasso | `napari:activate_add_polygon_lasso_mode` |
| `4`, `D` | Select vertices | `napari:activate_direct_mode` |
| `5`, `S` | Select shapes | `napari:activate_select_mode` |
| `6`, `Z` | Move camera | `napari:activate_shapes_pan_zoom_mode` |
| `7` | Transform | `napari:activate_shapes_transform_mode` |
| `2`, `I` | Insert vertex | `napari:activate_vertex_insert_mode` |
| `1`, `X` | Remove vertex | `napari:activate_vertex_remove_mode` |
| `Ctrl+C` | Copy any selected shapes | `napari:copy_selected_shapes` |
| `Ctrl+V` | Paste any copied shapes | `napari:paste_shape` |
| `F` | Move to front | `napari:move_shapes_selection_to_front` |
| `B` | Move to back | `napari:move_shapes_selection_to_back` |
| `A`, `Ctrl+A` | Select/Deselect all shapes in the current view slice | `napari:select_shapes_in_slice` |
| `3`, `⌦`, `⌫` | Delete any selected shapes | `napari:delete_selected_shapes` |
| `↵`, `⎋` | Finish any drawing, for example when using the path or polygon tool | `napari:finish_drawing_shape` |

## Vectors

| Shortcut | Action | Name |
|---|---|---|
| `1` | Move camera | `napari:activate_vectors_pan_zoom_mode` |
| `2` | Transform | `napari:activate_vectors_transform_mode` |

## Surface

| Shortcut | Action | Name |
|---|---|---|
| `1` | Move camera | `napari:activate_surface_pan_zoom_mode` |
| `2` | Transform | `napari:activate_surface_transform_mode` |

## Tracks

| Shortcut | Action | Name |
|---|---|---|
| `1` | Move camera | `napari:activate_tracks_pan_zoom_mode` |
| `2` | Transform | `napari:activate_tracks_transform_mode` |

_Generated by `tools/make_shortcuts_doc.py`; edit the generator, not this file._
