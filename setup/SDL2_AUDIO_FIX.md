# SDL2 Audio Isolation Fix

This prevents SDL2 from scanning/accessing hw:1,0 (DAC Pro) during Kivy initialization.

## Why This Works

SDL2 ignores environment variables and OS permissions during device enumeration.
The only way to prevent it from corrupting the PCM5122 DAC is to intercept its
audio functions at the library level using LD_PRELOAD.

## Deployment

### 1. Compile the stub library on the Pi

```bash
cd /usr/local/PiHome/setup
gcc -shared -fPIC -o /usr/local/lib/libsdl2_audio_stub.so sdl2_audio_stub.c
```

### 2. Update systemd service to use LD_PRELOAD

Edit `/etc/systemd/system/pihome.service` and add this line in the `[Service]` section:

```ini
Environment="LD_PRELOAD=/usr/local/lib/libsdl2_audio_stub.so"
```

### 3. Reload and restart

```bash
sudo systemctl daemon-reload
sudo systemctl restart pihome
```

## How It Works

- `LD_PRELOAD` loads our stub library before SDL2
- When SDL2 calls `SDL_GetNumAudioDevices()`, our stub returns 0
- SDL2 thinks there are no audio devices, skips enumeration
- hw:1,0 (DAC Pro) is never touched, remains functional for shairport-sync

## Testing

While PiHome is running:

```bash
speaker-test -D hw:1,0 -c 2 -t sine -l 1
```

You should hear audio from the DAC.
