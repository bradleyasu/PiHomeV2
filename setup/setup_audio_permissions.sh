#!/bin/bash
# Setup audio device permissions to isolate hw:1,0 for shairport-sync
# This prevents PiHome from accessing the DAC Pro at the OS level

set -e

echo "=== Audio Device Permission Setup ==="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "ERROR: This script must be run as root"
    echo "Usage: sudo bash setup_audio_permissions.sh"
    exit 1
fi

# 1. Create pihome group if it doesn't exist
if ! getent group pihome > /dev/null 2>&1; then
    echo "[1/6] Creating pihome group..."
    groupadd pihome
    echo "✓ Created pihome group"
else
    echo "[1/6] pihome group already exists"
fi

# 2. Create pihome user if it doesn't exist
if ! id -u pihome > /dev/null 2>&1; then
    echo "[2/6] Creating pihome system user..."
    useradd -r -s /bin/false -d /usr/local/PiHome -g pihome -c "PiHome Service User" pihome
    echo "✓ Created pihome user"
else
    echo "[2/6] pihome user already exists"
    # Ensure user is in pihome group
    usermod -g pihome pihome
fi

# 3. Ensure shairport-sync user is in audio group (for hw:1,0 access)
if id -u shairport-sync > /dev/null 2>&1; then
    echo "[3/6] Adding shairport-sync to audio group (hw:1,0 access)..."
    usermod -a -G audio shairport-sync
    echo "✓ shairport-sync user added to audio group"
else
    echo "[3/6] WARNING: shairport-sync user not found. Install shairport-sync first."
fi

# 4. Verify pihome user is NOT in audio group (isolation)
echo "[4/6] Ensuring pihome user is NOT in audio group (for isolation)..."
if groups pihome | grep -q audio; then
    echo "⚠ Removing pihome from audio group..."
    gpasswd -d pihome audio
    echo "✓ pihome removed from audio group"
else
    echo "✓ pihome user is not in audio group (correct)"
fi

# 5. Create udev rules to control device access
echo "[5/6] Creating udev rules for device access control..."
cat > /etc/udev/rules.d/99-audio-isolation.rules << 'EOF'
# Audio device isolation for PiHome and shairport-sync
# hw:0,0 (bcm2835) → pihome group
# hw:1,0 (DAC Pro) → audio group (for shairport-sync)

# Restrict DAC Pro (PCM5122 - hw:1,0) to audio group
# This allows shairport-sync (in audio group) to access it
# PiHome (NOT in audio group) cannot access it

# PCM control devices for card1 (hw:1,0)
SUBSYSTEM=="sound", KERNEL=="controlC1", GROUP="audio", MODE="0660"

# PCM playback devices for card1 (hw:1,0)
SUBSYSTEM=="sound", KERNEL=="pcmC1D0p", GROUP="audio", MODE="0660"

# All sound devices for card1 (hw:1,0)
SUBSYSTEM=="sound", KERNEL=="card1", GROUP="audio", MODE="0660"

# Grant bcm2835 (hw:0,0) to pihome group
# This allows PiHome to play audio on the built-in output
# shairport-sync (NOT in pihome group) will not use this device

# PCM control devices for card0 (hw:0,0)
SUBSYSTEM=="sound", KERNEL=="controlC0", GROUP="pihome", MODE="0660"

# PCM playback devices for card0 (hw:0,0)
SUBSYSTEM=="sound", KERNEL=="pcmC0D0p", GROUP="pihome", MODE="0660"
SUBSYSTEM=="sound", KERNEL=="pcmC0D1p", GROUP="pihome", MODE="0660"

# All sound devices for card0 (hw:0,0)
SUBSYSTEM=="sound", KERNEL=="card0", GROUP="pihome", MODE="0660"
EOF

echo "✓ Created /etc/udev/rules.d/99-audio-isolation.rules"

# 6. Reload udev rules
echo "[6/6] Reloading udev rules..."
udevadm control --reload-rules
udevadm trigger
echo "✓ udev rules reloaded"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Summary:"
echo "  - pihome user: Member of 'pihome' group, can access hw:0,0 only"
echo "  - shairport-sync user: Member of 'audio' group, can access hw:1,0 only"
echo "  - hw:0,0 devices: Owned by 'pihome' group (mode 0660)"
echo "  - hw:1,0 devices: Owned by 'audio' group (mode 0660)"
echo ""
echo "Current device permissions:"
ls -l /dev/snd/by-id/ 2>/dev/null || ls -l /dev/snd/ || echo "  (run on Raspberry Pi to see devices)"
echo ""
echo "Next steps:"
echo "  1. Update pihome.service to use User=pihome, Group=pihome"
echo "  2. Set ownership: sudo chown -R pihome:pihome /usr/local/PiHome"
echo "  3. Restart services: sudo systemctl daemon-reload && sudo systemctl restart pihome"
echo ""
