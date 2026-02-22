#!/bin/bash
# Check detailed ALSA state before and after PiHome initialization

echo "=================================="
echo "ALSA Device State Monitor"
echo "=================================="

echo -e "\n1. Initial state of hw:1,0:"
echo "-----------------------------------"
cat /proc/asound/card1/pcm0p/sub0/status
cat /proc/asound/card1/pcm0p/sub0/hw_params 2>/dev/null || echo "No hw_params set"
echo ""

echo "2. ALSA device locks:"
sudo fuser -v /dev/snd/* 2>&1

echo -e  "\n3. Testing hw:1,0 BEFORE starting PiHome:"
speaker-test -D hw:1,0 -c 2 -t wav -l 1 2>&1 | head -5

echo -e "\n=================================="
echo "Press CTRL+C when ready, then start PiHome in another terminal"
echo "After PiHome starts, press ENTER here to check device state..."
echo "=================================="
read

echo -e "\n4. State of hw:1,0 AFTER PiHome started:"
echo "-----------------------------------"
cat /proc/asound/card1/pcm0p/sub0/status
cat /proc/asound/card1/pcm0p/sub0/hw_params 2>/dev/null || echo "No hw_params set"
echo ""

echo "5. ALSA device locks AFTER PiHome:"
sudo fuser -v /dev/snd/* 2>&1

echo -e "\n6. Testing hw:1,0 AFTER PiHome started:"
speaker-test -D hw:1,0 -c 2 -t wav -l 1 2>&1 | head -10

echo -e "\n7. Checking dmesg for errors:"
dmesg | grep -i "pcm5122\|dac\|alsa\|audio" | tail -20

echo -e "\n8. Checking ALSA driver state:"
cat /sys/class/sound/card1/id
cat /sys/class/sound/card1/number

echo -e "\n9. Checking if device is in error state:"
cat /proc/asound/card1/pcm0p/sub0/status | grep -i "error\|closed\|xrun"

echo -e "\n=================================="
echo "ANALYSIS COMPLETE"
echo "=================================="
echo "If 'closed' appears in status, the device was closed improperly"
echo "If 'XRUN' appears, there was a buffer overrun/underrun"
echo "Check dmesg for kernel-level errors"
