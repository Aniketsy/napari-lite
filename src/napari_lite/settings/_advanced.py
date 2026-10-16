# napari-lite: own code
"""Advanced settings: canvas creation flags."""

from __future__ import annotations

from napari_lite.utils.events.evented_model import EventedModel


class AdvancedSettings(EventedModel):
    multisampling: bool = False
    autoswap_buffers: bool = False
