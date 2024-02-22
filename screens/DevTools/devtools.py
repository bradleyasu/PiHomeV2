from datetime import datetime, timedelta
import socket
from kivy.lang import Builder
from kivy.uix.floatlayout import FloatLayout
from kivy.metrics import dp
from kivy.properties import ColorProperty, StringProperty,ObjectProperty, NumericProperty

from components.Button.circlebutton import CircleButton
from components.Button.simplebutton import SimpleButton
from components.Image.networkimage import NetworkImage
from components.Slider.slidecontrol import SlideControl
from components.SmartLight.smartlight import SmartLight
from components.Switch.switch import PiHomeSwitch
from composites.ControlPanel.controlpanel import CONTROL_PANEL
from interface.pihomescreen import PiHomeScreen
from server.server import SERVER
from services.qr.qr import QR
from services.taskmanager.taskmanager import TASK_MANAGER, Task, TaskPriority, TaskStatus
from system.brightness import set_brightness
from theme.color import Color
from theme.theme import Theme
from kivy.factory import Factory
from util.const import SERVER_PORT
from util.helpers import appmenu_open, audio_player, get_app, goto_screen, update_pihome
from util.tools import hex
from kivy.clock import Clock
from kivy.animation import Animation
from kivy.uix.label import Label
from services.timers.timer import Timer
from components.PihomeTimer.pihometimer import PiHomeTimer

from mplayer import Player

Builder.load_file("./screens/DevTools/devtools.kv")

class DevTools(PiHomeScreen):
    local_ip = StringProperty("0.0.0.0")
    theme = Theme()
    slider = None
    def __init__(self, **kwargs):
        super(DevTools, self).__init__(**kwargs)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        self.local_ip = s.getsockname()[0]
        s.close()
        self.build()

    
    def build(self):
        layout = FloatLayout(size=(dp(800), dp(600)))

        button = CircleButton(text='X', size=(dp(50), dp(50)), pos=(dp(self.width - 70), dp(self.height - 200)))
        button.stroke_color = self.theme.get_color(self.theme.ALERT_DANGER)
        button.text_color = self.theme.get_color(self.theme.ALERT_DANGER)
        button.down_color = self.theme.get_color(self.theme.ALERT_DANGER, 0.2)
        button.bind(on_release=lambda _: update_pihome())
        layout.add_widget(button)

        # timer = Timer(10)
        # timer_widget = PiHomeTimer(timer=timer, display_text="TimerText")
        # layout.add_widget(timer_widget)

        # stopbutton = CircleButton(text='T', size=(dp(140), dp(50)), pos=(dp(20), dp(self.height - 200)))
        # stopbutton.stroke_color = self.theme.get_color(self.theme.ALERT_SUCCESS)
        # stopbutton.text_color = self.theme.get_color(self.theme.ALERT_SUCCESS)
        # stopbutton.down_color = self.theme.get_color(self.theme.ALERT_SUCCESS, 0.2)
        # stopbutton.bind(on_release=lambda _: timer_widget.start())
        # layout.add_widget(stopbutton)

        # switch = PiHomeSwitch(pos=(dp(20), dp(20)))
        # layout.add_widget(switch)

        self.serverButton = CircleButton(text='TOGGLE SERVER', size=(dp(50), dp(50)), pos=(dp(130), dp(self.height - 200)))
        self.serverButton.stroke_color = self.theme.get_color(self.theme.ALERT_WARNING)
        self.serverButton.text_color = self.theme.get_color(self.theme.ALERT_WARNING)
        self.serverButton.down_color = self.theme.get_color(self.theme.ALERT_WARNING, 0.2)
        self.serverButton.bind(on_release=lambda _: self.toggle_server())
        layout.add_widget(self.serverButton)

        # self.control_panel = SimpleButton(text="Control Panel", size=(dp(200), dp(50)), pos=(dp(90), dp(20)))
        # self.control_panel.bind(on_release=lambda _: CONTROL_PANEL.open())
        # layout.add_widget(self.control_panel)
        
        self.goback = SimpleButton(text="GO BACK", size=(dp(200), dp(50)), pos=(dp(90), dp(20)))
        self.goback.bind(on_release=lambda _: self.go_back())
        layout.add_widget(self.goback)


        
        self.delete_tasks = SimpleButton(text="Delete All Tasks", size=(dp(200), dp(50)), pos=(dp(300), dp(80)))
        self.delete_tasks.bind(on_release=lambda _: TASK_MANAGER.delete_task_cache())
        layout.add_widget(self.delete_tasks)


        # slider = SlideControl(size=(dp(20), dp(200)), pos=(dp(500), dp(100)))
        # slider.add_listener(lambda value: set_brightness(value))
        # slider.background_color = hex(Color.CHARTREUSE_600, 0.1)
        # slider.active_color = hex(Color.DARK_CHARTREUSE_700)
        # layout.add_widget(slider)


        qr = QR().from_url("http://{}:{}".format(self.local_ip, SERVER_PORT))
        qr_img = NetworkImage(qr, size=(dp(256), dp(256)), pos=(dp(100), dp(100)))
        # center the qr code
        qr_img.pos = (dp((self.width - qr_img.width) / 2), dp((self.height - qr_img.height) / 2))
        # round the corners
        qr_img.radius = (dp(20), dp(20), dp(20), dp(20))
        layout.add_widget(qr_img)
        # url = ""
        # player = VideoPlayer(source=url, state='play', options={'allow_stretch': True})
        # layout.add_widget(player)

        # self.slider = Slider(on_touch_move=lambda x,y: self.set_brightness(self.slider.value), orientation='horizontal', min=20, max = 255, pos=(dp(self.width - 10), dp(self.height - 100)), size=(dp(40), dp(200)), step=1)
        # layout.add_widget(self.slider)
        
        self.add_widget(layout)

    
    def set_brightness(self, level):
        # echo 32 > /sys/class/backlight/rpi_backlight/brightness
        # subprocess.call(['sh', './set_brightness.sh', level])
        print(level)

    def play_sound(self):
        audio_player().play("./assets/audio/notify/001.mp3")

    def stop_sound(self):
        audio_player().stop()

    def toggle_server(self):
        if SERVER.is_online():
            SERVER.stop_server()
        else:
            SERVER.start_server()
