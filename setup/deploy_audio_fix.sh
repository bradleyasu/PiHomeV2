#!/bin/bash
# Deploy SDL2 audio stub to prevent DAC corruption

set -e

echo "=== Deploying SDL2 Audio Stub ==="
echo ""

# Check if running on Pi
if [ ! -f /proc/device-tree/model ] || ! grep -q "Raspberry Pi" /proc/device-tree/model; then
    echo "Warning: This doesn't appear to be a Raspberry Pi"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Compile stub library
echo "[1/4] Compiling SDL2 audio stub library..."
if [ ! -f sdl2_audio_stub.c ]; then
    echo "Error: sdl2_audio_stub.c not found"
    exit 1
fi

gcc -shared -fPIC -o /tmp/libsdl2_audio_stub.so sdl2_audio_stub.c
if [ $? -ne 0 ]; then
    echo "Error: Compilation failed"
    exit 1
fi
echo "✓ Compiled successfully"

# Install library
echo "[2/4] Installing stub library..."
sudo cp /tmp/libsdl2_audio_stub.so /usr/local/lib/
sudo chmod 644 /usr/local/lib/libsdl2_audio_stub.so
echo "✓ Installed to /usr/local/lib/libsdl2_audio_stub.so"

# Update service file
echo "[3/4] Updating systemd service..."
sudo cp pihome.service /etc/systemd/system/
sudo systemctl daemon-reload
echo "✓ Service file updated"

# Test
echo "[4/4] Verifying stub library..."
if [ -f /usr/local/lib/libsdl2_audio_stub.so ]; then
    echo "✓ Stub library installed correctly"
else
    echo "✗ Stub library not found"
    exit 1
fi

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "The SDL2 audio stub is now active. This prevents SDL2 from"
echo "scanning/corrupting hw:1,0 (DAC Pro)."
echo ""
echo "Next steps:"
echo "  1. Restart PiHome: sudo systemctl restart pihome"
echo "  2. Test DAC while PiHome runs: speaker-test -D hw:1,0 -c 2 -t sine -l 1"
echo ""
