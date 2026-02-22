#!/bin/bash
# Test audio device permissions after setup
# Run this on the Raspberry Pi to verify the isolation is working

echo "=== Audio Device Permission Test ==="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test 1: Check users exist
echo "[Test 1] Checking users..."
if id -u pihome-user > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} pihome-user exists"
else
    echo -e "${RED}✗${NC} pihome-user NOT found"
    exit 1
fi

if id -u shairport-sync > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} shairport-sync user exists"
else
    echo -e "${YELLOW}⚠${NC} shairport-sync user NOT found (install shairport-sync first)"
fi

# Test 2: Check groups
echo ""
echo "[Test 2] Checking group memberships..."

if groups pihome-user | grep -q "^pihome-grp" || groups pihome-user | grep -q " pihome-grp"; then
    echo -e "${GREEN}✓${NC} pihome-user is in 'pihome-grp' group (can access hw:0,0)"
else
    echo -e "${RED}✗${NC} pihome-user NOT in 'pihome-grp' group"
fi

# Check hardware access groups
for group in gpio video render; do
    if groups pihome-user | grep -q $group; then
        echo -e "${GREEN}✓${NC} pihome-user is in '$group' group (hardware access)"
    else
        echo -e "${YELLOW}⚠${NC} pihome-user NOT in '$group' group (may need for GPIO/GPU)"
    fi
done

if groups pihome-user | grep -q audio; then
    echo -e "${YELLOW}⚠${NC} WARNING: pihome-user is in 'audio' group (should be isolated)"
else
    echo -e "${GREEN}✓${NC} pihome-user is NOT in 'audio' group (correct isolation)"
fi

if id -u shairport-sync > /dev/null 2>&1; then
    if groups shairport-sync | grep -q audio; then
        echo -e "${GREEN}✓${NC} shairport-sync is in 'audio' group (can access hw:1,0)"
    else
        echo -e "${RED}✗${NC} shairport-sync NOT in 'audio' group"
    fi
fi

# Test 3: Check device permissions
echo ""
echo "[Test 3] Checking device permissions..."

# Check hw:0,0 (should be pihome-grp group)
if [ -e /dev/snd/controlC0 ]; then
    CONTROL_GROUP=$(stat -c '%G' /dev/snd/controlC0 2>/dev/null || stat -f '%Sg' /dev/snd/controlC0 2>/dev/null)
    if [ "$CONTROL_GROUP" = "pihome-grp" ]; then
        echo -e "${GREEN}✓${NC} /dev/snd/controlC0 owned by 'pihome-grp' group"
    else
        echo -e "${YELLOW}⚠${NC} /dev/snd/controlC0 owned by '$CONTROL_GROUP' (expected: pihome-grp)"
    fi
    ls -l /dev/snd/controlC0
else
    echo -e "${YELLOW}⚠${NC} /dev/snd/controlC0 not found"
fi

# Check hw:1,0 (should be audio group)
if [ -e /dev/snd/controlC1 ]; then
    CONTROL_GROUP=$(stat -c '%G' /dev/snd/controlC1 2>/dev/null || stat -f '%Sg' /dev/snd/controlC1 2>/dev/null)
    if [ "$CONTROL_GROUP" = "audio" ]; then
        echo -e "${GREEN}✓${NC} /dev/snd/controlC1 owned by 'audio' group"
    else
        echo -e "${YELLOW}⚠${NC} /dev/snd/controlC1 owned by '$CONTROL_GROUP' (expected: audio)"
    fi
    ls -l /dev/snd/controlC1
else
    echo -e "${YELLOW}⚠${NC} /dev/snd/controlC1 not found (hw:1,0 may not be connected)"
fi

# Test 4: Check udev rules
echo ""
echo "[Test 4] Checking udev rules..."

if [ -f /etc/udev/rules.d/99-audio-isolation.rules ]; then
    echo -e "${GREEN}✓${NC} /etc/udev/rules.d/99-audio-isolation.rules exists"
    echo "   Content:"
    cat /etc/udev/rules.d/99-audio-isolation.rules | grep -v '^#' | grep -v '^$' | sed 's/^/   /'
else
    echo -e "${RED}✗${NC} udev rules file NOT found"
fi

# Test 5: Test actual device access
echo ""
echo "[Test 5] Testing device access (requires speaker-test)..."

if command -v speaker-test > /dev/null 2>&1; then
    # Test pihome-user access to hw:0,0 (should work)
    echo -n "  Testing pihome-user access to hw:0,0... "
    if sudo -u pihome-user speaker-test -D hw:0,0 -c 2 -t sine -l 1 > /dev/null 2>&1; then
        echo -e "${GREEN}✓ SUCCESS${NC}"
    else
        echo -e "${RED}✗ FAILED${NC}"
    fi

    # Test pihome-user access to hw:1,0 (should fail)
    echo -n "  Testing pihome-user access to hw:1,0... "
    if sudo -u pihome-user speaker-test -D hw:1,0 -c 2 -t sine -l 1 > /dev/null 2>&1; then
        echo -e "${RED}✗ UNEXPECTED SUCCESS (should be denied)${NC}"
        echo ""
        echo "=== TROUBLESHOOTING: pihome-user can access hw:1,0 ==="
        echo ""
        echo "This should NOT happen. The isolation is broken."
        echo ""
        echo "Possible causes and fixes:"
        echo ""
        echo "1. Check if pihome-user is in audio group (should NOT be):"
        echo "   $ groups pihome-user"
        if groups pihome-user | grep -q audio; then
            echo -e "   ${RED}FOUND: pihome-user IS in audio group${NC}"
            echo "   FIX: sudo gpasswd -d pihome-user audio"
        else
            echo -e "   ${GREEN}OK: pihome-user is NOT in audio group${NC}"
        fi
        echo ""
        echo "2. Check device permissions on hw:1,0:"
        echo "   $ ls -l /dev/snd/controlC1"
        ls -l /dev/snd/controlC1
        ACTUAL_GROUP=$(stat -c '%G' /dev/snd/controlC1 2>/dev/null || stat -f '%Sg' /dev/snd/controlC1 2>/dev/null)
        if [ "$ACTUAL_GROUP" != "audio" ]; then
            echo -e "   ${RED}WRONG: Group is '$ACTUAL_GROUP' (should be 'audio')${NC}"
            echo "   FIX: sudo chgrp audio /dev/snd/controlC1"
        else
            echo -e "   ${GREEN}OK: Group is 'audio'${NC}"
        fi
        echo ""
        echo "3. Reload udev rules and reapply permissions:"
        echo "   $ sudo udevadm control --reload-rules"
        echo "   $ sudo udevadm trigger"
        echo ""
        echo "4. If still failing, run setup script again:"
        echo "   $ sudo bash /usr/local/PiHome/setup/setup_audio_permissions.sh"
        echo ""
        echo "5. After fixing, reboot to ensure all changes take effect:"
        echo "   $ sudo reboot"
        echo ""
    else
        echo -e "${GREEN}✓ DENIED (as expected)${NC}"
    fi

    # Test shairport-sync access to hw:1,0 (should work)
    if id -u shairport-sync > /dev/null 2>&1; then
        echo -n "  Testing shairport-sync access to hw:1,0... "
        if sudo -u shairport-sync speaker-test -D hw:1,0 -c 2 -t sine -l 1 > /dev/null 2>&1; then
            echo -e "${GREEN}✓ SUCCESS${NC}"
        else
            echo -e "${RED}✗ FAILED${NC}"
        fi
    fi
else
    echo -e "${YELLOW}⚠${NC} speaker-test not found, skipping access tests"
    echo "   Install with: sudo apt-get install alsa-utils"
fi

# Test 6: List all sound devices
echo ""
echo "[Test 6] Sound devices:"
ls -lh /dev/snd/ 2>/dev/null | grep -v '^total'

# Test 7: Check service status
echo ""
echo "[Test 7] Service status:"
if systemctl is-active --quiet pihome; then
    echo -e "${GREEN}✓${NC} pihome service is running"
    echo "  User: $(systemctl show pihome -p User --value)"
    echo "  Group: $(systemctl show pihome -p Group --value)"
else
    echo -e "${YELLOW}⚠${NC} pihome service is not running"
fi

echo ""
echo "=== Test Complete ==="
echo ""
echo "Expected results:"
echo "  ✓ pihome-user can access hw:0,0"
echo "  ✓ pihome-user CANNOT access hw:1,0 (permission denied)"
echo "  ✓ shairport-sync can access hw:1,0"
echo ""
