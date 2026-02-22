#!/bin/bash
# Check ALSA configuration for potential issues

echo "=============================="
echo "ALSA Configuration Diagnostics"
echo "=============================="

echo -e "\n1. Checking /etc/asound.conf (system-wide):"
if [ -f /etc/asound.conf ]; then
    echo "File exists:"
    cat /etc/asound.conf
else
    echo "Not present (OK)"
fi

echo -e "\n2. Checking ~/.asoundrc (user-level):"
if [ -f ~/.asoundrc ]; then
    echo "File exists:"
    cat ~/.asoundrc
else
    echo "Not present (OK)"
fi

echo -e "\n3. Checking /usr/share/alsa/alsa.conf includes:"
grep -i "pcm\." /usr/share/alsa/alsa.conf | head -20

echo -e "\n4. Listing all ALSA cards:"
cat /proc/asound/cards

echo -e "\n5. Checking hw:1,0 (DAC) status:"
cat /proc/asound/card1/pcm0p/sub0/status 2>/dev/null || echo "Cannot read status"

echo -e "\n6. Checking for ALSA UCM (Use Case Manager) configs:"
ls -la /usr/share/alsa/ucm* 2>/dev/null || echo "No UCM configs found"

echo -e "\n7. Checking loaded sound modules:"
lsmod | grep -i snd

echo -e "\n8. Checking dmesg for audio errors:"
dmesg | grep -i "audio\|alsa\|pcm5122\|dac" | tail -20

echo "\n=============================="
echo "END DIAGNOSTICS"
echo "=============================="
