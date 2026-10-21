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

    # not qtbot.addWidget: closing a QtDims deletes it, and qtbot's own
    # close at teardown would find it gone
    widget = QtDims(Dims(ndim=3))
    widget.play(0, fps=50)
    qtbot.waitUntil(lambda: widget.is_playing)
    thread = widget._animation_thread
    assert thread.isRunning()
    widget.close()
    assert not widget.is_playing
    assert thread.isFinished()
    qtbot.wait(50)  # the deferred deletion, as a window's event loop does
