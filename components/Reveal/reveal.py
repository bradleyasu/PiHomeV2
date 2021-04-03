from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.animation import Animation
from kivy.core.window import Window

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
            pos = -Window.width/2
            anim = Animation(x=pos, duration=0.3)
            anim.start(self)
            self.__revealed = True

class RevealBottom(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)



class Reveal(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.size_hint_y = .1

        self.__wrapper = FloatLayout()
        self.add_widget(self.__wrapper)

        self.__revealTop = RevealTop()
        self.__revealBottom = RevealBottom()

        self.__wrapper.add_widget(self.__revealBottom)
        self.__wrapper.add_widget(self.__revealTop)


class RevealApp(App):
    def build(self):
        return Reveal()

if __name__ == '__main__':
    RevealApp().run()
