from kivy.lang import Builder
from interface.pihomescreen import PiHomeScreen
from services.audio.sfx import SFX
from kivy.properties import ColorProperty, StringProperty, NumericProperty

from components.Button.circlebutton import CircleButton

from theme.theme import Theme

Builder.load_file("./screens/Task/taskscreen.kv")

class TaskScreen(PiHomeScreen):
    background = ColorProperty((0,0,0,0.7))
    text_color = Theme().get_color(Theme().TEXT_PRIMARY)
    title = StringProperty("<title>")
    description = StringProperty("<message>")
    start_time = NumericProperty(0)
    on_confirm = None
    on_cancel = None

    def __init__(self, **kwargs):
        super(TaskScreen, self).__init__(**kwargs)

    def set_task(self, task):
        from services.taskmanager.taskmanager import TaskPriority
        self.title = task.name
        self.description = task.description
        if task.priority == TaskPriority.LOW:
            self.background = Theme().get_color(Theme().ALERT_INFO, 0.8)
        elif task.priority == TaskPriority.MEDIUM:
            self.background = Theme().get_color(Theme().ALERT_WARNING, 0.8)
        else:
            self.background = Theme().get_color(Theme().ALERT_DANGER, 0.8)
        # self.start_time = task.start_time
        # self.status = task.status
        # self.priority = task.priority
        self.on_confirm = task.on_confirm
        self.on_cancel = task.on_cancel