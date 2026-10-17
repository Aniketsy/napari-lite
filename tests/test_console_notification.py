# napari-lite: own code
"""Console notifications on a console that cannot encode every character
(cp1252 when Windows pipes the output): the message is printed with those
characters replaced, instead of print failing inside the notification
handler and a misleading log taking the message's place."""

from __future__ import annotations

import io
import sys


def test_console_notification_with_a_legacy_console_encoding(
    monkeypatch,
) -> None:
    from napari_lite.settings import get_settings
    from napari_lite.utils.notifications import (
        Notification,
        NotificationSeverity,
        show_console_notification,
    )

    monkeypatch.setattr(
        get_settings().application,
        'console_notification_level',
        NotificationSeverity.INFO,
    )
    raw = io.BytesIO()
    monkeypatch.setattr(
        sys,
        'stdout',
        io.TextIOWrapper(raw, encoding='cp1252', errors='strict'),
    )
    show_console_notification(Notification('press \u21e7 to select', 'warning'))
    sys.stdout.flush()
    assert b'press ? to select' in raw.getvalue()
