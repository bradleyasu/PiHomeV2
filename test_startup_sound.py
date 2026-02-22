#!/usr/bin/env python3
"""
Test if the startup sound effect or full PiHome initialization breaks hw:1,0
"""
import os
import sys
import time

# Set environment variables BEFORE importing anything
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["KIVY_AUDIO"] = "sdl2"
os.environ["KIVY_VIDEO"] = "null"
os.environ["KIVY_NO_CONSOLELOG"] = "1"

print("="*60)
print("Testing PiHome Startup Sound Effect")
print("="*60)

input("\n1. Confirm hw:1,0 is working (speaker-test -D hw:1,0), then press ENTER...")

print("\n2. Importing PiHome SFX module...")
from services.audio.sfx import SFX
print("   SFX imported successfully")

print(f"\n3. SFX device configured as: {SFX.device}")

input("\n   Check if hw:1,0 STILL works now. Press ENTER to continue...")

print("\n4. Playing 'startup' sound effect...")
try:
    SFX.play("startup")
    print("   Sound effect play() called")
    time.sleep(3)  # Wait for sound to play
    print("   Waiting complete")
except Exception as e:
    print(f"   ERROR: {e}")

input("\n5. Check if hw:1,0 STILL works after sound. Press ENTER to continue...")

print("\n6. Stopping all SFX...")
SFX.cleanup()

print("\n7. Testing with actual ffmpeg command that SFX uses...")
import subprocess
startup_file = SFX.SOURCES.get("startup")
if startup_file:
    print(f"   Startup file: {startup_file}")
    print(f"   Running: ffmpeg -i {startup_file} -f alsa hw:0,0")
    
    proc = subprocess.Popen(
        ['ffmpeg', '-i', startup_file, '-f', 'alsa', '-loglevel', 'quiet', 'hw:0,0'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL
    )
    proc.wait()
    print("   ffmpeg process completed")
else:
    print("   WARNING: startup sound file not found")

input("\n8. Check if hw:1,0 STILL works after direct ffmpeg. Press ENTER to continue...")

print("\n" + "="*60)
print("TEST COMPLETE - Summary:")
print("="*60)
print("\nIf hw:1,0 stopped working:")
print(" - After step 2: Issue is with importing SFX or its dependencies")
print(" - After step 4: Issue is with SFX.play() method")  
print(" - After step 7: Issue is with the specific ffmpeg command for audio files")
print("\nIf hw:1,0 never stopped: Issue is elsewhere in PiHome initialization")
print("="*60)
