#!/bin/bash
# Emergency fix script if pihome-user can access hw:1,0
# Run this if test_audio_permissions.sh shows isolation is broken

set -e

echo "=== Audio Isolation Emergency Fix ==="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "ERROR: This script must be run as root"
    echo "Usage: sudo bash fix_audio_isolation.sh"
    exit 1
fi

echo "[1/7] Checking current pihome-user group membership..."
PIHOME_GROUPS=$(groups pihome-user 2>/dev/null || echo "")
echo "Current groups: $PIHOME_GROUPS"

if echo "$PIHOME_GROUPS" | grep -q audio; then
    echo "⚠ WARNING: pihome-user is in audio group (THIS IS THE PROBLEM)"
    echo "[2/7] Removing pihome-user from audio group..."
    gpasswd -d pihome-user audio
    echo "✓ Removed pihome-user from audio group"
else
    echo "[2/7] pihome-user is NOT in audio group (correct)"
fi

echo ""
echo "[3/7] Setting pihome-user's primary group to pihome-grp..."
usermod -g pihome-grp pihome-user
echo "✓ Primary group set to pihome-grp"

echo ""
echo "[3.5/7] Ensuring pihome-user has hardware access groups..."
for group in gpio video render; do
    if getent group $group > /dev/null 2>&1; then
        if ! groups pihome-user | grep -q $group; then
            usermod -a -G $group pihome-user
            echo "✓ Added pihome-user to $group group"
        else
            echo "✓ pihome-user already in $group group"
        fi
    fi
done

echo ""
echo "[4/7] Fixing device permissions manually..."

# Fix hw:1,0 (DAC Pro) permissions
if [ -e /dev/snd/controlC1 ]; then
    chgrp audio /dev/snd/controlC1
    chmod 0660 /dev/snd/controlC1
    echo "✓ Fixed /dev/snd/controlC1 (hw:1,0 control)"
fi

if [ -e /dev/snd/pcmC1D0p ]; then
    chgrp audio /dev/snd/pcmC1D0p
    chmod 0660 /dev/snd/pcmC1D0p
    echo "✓ Fixed /dev/snd/pcmC1D0p (hw:1,0 playback)"
fi

# Fix hw:0,0 (bcm2835) permissions
if [ -e /dev/snd/controlC0 ]; then
    chgrp pihome-grp /dev/snd/controlC0
    chmod 0660 /dev/snd/controlC0
    echo "✓ Fixed /dev/snd/controlC0 (hw:0,0 control)"
fi

if [ -e /dev/snd/pcmC0D0p ]; then
    chgrp pihome-grp /dev/snd/pcmC0D0p
    chmod 0660 /dev/snd/pcmC0D0p
    echo "✓ Fixed /dev/snd/pcmC0D0p (hw:0,0 playback)"
fi

if [ -e /dev/snd/pcmC0D1p ]; then
    chgrp pihome-grp /dev/snd/pcmC0D1p
    chmod 0660 /dev/snd/pcmC0D1p
    echo "✓ Fixed /dev/snd/pcmC0D1p (hw:0,0 playback alt)"
fi

echo ""
echo "[5/7] Verifying udev rules file..."
if [ -f /etc/udev/rules.d/99-audio-isolation.rules ]; then
    echo "✓ udev rules file exists"
    echo ""
    echo "Rules content:"
    cat /etc/udev/rules.d/99-audio-isolation.rules | grep -v '^#' | grep -v '^$'
else
    echo "⚠ WARNING: udev rules file missing!"
    echo "You need to run: sudo bash setup_audio_permissions.sh"
fi

echo ""
echo "[6/7] Reloading udev rules..."
udevadm control --reload-rules
udevadm trigger
echo "✓ udev rules reloaded"

echo ""
echo "[7/7] Testing isolation..."
echo ""

# Test pihome-user access to hw:1,0 (should fail)
echo -n "Testing pihome-user access to hw:1,0... "
if sudo -u pihome-user speaker-test -D hw:1,0 -c 2 -t sine -l 1 > /dev/null 2>&1; then
    echo "❌ STILL HAS ACCESS (isolation broken)"
    echo ""
    echo "The fix did not work. Additional steps needed:"
    echo ""
    echo "1. Check if DAC is connected:"
    echo "   $ aplay -l | grep -i dac"
    echo ""
    echo "2. Reboot the system:"
    echo "   $ sudo reboot"
    echo ""
    echo "3. After reboot, test again:"
    echo "   $ bash /usr/local/PiHome/setup/test_audio_permissions.sh"
    echo ""
else
    echo "✓ DENIED (isolation working!)"
fi

# Test pihome-user access to hw:0,0 (should work)
echo -n "Testing pihome-user access to hw:0,0... "
if sudo -u pihome-user speaker-test -D hw:0,0 -c 2 -t sine -l 1 > /dev/null 2>&1; then
    echo "✓ ACCESS GRANTED (correct)"
else
    echo "❌ DENIED (this should work)"
    echo "   Check if pihome-grp group has access to hw:0,0"
fi

echo ""
echo "=== Fix Complete ==="
echo ""
echo "Current status:"
echo "  - pihome-user groups: $(groups pihome-user)"
echo "  - hw:0,0 control: $(ls -l /dev/snd/controlC0 2>/dev/null | awk '{print $3":"$4" "$1}' || echo 'not found')"
echo "  - hw:1,0 control: $(ls -l /dev/snd/controlC1 2>/dev/null | awk '{print $3":"$4" "$1}' || echo 'not found')"
echo ""

# Check if pihome service is running
if systemctl is-active --quiet pihome; then
    echo "Note: pihome service is running. You may need to restart it:"
    echo "  $ sudo systemctl restart pihome"
    echo ""
fi

echo "If isolation is still broken after this fix, REBOOT is required:"
echo "  $ sudo reboot"
echo ""
