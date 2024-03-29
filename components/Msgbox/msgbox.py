from kivy.uix.widget import Widget
from kivy.metrics import dp
from kivy.lang import Builder
from kivy.properties import StringProperty, NumericProperty, ColorProperty
from interface.pihomescreenmanager import PIHOME_SCREEN_MANAGER
from services.audio.sfx import SFX
from services.timers.timer import Timer
from kivy.animation import Animation
from components.Button.simplebutton import SimpleButton
import time
from theme.theme import Theme
from kivy.clock import Clock
from kivy.uix.popup import Popup

from util.helpers import get_app

Builder.load_file("./components/Msgbox/msgbox.kv")

MSGBOX_TYPES = {
    "ERROR": 0,
    "WARNING": 1,
    "INFO": 2
}

MSGBOX_BUTTONS = {
    "OK": 0,
    "YES_NO": 1
}


class Msgbox(Widget):
    title = StringProperty("Title")
    message = StringProperty("Message")
    timeout = NumericProperty(0)
    background_color = ColorProperty(Theme().get_color(Theme().COLOR_SECONDARY))
    backdrop_color = ColorProperty(Theme().get_color(Theme().COLOR_PRIMARY, 0.8))
    text_color = ColorProperty(Theme().get_color(Theme().TEXT_PRIMARY))

    type = NumericProperty(2)
    buttons = NumericProperty(0)

    def __init__(self, **kwargs):
        super(Msgbox, self).__init__(**kwargs)
        self.size = (dp(400), dp(200))
    
    def slide_in(self):
        self.pos = (dp(get_app().width /2) - self.width /2, dp(get_app().height))
        self.animate_in()
        if self.type == MSGBOX_TYPES["ERROR"]:
            self.backdrop_color = Theme().get_color(Theme().ALERT_DANGER, 0.8)
            SFX.play("error")
        elif self.type == MSGBOX_TYPES["WARNING"]:
            self.backdrop_color = Theme().get_color(Theme().ALERT_WARNING, 0.8)
        else:
            self.backdrop_color = Theme().get_color(Theme().COLOR_PRIMARY, 0.8)

    def slide_out(self, on_out = None):
        if on_out is not None:
            Clock.schedule_once(lambda _: on_out(), 0.5)
        self.animate_out()

    def animate_in(self):
        animation = Animation(pos=(dp(get_app().width /2) - self.width /2, dp(get_app().height /2) - self.height /2), t='in_back', d=0.5)
        animation.start(self)

    def animate_out(self):
        animation = Animation(pos=(dp(get_app().width /2) - self.width /2, dp(get_app().height)), t='out_back', d=0.5)
        animation.start(self)
        # remove widget after animation
        animation.bind(on_complete=lambda _,widget: widget.parent.remove_widget(widget))

    def set_buttons(self, buttons, on_yes = None, on_no = None):
        self.buttons = buttons
        grid = self.ids.button_grid
        grid.clear_widgets()
        if self.buttons == MSGBOX_BUTTONS["OK"]:
            grid.add_widget(SimpleButton(text="OKAY", size_hint=(0.5,1), on_press=lambda _: self.slide_out()))
        elif self.buttons == MSGBOX_BUTTONS["YES_NO"]:
            grid.add_widget(SimpleButton(text="YES", size_hint=(0.5,1), on_press=lambda _: self.slide_out(on_yes)))
            grid.add_widget(SimpleButton(text="NO", size_hint=(0.5,1), on_press=lambda _: self.slide_out(on_no)))

class MsgboxFactory:
    def __init__(self):
        pass

    def show(self, title, message, timeout, 
             type = MSGBOX_TYPES["INFO"], 
             buttons = MSGBOX_BUTTONS["OK"],
             on_yes= None,
             on_no= None
            ):
        """
        Root is the root widget to add the msgbox to
        """
        self.msgbox = Msgbox()
        self.msgbox.title = title
        self.msgbox.message = message
        self.msgbox.type = type
        self.msgbox.set_buttons(buttons, on_yes, on_no)
        
        # center message box
        self.msgbox.pos = (dp(get_app().width /2) - self.msgbox.width /2, dp(get_app().height /2) - self.msgbox.height /2)
        
        PIHOME_SCREEN_MANAGER.current_screen.add_widget(self.msgbox, index=0)
        self.msgbox.slide_in()
        if timeout > 0:
            Clock.schedule_once(lambda _: self.msgbox.slide_out(), timeout)
        return self.msgbox


MSGBOX_FACTORY = MsgboxFactory()