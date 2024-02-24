from kivy.lang import Builder
from events.pihomeevent import PihomeEventFactory
from interface.pihomescreen import PiHomeScreen
from services.audio.sfx import SFX
from kivy.properties import ColorProperty, StringProperty, NumericProperty
from theme.theme import Theme

# Imports used by kv file
from components.Button.circlebutton import CircleButton
from util.phlog import PIHOME_LOGGER

Builder.load_file("./screens/Task/taskscreen.kv")

class TaskScreen(PiHomeScreen):
    background = ColorProperty((0,0,0,0.7))
    background_image = StringProperty("")
    text_color = Theme().get_color(Theme().TEXT_PRIMARY)
    title = StringProperty("<title>")
    description = StringProperty("<message>")
    start_time = NumericProperty(0)
    on_confirm = None
    on_cancel = None
    sfx = None
    
    def __init__(self, **kwargs):
        super(TaskScreen, self).__init__(**kwargs)

    def set_task(self, task):
        self.locked = True
        PIHOME_LOGGER.info("Task Screen Set Task To: {} with priority of {}".format(task.name, task.priority))
        self.task = task
        from services.taskmanager.taskmanager import TaskPriority
        self.title = task.name
        self.description = task.description
        if task.priority == TaskPriority.LOW:
            self.background = Theme().get_color(Theme().ALERT_INFO, 0.8)
            # self.sfx = SFX.play("notify")
        elif task.priority == TaskPriority.MEDIUM:
            self.background = Theme().get_color(Theme().ALERT_WARNING, 0.8)
            self.sfx = SFX.play("alert")
        else:
            self.background = Theme().get_color(Theme().ALERT_DANGER, 0.8)
            self.sfx = SFX.loop("alert")
        
        if task.background_image is not None:
            self.background_image = task.background_image
        else:
            self.background_image = ""

        # self.start_time = task.start_time
        self.on_confirm = self.generate_event(task.on_confirm)
        self.on_cancel = self.generate_event(task.on_cancel)
    
    def on_touch_down(self, touch):
        if self.sfx is not None:
            self.sfx.stop()
        return super().on_touch_down(touch)

    def generate_event(self, event_json):
        event = None
        if event_json is None:
            return event
        try:
            event = PihomeEventFactory.create_event_from_dict(event_json)
        except Exception as e:
            PIHOME_LOGGER.error(f"Error generating event from json: {e}")
        return event

    def on_leave(self, *args):
        if self.sfx is not None:
            self.sfx.stop()
        return super().on_leave(*args)


    def confirm(self):
        self.locked = False
        if self.on_confirm is not None:
            self.on_confirm.execute()
        from services.taskmanager.taskmanager import TaskStatus
        self.task.status = TaskStatus.COMPLETED
        self.go_back()

    def cancel(self):
        self.locked = False
        if self.on_cancel is not None:
            self.on_cancel.execute()
        from services.taskmanager.taskmanager import TaskStatus
        self.task.status = TaskStatus.CANCELED
        self.go_back()
