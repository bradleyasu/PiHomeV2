from kivy.lang import Builder
from interface.pihomescreen import PiHomeScreen
from services.audio.sfx import SFX
from kivy.properties import ColorProperty, StringProperty, NumericProperty

Builder.load_file("./screens/Task/taskscreen.kv")

class TaskScreen(PiHomeScreen):
    background = ColorProperty((0,0,0,0.7))
    title = StringProperty("<title>")
    description = StringProperty("<message>")
    start_time = NumericProperty(0)
    status = NumericProperty(0)
    priority = NumericProperty(0)
    on_confirm = None
    on_cancel = None

    def __init__(self, **kwargs):
        super(TaskScreen, self).__init__(**kwargs)

    def set_task(self, task):
        self.title = task.name
        self.description = task.description
        # self.start_time = task.start_time
        # self.status = task.status
        # self.priority = task.priority
        self.on_confirm = task.on_confirm
        self.on_cancel = task.on_cancel