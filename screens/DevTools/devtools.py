from datetime import datetime, timedelta
import socket
from kivy.lang import Builder
from kivy.uix.floatlayout import FloatLayout
from kivy.metrics import dp
from kivy.properties import ColorProperty, StringProperty,ObjectProperty, NumericProperty


from kivy.core.audio import SoundLoader
from components.Button.circlebutton import CircleButton
from components.Button.simplebutton import SimpleButton
from components.Image.networkimage import NetworkImage
from components.Msgbox.msgbox import MSGBOX_FACTORY
from components.Slider.slidecontrol import SlideControl
from components.SmartLight.smartlight import SmartLight
from components.Switch.switch import PiHomeSwitch
from composites.ControlPanel.controlpanel import CONTROL_PANEL
from interface.pihomescreen import PiHomeScreen
from interface.pihomescreenmanager import PIHOME_SCREEN_MANAGER
from server.server import SERVER
from services.audio.audioplayer import AUDIO_PLAYER
from services.qr.qr import QR
from services.taskmanager.taskmanager import TASK_MANAGER, Task, TaskPriority, TaskStatus
from system.brightness import set_brightness
from theme.color import Color
from theme.theme import Theme
from kivy.factory import Factory
from util.const import SERVER_PORT
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
        button.bind(on_release=lambda _: PIHOME_SCREEN_MANAGER.goto("_shutdown"))
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

        # self.serverButton = CircleButton(text='TOGGLE SERVER', size=(dp(50), dp(50)), pos=(dp(130), dp(self.height - 200)))
        # self.serverButton.stroke_color = self.theme.get_color(self.theme.ALERT_WARNING)
        # self.serverButton.text_color = self.theme.get_color(self.theme.ALERT_WARNING)
        # self.serverButton.down_color = self.theme.get_color(self.theme.ALERT_WARNING, 0.2)
        # self.serverButton.bind(on_release=lambda _: self.toggle_server())
        # layout.add_widget(self.serverButton)

        # self.control_panel = SimpleButton(text="Control Panel", size=(dp(200), dp(50)), pos=(dp(90), dp(20)))
        # self.control_panel.bind(on_release=lambda _: CONTROL_PANEL.open())
        # layout.add_widget(self.control_panel)
        
        # self.goback = SimpleButton(text="GO BACK", size=(dp(200), dp(50)), pos=(dp(90), dp(20)))
        # self.goback.bind(on_release=lambda _: self.go_back())
        # layout.add_widget(self.goback)


        def delete_cache(self):
            TASK_MANAGER.delete_task_cache()
            MSGBOX_FACTORY.show("Task Cache Deleted", "Task Cache Deleted", 10, 0, 0)
        
        self.delete_tasks = SimpleButton(text="Delete Tasks Cache", size=(dp(200), dp(50)), pos=(dp(300), dp(80)))
        self.delete_tasks.bind(on_release=delete_cache)
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
        AUDIO_PLAYER.play("./assets/audio/notify/001.mp3")

    def stop_sound(self):
        AUDIO_PLAYER.stop()

    def toggle_server(self):
        if SERVER.is_online():
            SERVER.stop_server()
        else:
            SERVER.start_server()


    def on_enter(self, *args):
        url = "https://rr3---sn-8xgp1vo-2pul.googlevideo.com/videoplayback?expire=1709337780&ei=VBjiZdeJFeG9_9EP3J2AiA8&ip=74.109.241.148&id=o-ALLuUo5hmYuUdLSWnmmfJedi9hpY8h8b58OCsN-HQCpc&itag=251&source=youtube&requiressl=yes&xpc=EgVo2aDSNQ%3D%3D&mh=Nn&mm=31%2C29&mn=sn-8xgp1vo-2pul%2Csn-8xgp1vo-p5qe&ms=au%2Crdu&mv=m&mvi=3&pl=18&gcr=us&initcwndbps=898750&spc=UWF9fzggasD4niyPJNKYKiVzKvYnUtZ3cbXFjsryDK4EqWs&vprv=1&svpuc=1&mime=audio%2Fwebm&gir=yes&clen=4391306&dur=278.361&lmt=1706308899802101&mt=1709315833&fvip=6&keepalive=yes&fexp=24007246&c=ANDROID&txp=4532434&sparams=expire%2Cei%2Cip%2Cid%2Citag%2Csource%2Crequiressl%2Cxpc%2Cgcr%2Cspc%2Cvprv%2Csvpuc%2Cmime%2Cgir%2Cclen%2Cdur%2Clmt&sig=AJfQdSswRQIgQE0R0uwDzqSxnuX_9B5vtfx8_LsUlvvH__bxjLVujp0CIQCqe4oUM7hOdBOkc0gk2h60UCK-yyZZWEr08oao6fIMpw%3D%3D&lsparams=mh%2Cmm%2Cmn%2Cms%2Cmv%2Cmvi%2Cpl%2Cinitcwndbps&lsig=APTiJQcwRgIhAPaaWdV0tV5FkPYOpHN82ZKBLn27S6Dc79TMTJQigrf4AiEAq5jcfnMox5ToATXrgG4QcMyMGSUSgOOlA7yI06Rp0nY%3D&fmt=.mp3"
        self.sound = SoundLoader.load(url)
        self.sound.play()
        return super().on_enter(*args)

    def on_leave(self, *args):
        if self.sound:
            self.sound.stop()
            self.sound.unload()
        return super().on_leave(*args)

