"""
server/remote_input_handler.py

Lightweight handler for the dedicated remote-text-entry WebSocket
(``TEXT_SOCKET_PORT``). This is a high-frequency keystroke stream, so it does NOT
go through the event factory — it just forwards each value to the REMOTE_INPUT
bridge, which mirrors it onto the focused field on the Kivy main thread.

Expected message shapes (JSON):
    {"focus_id": <int>, "value": "<text>"}      live mirror
    {"focus_id": <int>, "action": "clear"}      clear the field
"""

import json

from util.phlog import PIHOME_LOGGER
from util.remote_input import REMOTE_INPUT


class RemoteInputSocketHandler:
    async def handle_message(self, message, socket):
        if message is None:
            return
        try:
            data = json.loads(message)
        except (ValueError, TypeError):
            return

        if not isinstance(data, dict) or "focus_id" not in data:
            return

        focus_id = data.get("focus_id")
        try:
            focus_id = int(focus_id)
        except (TypeError, ValueError):
            return

        if data.get("action") == "clear":
            REMOTE_INPUT.apply_text(focus_id, "")
            return

        if "value" in data:
            REMOTE_INPUT.apply_text(focus_id, data.get("value"))
