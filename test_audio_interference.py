#!/usr/bin/env python3
"""
Minimal test to determine what causes hw:1,0 interference.
Run this on the Raspberry Pi to test different scenarios.
"""
import os
import subprocess
import time
import sys

def test_case(name, func):
    """Run a test case and report results"""
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print('='*60)
    input("Press ENTER when hw:1,0 is confirmed working (check with speaker-test)...")
    
    print(f"Running test...")
    func()
    
    input(f"Test complete. Check if hw:1,0 still works. Press ENTER to continue...")
    print()

def test_only_ffmpeg():
    """Test 1: Just ffmpeg to hw:0,0, no Kivy"""
    print("Playing 5 seconds of silence to hw:0,0 using ffmpeg...")
    proc = subprocess.Popen([
        'ffmpeg', '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo',
        '-t', '5', '-f', 'alsa', 'hw:0,0'
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    proc.wait()
    print("ffmpeg finished")

def test_sdl_with_dummy():
    """Test 2: Import Kivy with SDL_AUDIODRIVER=dummy"""
    print("Setting SDL_AUDIODRIVER=dummy and importing Kivy...")
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    os.environ["KIVY_AUDIO"] = "sdl2"
    os.environ["KIVY_VIDEO"] = "null"
    os.environ["KIVY_NO_CONSOLELOG"] = "1"
    
    import kivy
    from kivy.app import App
    from kivy.uix.label import Label
    
    class TestApp(App):
        def build(self):
            return Label(text='Test')
    
    print("Kivy imported, creating window (will exit after 3  seconds)...")
    from kivy.clock import Clock
    app = TestApp()
    Clock.schedule_once(lambda dt: app.stop(), 3)
    app.run()
    print("Kivy app finished")

def test_full_imports():
    """Test 3: Import everything like main.py does"""
    print("Importing all PiHome modules...")
    # Set environment like main.py
    os.environ["KIVY_AUDIO"] = "sdl2"
    os.environ["KIVY_VIDEO"] = "null"
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    
    # Import heavy imports from main.py
    from kivy.config import Config
    from kivy.core.window import Window
    from kivy.clock import Clock
    import kivy
    
    print("All imports complete (no app started)")
    time.sleep(3)

if __name__ == "__main__":
    print("Audio Interference Diagnostic Tool")
    print("="*60)
    print("This will help identify what causes hw:1,0 to stop working.")
    print()
    print("Before each test, make sure hw:1,0 is working:")
    print("  speaker-test -D hw:1,0 -c 2 -t wav")
    print()
    print("After each test, check if hw:1,0 still works.")
    print("="*60)
    
    tests = [
        ("1. FFmpeg to hw:0,0 (no Kivy)", test_only_ffmpeg),
        ("2. Kivy with SDL_AUDIODRIVER=dummy", test_sdl_with_dummy),
        ("3. Full PiHome imports (no app run)", test_full_imports),
    ]
    
    for name, func in tests:
        try:
            test_case(name, func)
        except Exception as e:
            print(f"ERROR in test: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*60)
    print("DIAGNOSTIC COMPLETE")
    print("="*60)
    print("\nResults will help identify the root cause:")
    print("- If Test 1 breaks hw:1,0: Issue is with ALSA/hardware when accessing hw:0,0")
    print("- If Test 2 breaks hw:1,0: Issue is with SDL/Kivy initialization")
    print("- If Test 3 breaks hw:1,0: Issue is with a specific PiHome import")
