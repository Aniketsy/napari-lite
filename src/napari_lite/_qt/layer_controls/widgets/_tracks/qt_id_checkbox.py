from qtpy.QtWidgets import (
    QCheckBox,
    QWidget,
)

from napari_lite._qt.layer_controls.widgets.qt_widget_controls_base import (
    QtWidgetControlsBase,
    QtWrappedLabel,
)
from napari_lite._qt.utils import checked_to_bool
from napari_lite.layers import Tracks
from napari_lite.utils.events.event_utils import connect_setattr


class QtIdCheckBoxControl(QtWidgetControlsBase):
    """
    Class that wraps the connection of events/signals between the id should be
    displayed attribute and Qt widgets.

    Parameters
    ----------
    parent: qtpy.QtWidgets.QWidget
        An instance of QWidget that will be used as widgets parent
    layer : napari_lite.layers.Tracks
        An instance of a napari Tracks layer.

    Attributes
    ----------
    id_checkbox : qtpy.QtWidgets.QCheckBox
        Checkbox controlling if id of the layer should be shown.
    id_checkbox_label : napari_lite._qt.layer_controls.widgets.qt_widget_controls_base.QtWrappedLabel
        Label for showing the id chooser widget.
    """

    def __init__(self, parent: QWidget, layer: Tracks) -> None:
        super().__init__(parent, layer)
        # Setup layer
        # NOTE(arl): there are no events fired for changing checkbox (layer `display_id` attribute)

        # Setup widgets
        self.id_checkbox = QCheckBox()
        connect_setattr(
            self.id_checkbox.stateChanged,
            layer,
            'display_id',
            convert_fun=checked_to_bool,
        )

        self.id_checkbox_label = QtWrappedLabel('show ID:')

    def get_widget_controls(
        self,
    ) -> list[tuple[QtWrappedLabel, QWidget] | tuple[QWidget]]:
        return [(self.id_checkbox_label, self.id_checkbox)]
