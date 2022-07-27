from kivy.app import App

def get_app():
    return App.get_running_app()

def get_config():
    return get_app().get_config()

def get_poller():
    return get_app().get_poller()

def goto_screen(screen, pin_required = False):
    get_app().goto_screen(screen, pin_required)