#!/bin/bash
# Test that openat() interception blocks card1 sysfs access

set -e

echo "=== Testing sysfs card1 blocking ==="
echo ""

# Compile the stub if needed
if [ ! -f /usr/local/lib/libsdl2_audio_stub.so ] || [ sdl2_audio_stub.c -nt /usr/local/lib/libsdl2_audio_stub.so ]; then
    echo "Compiling updated stub library..."
    gcc -shared -fPIC -o /tmp/libsdl2_audio_stub.so sdl2_audio_stub.c -ldl
    sudo cp /tmp/libsdl2_audio_stub.so /usr/local/lib/
    echo "✓ Stub compiled and installed"
    echo ""
fi

# Test 1: Normal access to card1 (should work)
echo "[Test 1] Normal access to card1 sysfs (without stub):"
if cat /sys/devices/platform/soc/soc:sound/sound/card1/uevent > /dev/null 2>&1; then
    echo "✓ card1 uevent is readable (expected)"
else
    echo "✗ card1 uevent not readable (unexpected)"
fi

# Test 2: Access with LD_PRELOAD (should be blocked)
echo ""
echo "[Test 2] Access to card1 sysfs WITH stub (should be blocked):"
LD_PRELOAD=/usr/local/lib/libsdl2_audio_stub.so cat /sys/devices/platform/soc/soc:sound/sound/card1/uevent 2>&1 | grep -q "No such file" && echo "✓ card1 access blocked (expected)" || echo "✗ card1 still accessible (PROBLEM)"

# Test 3: Access to card0 should still work
echo ""
echo "[Test 3] Access to card0 sysfs WITH stub (should still work):"
if LD_PRELOAD=/usr/local/lib/libsdl2_audio_stub.so cat /sys/devices/platform/soc/soc:sound/sound/card0/uevent > /dev/null 2>&1; then
    echo "✓ card0 still accessible (expected)"
else
    echo "✗ card0 blocked (PROBLEM - too aggressive)"
fi

# Test 4: Run Python with stub and check what it tries to access
echo ""
echo "[Test 4] Testing with Python (simulating PiHome):"
echo "Running: LD_PRELOAD=... strace python3 -c 'import sys' 2>&1 | grep card1"
LD_PRELOAD=/usr/local/lib/libsdl2_audio_stub.so strace -e openat python3 -c "import sys" 2>&1 | grep -q "card1" && echo "✗ card1 accessed" || echo "✓ No card1 access detected"

echo ""
echo "=== Test Complete ==="
echo ""
echo "If all tests passed, the stub should prevent card1 corruption."
echo "Deploy with: sudo ./deploy_audio_fix.sh"
