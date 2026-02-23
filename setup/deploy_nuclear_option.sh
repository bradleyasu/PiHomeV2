#!/bin/bash
# Deploy the "nuclear option" - physically remove/restore DAC around PiHome startup

set -e

echo "========================================="
echo " NUCLEAR OPTION: DAC REMOVAL DURING INIT"
echo "========================================="
echo ""
echo "This approach:"
echo "  1. Stops shairport-sync"
echo "  2. Unloads PCM5122 drivers (card1 disappears)"
echo "  3. Starts PiHome (no card1 = no corruption)"
echo "  4. Waits 15 seconds"
echo "  5. Reloads drivers (card1 comes back)"
echo "  6. Restarts shairport-sync"
echo ""
read -p "Continue? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
fi

cd /usr/local/PiHome/setup

# Stop current service
echo "[1/5] Stopping current PiHome service..."
sudo systemctl stop pihome 2>/dev/null || true

# Install wrapper script
echo "[2/5] Installing safe start wrapper..."
sudo cp pihome_safe_start.sh /usr/local/bin/
sudo chmod +x /usr/local/bin/pihome_safe_start.sh
echo "✓ Wrapper installed"

# Install new service file
echo "[3/5] Installing new service file..."
sudo cp pihome_safe.service /etc/systemd/system/pihome.service
sudo systemctl daemon-reload
echo "✓ Service file updated"

# Test wrapper manually first
echo "[4/5] Testing wrapper (this will take ~20 seconds)..."
echo "Monitoring /var/log/pihome_safe_start.log..."
sudo touch /var/log/pihome_safe_start.log
tail -f /var/log/pihome_safe_start.log &
TAIL_PID=$!

# Run wrapper in background
sudo /usr/local/bin/pihome_safe_start.sh &
WRAPPER_PID=$!

# Wait 20 seconds
sleep 20

# Kill the wrapper test
sudo kill $WRAPPER_PID 2>/dev/null || true
sudo pkill -f "python3.*main.py" 2>/dev/null || true
kill $TAIL_PID 2>/dev/null || true

echo ""
echo "✓ Test complete"

# Show the log
echo ""
echo "Wrapper log:"
cat /var/log/pihome_safe_start.log
echo ""

# Enable and start service
echo "[5/5] Starting PiHome service..."
sudo systemctl start pihome

# Wait for initialization
sleep 20

echo ""
echo "========================================="
echo " VERIFICATION"
echo "========================================="

# Check if PiHome is running
if systemctl is-active --quiet pihome; then
    echo "✓ PiHome is running"
    PID=$(pgrep -f "python3.*main.py" || echo "")
    if [ -n "$PID" ]; then
        echo "✓ PiHome process: $PID"
    fi
else
    echo "✗ PiHome is not running"
fi

# Check for card1
if [ -e /sys/devices/platform/soc/soc:sound/sound/card1 ]; then
    echo "✓ card1 exists (DAC restored)"
else
    echo "✗ card1 doesn't exist (DAC not restored!)"
fi

# Check for uevent errors AFTER startup
echo ""
echo "Checking for uevent errors (last 5):"
dmesg -T | grep -i "card1.*uevent" | tail -5

# Test DAC
echo ""
echo "Testing DAC..."
if speaker-test -D hw:1,0 -c 2 -t sine -l 1 > /dev/null 2>&1; then
    echo "✓ DAC is working!"
else
    echo "✗ DAC is broken"
fi

# Check shairport-sync
echo ""
if systemctl is-active --quiet shairport-sync; then
    echo "✓ shairport-sync is running"
else
    echo "✗ shairport-sync is not running"
fi

echo ""
echo "========================================="
echo " DEPLOYMENT COMPLETE"
echo "========================================="
echo ""
echo "Check logs:"
echo "  sudo journalctl -u pihome -f"
echo "  sudo tail -f /var/log/pihome_safe_start.log"
echo ""
