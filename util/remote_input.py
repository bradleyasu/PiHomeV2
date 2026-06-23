"""
util/remote_input.py

Bridge between PiHome's focused on-screen text field and the phone web client.

When a ``PiTextInput`` gains focus, it registers itself here. The status payload
(polled every ~1s over the 8765 WebSocket) reports the focused field via
``to_status()`` so the phone can pop a text-entry sheet. The phone then opens a
dedicated socket (port ``TEXT_SOCKET_PORT``) and streams the typed value back via
``apply_text()``, which mirrors it onto the device field on the Kivy main thread.

The ``focus_id`` is a monotonic counter that guards the ~1s race window: text
aimed at a field that is no longer focused (a newer id has been issued, or the
field blurred) is ignored.
"""

import weakref

from kivy.clock import Clock

from util.phlog import PIHOME_LOGGER


class RemoteInput:
    def __init__(self):
        self._focus_id = 0
        self._widget_ref = None   # weakref to the currently focused PiTextInput

    # ── Device-side focus tracking (called from PiTextInput.on_focus) ──

    def set_focus(self, widget):
        """Record *widget* as the focused field and issue a fresh focus_id."""
        self._focus_id += 1
        self._widget_ref = weakref.ref(widget)

    def clear_focus(self, widget):
        """Clear focus if *widget* is the one we currently track."""
        if self._current() is widget:
            self._widget_ref = None

    def _current(self):
        return self._widget_ref() if self._widget_ref is not None else None

    # ── Status reporting (called from StatusEvent) ──

    def to_status(self):
        widget = self._current()
        if widget is None or not getattr(widget, "focus", False):
            return {"active": False, "focus_id": self._focus_id}

        secure = bool(getattr(widget, "secure", False))
        try:
            from interface.pihomescreenmanager import PIHOME_SCREEN_MANAGER
            screen = PIHOME_SCREEN_MANAGER.current_screen.name
        except Exception:
            screen = ""

        return {
            "active": True,
            "focus_id": self._focus_id,
            "hint": getattr(widget, "hint_text", "") or "",
            # Never echo a secure field's existing value back to the phone.
            "value": None if secure else (widget.text or ""),
            "multiline": bool(getattr(widget, "multiline", False)),
            "secure": secure,
            "screen": screen,
        }

    # ── Remote text application (called from the dedicated text socket) ──

    def apply_text(self, focus_id, value):
        """Mirror *value* onto the focused field, on the Kivy main thread.

        Ignored if *focus_id* is stale (focus moved or the field blurred).
        """
        Clock.schedule_once(lambda dt: self._apply(focus_id, value), 0)

    def _apply(self, focus_id, value):
        if focus_id != self._focus_id:
            return
        widget = self._current()
        if widget is None or not getattr(widget, "focus", False):
            return
        try:
            widget.text = "" if value is None else str(value)
        except Exception as e:
            PIHOME_LOGGER.error(f"RemoteInput: failed to apply text: {e}")


REMOTE_INPUT = RemoteInput()
