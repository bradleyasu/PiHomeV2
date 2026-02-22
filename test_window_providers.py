#!/usr/bin/env python3
"""
Test different Kivy window providers to see which ones don't interfere with hw:1,0
"""
import os
import sys
import time

def test_window_provider(provider_name, extra_env=None):
    """Test a specific window provider"""
    print(f"\n{'='*60}")
    print(f"Testing window provider: {provider_name}")
    print('='*60)
    
    input(f"Confirm hw:1,0 is working, then press ENTER to test {provider_name}...")
    
    # Start fresh Python process to avoid contamination
    env = os.environ.copy()
    env["KIVY_WINDOW"] = provider_name
    env["SDL_AUDIODRIVER"] = "dummy"
    env["KIVY_AUDIO"] = "sdl2"
    env["KIVY_VIDEO"] = "null"
    env["KIVY_NO_CONSOLELOG"] = "1"
    
    if extra_env:
        env.update(extra_env)
    
    # Create a minimal test script
    test_code = """
import os
from kivy.app import App
from kivy.uix.label import Label
from kivy.clock import Clock

class TestApp(App):
    def build(self):
        Clock.schedule_once(lambda dt: self.stop(), 3)
        return Label(text=f'Testing {provider_name}')

TestApp().run()
print("Test completed")
"""
    
    import subprocess
    proc = subprocess.Popen(
        [sys.executable, '-c', test_code],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    stdout, stderr = proc.communicate()
    
    print(f"\nTest for {provider_name} finished")
    if proc.returncode != 0:
        print(f"ERROR: Exit code {proc.returncode}")
        print("STDERR:", stderr.decode()[-500:])
    
    input(f"Check if hw:1,0 still works after {provider_name}. Press ENTER to continue...")

if __name__ == "__main__":
    print("Window Provider Test")
    print("="*60)
    print("This will test different Kivy window providers")
    print("to find one that doesn't interfere with hw:1,0")
    print("="*60)
    
    providers = [
        ("sdl2", None),
        ("egl_rpi", None),
        ("x11", None),
    ]
    
    for provider, extra_env in providers:
        try:
            test_window_provider(provider, extra_env)
        except KeyboardInterrupt:
            print("\nTest interrupted")
            break
        except Exception as e:
            print(f"ERROR testing {provider}: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60)
    print("\nIdentify which provider(s) don't break hw:1,0,")
    print("then set KIVY_WINDOW to that provider in main.py")
