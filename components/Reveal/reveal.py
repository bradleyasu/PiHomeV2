from random import randint

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.relativelayout import RelativeLayout

from kivy.animation import Animation
from kivy.core.window import Window
from kivy.lang import Builder

Builder.load_file("./components/Reveal/reveal.kv")

class RevealTop(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.__revealed = None
        self.__open = None
        self.__moved = None

    def on_touch_down(self, touch):
        if self.collide_point(touch.x, touch.y):
            if self.__open:
                return False

            touch.grab(self)
            return True
        return False

    def on_touch_move(self, touch):
        if self.collide_point(touch.x, touch.y):
            if self.__moved:
                return False
            if self.__open:
                self.__open = None
            else:
                self.__open = True

            self.reveal()
            self.__moved = True

    def on_touch_up(self, touch):
        if self.collide_point(touch.x, touch.y):
            touch.ungrab(self)
            self.__moved = None

            return True
        return False

    def reveal(self):
        if self.__revealed:
            pos = 0
            anim = Animation(x=pos, duration=0.3)
            anim.start(self)
            self.__revealed = False
        else:
            pos = -self.width/2
            anim = Animation(x=pos, duration=0.3)
            anim.start(self)
            self.__revealed = True

class RevealBottom(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def add_child(self, child):
        self.ids.parent_bottom.add_widget(child)


class Reveal(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.__wrapper = RelativeLayout()

        self.add_widget(self.__wrapper)

        self.__revealTop = RevealTop()
        self.__revealBottom = RevealBottom()

        self.__wrapper.add_widget(self.__revealBottom)
        self.__wrapper.add_widget(self.__revealTop)

    def add_top_widget(self, widget):
        self.__revealTop.add_widget(widget)

    def add_bottom_widget(self, widget):
        self.__revealBottom.add_child(widget)




# For testing python ./reveal.py -size WxH
class RevealApp(App):
    def build(self):
        return Reveal()

if __name__ == '__main__':
    RevealApp().run()
