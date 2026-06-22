import json

from events.pihomeevent import PihomeEvent
from util.phlog import PIHOME_LOGGER

_LEVELS = ["info", "warning", "error", "success"]


class NotificationEvent(PihomeEvent):
    """Push a persistent, actionable notification into the Notification Center.

    Unlike a toast (which auto-dismisses) a notification lingers until the user
    taps it (firing the optional attached event, then auto-dismissing) or clears
    it. Notifications appear as an app-wide bell badge and open into a slide-in
    panel.
    """

    type = "notification"

    def __init__(self, title, description="", icon=None, event=None,
                 level="info", id=None, **kwargs):
        super().__init__()
        self.title = title
        self.description = description or ""
        self.icon = icon                # image URL (optional)
        self.event = event              # nested PiHome event dict fired on tap (optional)
        self.level = level if level in _LEVELS else "info"
        self.id = id                    # optional; same id replaces an existing notification

    def execute(self):
        if not self.title:
            return {
                "code": 400,
                "body": {"status": "error", "message": "title is required"}
            }
        try:
            # Lazy import: the singleton lives in a Kivy composite that must not
            # be imported before the Window/Config setup in main.py.
            from composites.Notifications.notificationcenter import NOTIFICATION_CENTER
            nid = NOTIFICATION_CENTER.add({
                "id": self.id,
                "title": self.title,
                "description": self.description,
                "icon": self.icon,
                "event": self.event,
                "level": self.level,
            })
        except Exception as e:
            PIHOME_LOGGER.error("NotificationEvent: failed to add notification: {}".format(e))
            return {
                "code": 500,
                "body": {"status": "error", "message": str(e)}
            }
        return {
            "code": 200,
            "body": {"status": "success", "message": "Notification added", "id": nid}
        }

    def to_json(self):
        return json.dumps({
            "type": self.type,
            "title": self.title,
            "description": self.description,
            "icon": self.icon,
            "event": self.event,
            "level": self.level,
            "id": self.id,
        })

    def to_definition(self):
        return {
            "type": self.type,
            "title": self.type_def("string", required=True, description="Notification title"),
            "description": self.type_def("string", required=False, description="Notification body text"),
            "icon": self.type_def("string", required=False, description="Image URL for the notification icon"),
            "level": self.type_def("option", required=False, description="Notification level (sets default icon + accent color)", options=_LEVELS),
            "event": self.type_def("event", required=False, description="PiHome event to fire when the notification is tapped"),
            "id": self.type_def("string", required=False, description="Optional id; sending the same id again updates the existing notification"),
        }
