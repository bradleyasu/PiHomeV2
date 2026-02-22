#!/usr/bin/env python3
"""
Minimal PiHome app that exits after 10 seconds to test if App itself breaks hw:1,0
"""
import os
import sys
import platform

# Must set BEFORE importing Kivy
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["KIVY_AUDIO"] = "sdl2"
os.environ["KIVY_VIDEO"] = "null"
os.environ["AUDIODEV"] = "/dev/null"
# Only use egl_rpi on Linux (Raspberry Pi)
if platform.system() == 'Linux':
    os.environ["KIVY_WINDOW"] = "egl_rpi"

print("Starting minimal PiHome app for 10 seconds...")
print("="*60)

from kivy.app import App
from kivy.clock import Clock
from kivy.uix.label import Label
from kivy.config import Config

Config.set('kivy', 'keyboard_mode', 'systemandmulti')
Config.set('graphics', 'verify_gl_main_thread', '0')

# Import PiHome modules that initialize on import
print("Importing PiHome modules...")
from services.audio.audioplayernew import AUDIO_PLAYER
from services.audio.sfx import SFX
from interface.pihomescreenmanager import PIHOME_SCREEN_MANAGER

print("Modules imported successfully")

class MinimalPiHomeTest(App):
    def build(self):
        print("App build() called")
        print(f"AUDIO_PLAYER device: {AUDIO_PLAYER.device}")
        print(f"SFX device: {SFX.device}")
        
        # Schedule exit after 10 seconds
        Clock.schedule_once(lambda dt: self.stop(), 10)
        
        return Label(text='Minimal PiHome Test\nWill exit in 10 seconds')
    
    def on_start(self):
        print("App started - check hw:1,0 now")
    
    def on_stop(self):
        print("App stopping - cleaning up...")
        AUDIO_PLAYER.cleanup()
        SFX.cleanup()
        return True

if __name__ == '__main__':
    print("="*60)
    input("Confirm hw:1,0 works, then press ENTER to start app...")
    MinimalPiHomeTest().run()
    print("="*60)
    print("App exited - check if hw:1,0 still works")
