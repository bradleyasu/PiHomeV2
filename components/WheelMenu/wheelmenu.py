from math import radians, cos, sin
from kivy.app import App
from kivy.lang import Builder
from kivy.uix.behaviors import ButtonBehavior 
from kivy.uix.image import AsyncImage  
from kivy.uix.label import Label
from interface.gesturewidget import GestureWidget
from theme.theme import Theme
from kivy.properties import BooleanProperty, ColorProperty, NumericProperty, StringProperty, ListProperty, ObjectProperty
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.uix.widget import Widget
from kivy.metrics import dp
from kivy.graphics import Color, Line, Ellipse
from kivy.uix.image import Image

from util.helpers import calculate_angle, get_app, select_item_by_degree

Builder.load_file("./components/WheelMenu/wheelmenu.kv")

class WheelMenu(Widget):

    is_open = BooleanProperty(False)
    max_radius = NumericProperty(100)
    min_radius = NumericProperty(40)
    radius = NumericProperty(40)

    drag_x = NumericProperty(0)
    drag_y = NumericProperty(0)
    drag_opacity = NumericProperty(0)

    arc_pos = NumericProperty(0)
    arc_offset = NumericProperty(90)

    icon = StringProperty("./components/WheelMenu/fp.png")
    icon_size = NumericProperty(50)
    icon_opacity = NumericProperty(1)

    display_text = StringProperty("")

    options = ListProperty([])
    selected_index = NumericProperty(0)

    def __init__(self, **kwargs):
        super(WheelMenu, self).__init__(**kwargs)
        self.drag_x = self.center_x
        self.drag_y = self.center_y
        Clock.schedule_interval(lambda _: self.run(), 0.05)


    def on_is_open(self, instance, value):
        if value:
            # self.radius = self.max_radius
            self.open_animation()
            self.display_pies()
        else:
            # self.radius = self.min_radius
            self.close_animation()

    def set_selected(self, item, index):
        self.display_text = item['text']
        self.selected_index = index

    def activate_selected(self, item):
        self.display_text = ""
        # call the callback function in item
        item[0]['callback']()

    def open_animation(self):
        animation = Animation(arc_offset=370, t='out_elastic', d=0.25)
        animation &= Animation(radius=self.max_radius, t='out_elastic', d=0.30)
        animation.start(self)
        self.display_pies()
        self.icon_opacity = 0

    def close_animation(self):
        animation = Animation(arc_offset=90, t='out_elastic', d=0.25)
        animation &= Animation(radius=self.min_radius, t='out_elastic', d=0.30)
        animation.start(self)
        self.icon_opacity = 1
        self.hide_pies()

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.is_open = True
            self.drag_x, self.drag_y = touch.pos
            self.drag_opacity = 1
            return False


    def on_touch_move(self, touch):
        if self.is_open:
            self.drag_x, self.drag_y = touch.pos
            angle = calculate_angle(self.center_x, self.center_y, touch.pos[0], touch.pos[1])
            item, index = select_item_by_degree(self.options, angle)
            self.set_selected(item, index)
        # return super().on_touch_move(touch)
        return False

    def on_touch_up(self, touch):
        if self.is_open:
            self.is_open = False
            self.drag_x = self.center_x
            self.drag_y = self.center_y
            self.drag_opacity = 0
            self.activate_selected(select_item_by_degree(self.options, calculate_angle(self.center_x, self.center_y, touch.pos[0], touch.pos[1])))
            return False

    def display_pies(self):
        items = self.options
        num_items = len(items)
        if num_items == 0:
            return
        
        angle_per_item = (360 / num_items)

        for i, item in enumerate(items):
            start_angle = i * angle_per_item + 90
            end_angle = (i + 1) * angle_per_item + 90

            start_x = self.center_x + dp(self.max_radius) * cos(radians(start_angle))
            start_y = self.center_y + dp(self.max_radius) * sin(radians(start_angle))
            end_x = self.center_x+ dp(self.max_radius) * cos(radians(end_angle))
            end_y = self.center_y + dp(self.max_radius) * sin(radians(end_angle))

            item['start_x'] = start_x
            item['start_y'] = start_y
            item['end_x'] = end_x
            item['end_y'] = end_y

            with self.canvas.after:
                Color(0, 1, 0, 1)  # Set color to red

                # Outline border
                # Line(circle=(self.center_x, self.center_y, dp(self.max_radius), start_angle, end_angle), width=2)
                # Add lines to separate the pie slices
                Color(1, 1, 1, 1)  # Set color to black
                Line(points=[
                    self.center_x, self.center_y,
                    start_x, start_y,
                ])
                Line(points=[
                    end_x, end_y,
                    self.center_x, self.center_y,
                ])

                mid_x = (start_x + end_x) / 2
                mid_y = (start_y + end_y) / 2

                # this is dumb, get the next item in the list and if the next item exceeds the index, loop to the start of the array
                next_item = items[(i) % len(items)]

                Image(
                    source=next_item['icon'], 
                    pos=(mid_x - dp(self.max_radius) / (2 * len(self.options)), mid_y - dp(self.max_radius) / (2 * len(self.options))), 
                    size=(dp(self.max_radius * 2) / len(self.options), dp(self.max_radius * 2) / len(self.options)), 
                    opacity=self.icon_opacity,
                    allow_stretch=True
                )

    def hide_pies(self):
        self.canvas.after.clear()  # Clear previous canvas instructions
    

    def run(self):
        self.arc_pos = self.arc_pos + 10
        if self.arc_pos >= 360:
            self.arc_pos = 0


        # if self.is_open and self.arc_offset <= 380:
        #     self.arc_offset = self.arc_offset + 45 
        # elif self.arc_offset > 90:
        #     self.arc_offset = self.arc_offset - 45