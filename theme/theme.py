from theme.color import Color
from util.configuration import Configuration
from util.tools import hex
from kivy.clock import Clock
from kivy.core.text import LabelBase

class Theme():
    ''' ENUM VALUES, KEY, DEFAULT_LIGHT, SECTION'''
    COLOR_PRIMARY             = ['primary', Color.GRAY_100, Color.DARK_GRAY_100, 'colors']
    COLOR_SECONDARY           = ['secondary', Color.GRAY_75, Color.DARK_GRAY_75, 'colors']

    BACKGROUND_PRIMARY        = ['primary',Color.GRAY_100, Color.DARK_GRAY_100,  'backgrounds']
    BACKGROUND_SECONDARY      = ['secondary', Color.GRAY_75, Color.DARK_GRAY_75, 'backgrounds']

    TEXT_PRIMARY              = ['primary', Color.GRAY_900, Color.DARK_GRAY_900, 'text']
    TEXT_SECONDARY            = ['secondary', Color.GRAY_800, Color.DARK_GRAY_800, 'text']
    TEXT_DANGER               = ['danger', Color.RED_400, Color.DARK_RED_400, 'text']
    TEXT_SUCCESS              = ['success', Color.GREEN_400, Color.DARK_GREEN_400, 'text']


    BUTTON_PRIMARY            = ['primary', Color.BLUE_400, Color.DARK_BLUE_400, 'buttons']
    BUTTON_SECONDARY          = ['secondary', Color.GRAY_50, Color.DARK_GRAY_50, 'buttons']
    BUTTON_DANGER             = ['danger', '', '', 'buttons']
    BUTTON_SUCCESS            = ['success', '', '', 'buttons']

    ALERT_DANGER              = ['danger', Color.RED_400, Color.DARK_RED_400, 'alerts']
    ALERT_WARNING             = ['warning', Color.ORANGE_400, Color.DARK_ORANGE_400,'alerts']
    ALERT_INFO                = ['info', Color.BLUE_400, Color.DARK_BLUE_400,'alerts']
    ALERT_SUCCESS             = ['success', Color.GREEN_400, Color.DARK_GREEN_400,'alerts']

    def __init__(self, **kwargs):
        super(Theme, self).__init__(**kwargs)
        self.theme  = Configuration('./theme.ini')
        self.mode = Configuration('./base.ini').get_int('theme', 'dark_mode', 0)
        LabelBase.register(name='Nunito', fn_regular='./theme/fonts/Nunito-Regular.ttf')

    def get_color(self, color, opacity = 1):
        if (self.mode == 0):
            key = color[0] + '_light'
            default = color[1]
        else:
            key = color[0] + '_dark'
            default = color[2]

        return hex(str(self.theme.get(color[3], key, default)), opacity)