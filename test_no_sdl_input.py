#!/usr/bin/env python3
"""
Attempt to use Kivy with ZERO SDL2 initialization by configuring input providers manually
"""
import os
import sys

# Set environment BEFORE imports
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["KIVY_AUDIO"] = "sdl2"
os.environ["KIVY_VIDEO"] = "null"
os.environ["KIVY_WINDOW"] = "egl_rpi"
os.environ["AUDIODEV"] = "/dev/null"

print("Testing Kivy with manual input configuration (no SDL2 auto-add)")
print("="*60)

input("Confirm hw:1,0 is working, then press ENTER...")

from kivy.config import Config

# Disable SDL2 input auto-add
print("\n1. Configuring Kivy to NOT auto-add SDL2 input...")
# We'll try to prevent the auto-add by using mtdev directly
Config.set('input', 'mouse', 'mouse')
# Config.remove_option('input', 'sdl2')  # Can't remove, but we can try not adding

from kivy.app import App
from kivy.uix.label import Label
from kivy.clock import Clock

class NoSDLTest(App):
    def build(self):
        print("2. App.build() called")
        print(f"   Window provider will be: egl_rpi")
        Clock.schedule_once(lambda dt: self.stop(), 5)
        return Label(text='Testing without SDL2 input\\nExits in 5 seconds')
    
    def on_start(self):
        print("3. App started - Window created")
        print("   Check hw:1,0 now!")

print("\nStarting app...")
NoSDLTest().run()

print("\n" + "="*60)
input("App exited. Check if hw:1,0 still works. Press ENTER...")
print("="*60)
