# napari-lite: own code
"""Closing a ``QtDims`` widget while it plays stops the playback thread
first.  Qt ends the process when a ``QThread`` is deleted while it runs,
and pytest-qt closes a test's widgets before any fixture can stop them,
so a playback test that failed used to take the whole run down with it."""

from __future__ import annotations

import pytest


@pytest.mark.allow_animation_thread
def test_closing_while_playing_stops_the_thread(qtbot) -> None:
    from napari_lite._qt.widgets.qt_dims import QtDims
    from napari_lite.components import Dims

    widget = QtDims(Dims(ndim=3))
    qtbot.addWidget(widget)
    widget.play(0, fps=50)
    qtbot.waitUntil(lambda: widget.is_playing)
    thread = widget._animation_thread
    assert thread.isRunning()
    widget.close()
    assert not widget.is_playing
    assert thread.isFinished()
    widget.close()  # again, as pytest-qt will: nothing left to stop
