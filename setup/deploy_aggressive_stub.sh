#!/bin/bash
# Deploy AGGRESSIVE card1 blocker stub

set -e

echo "========================================="
echo " AGGRESSIVE CARD1 BLOCKER DEPLOYMENT"
echo "========================================="
echo ""

cd /usr/local/PiHome/setup

# Step 1: Compile the stub with all optimizations
echo "[1/6] Compiling aggressive stub library..."
gcc -shared -fPIC -Wl,--no-as-needed -o /tmp/libsdl2_audio_stub.so sdl2_audio_stub.c -ldl
if [ $? -ne 0 ]; then
    echo "✗ Compilation failed!"
    exit 1
fi
echo "✓ Compiled successfully"

#Step 2: Install to system
echo "[2/6] Installing to /usr/local/lib/..."
sudo cp /tmp/libsdl2_audio_stub.so /usr/local/lib/
sudo chmod 644 /usr/local/lib/libsdl2_audio_stub.so
echo "✓ Installed"

# Step 3: Verify exported symbols
echo "[3/6] Verifying exported symbols..."
SYMBOLS=$(nm -D /usr/local/lib/libsdl2_audio_stub.so | grep -E "open|fopen|access|stat|readlink" | wc -l)
echo "✓ Found $SYMBOLS interception functions"

# Step 4: Update service file
echo "[4/6] Updating systemd service..."
if ! grep -q "LD_PRELOAD" /etc/systemd/system/pihome.service; then
    echo "⚠ Adding LD_PRELOAD to service file..."
    sudo sed -i '/\[Service\]/a Environment="LD_PRELOAD=/usr/local/lib/libsdl2_audio_stub.so"' /etc/systemd/system/pihome.service
fi
sudo systemctl daemon-reload
echo "✓ Service updated"

# Step 5: Test the stub manually
echo "[5/6] Testing stub interception..."
TEST_RESULT=$(LD_PRELOAD=/usr/local/lib/libsdl2_audio_stub.so python3 -c "
try:
    open('/sys/devices/platform/soc/soc:sound/sound/card1/uevent', 'r')
    print('FAIL')
except FileNotFoundError:
    print('PASS')
except Exception as e:
    print('ERROR')
" 2>&1)

if [ "$TEST_RESULT" = "PASS" ]; then
    echo "✓ Stub is working correctly!"
else
    echo "✗ Stub test failed: $TEST_RESULT"
    echo "  This might still work in systemd context"
fi

# Step 6: Restart PiHome
echo "[6/6] Restarting PiHome service..."
sudo systemctl restart pihome
sleep 5

# Final verification
echo ""
echo "========================================="
echo " VERIFICATION"
echo "========================================="

# Check if stub is loaded
if sudo cat /proc/$(pgrep -f "python3.*main.py")/maps | grep -q sdl2_audio_stub; then
    echo "✓ Stub loaded in PiHome process"
else
    echo "✗ Stub NOT loaded in PiHome process"
fi

# Check for uevent errors
RECENT_ERRORS=$(dmesg -T | grep -i "card1.*uevent" | tail -2)
if echo "$RECENT_ERRORS" | grep -q "$(date '+%b %e %H:')"; then
    echo "✗ New card1 uevent errors detected:"
    echo "$RECENT_ERRORS"
else
    echo "✓ No recent card1 uevent errors!"
fi

# Test DAC
echo ""
echo "Testing DAC (hw:1,0)..."
if speaker-test -D hw:1,0 -c 2 -t sine -l 1 > /dev/null 2>&1; then
    echo "✓ DAC is working!"
else
    echo "✗ DAC is not working"
fi

echo ""
echo "========================================="
echo " DEPLOYMENT COMPLETE"
echo "========================================="
echo ""
echo "If DAC still doesn't work, enable debug mode:"
echo "  1. Edit sdl2_audio_stub.c"
echo "  2. Uncomment: // #define DEBUG_STUB 1"
echo "  3. Rerun this script"
echo "  4. Check: sudo journalctl -u pihome -f"
echo ""
