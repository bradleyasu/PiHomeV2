from util.configuration import Configuration
from util.tools import hex
from kivy.clock import Clock

class Theme():
    ''' ENUM VALUES, KEY, DEFAULT_LIGHT, SECTION'''
    COLOR_PRIMARY       = ['primary', '#FFFFFF', '#424242', 'colors']
    COLOR_SECONDARY     = ['secondary', '#eaeaea', '#424242', 'colors']

    ALERT_DANER         = ['danger', '#FF0000', '#FF0000', 'alerts']
    ALERT_WARNING       = ['warning', '#FF0000', '#FF0000','alerts']
    ALERT_CAUTION       = ['caution', '#FF0000', '#FF0000','alerts']
    ALERT_SUCCESS       = ['success', '#FF0000', '#FF0000','alerts']

    def __init__(self, **kwargs):
        super(Theme, self).__init__(**kwargs)
        self.theme  = Configuration('./theme.ini')
        self.mode = Configuration('./base.ini').get_int('theme', 'dark_mode', 0)

    def get_color(self, color, opacity = 1):
        if (self.mode == 0):
            key = color[0] + '_light'
            default = color[1]
        else:
            key = color[0] + '_dark'
            default = color[2]

        return hex(str(self.theme.get(color[3], key, default)), opacity)