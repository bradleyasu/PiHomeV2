#!/bin/bash
# Safe PiHome startup - temporarily removes card1 DAC during initialization
# This prevents the kernel uevent bug that corrupts the PCM5122 DAC

set -e

echo "[$(date)] PiHome Safe Start - BEGIN" >> /var/log/pihome_safe_start.log

# Step 1: Stop shairport-sync (releases the DAC)
echo "[$(date)] Stopping shairport-sync..." >> /var/log/pihome_safe_start.log
systemctl stop shairport-sync 2>/dev/null || true

# Step 2: Unload PCM5122 drivers (makes card1 disappear)
echo "[$(date)] Unloading DAC drivers..." >> /var/log/pihome_safe_start.log
modprobe -r snd_soc_rpi_simple_soundcard 2>/dev/null || true
modprobe -r snd_soc_pcm512x_i2c 2>/dev/null || true
modprobe -r snd_soc_pcm512x 2>/dev/null || true

# Verify card1 is gone
if [ -e /sys/devices/platform/soc/soc:sound/sound/card1 ]; then
    echo "[$(date)] WARNING: card1 still exists!" >> /var/log/pihome_safe_start.log
else
    echo "[$(date)] card1 successfully removed" >> /var/log/pihome_safe_start.log
fi

# Step 3: Start PiHome (card1 doesn't exist, so no corruption)
echo "[$(date)] Starting PiHome..." >> /var/log/pihome_safe_start.log
cd /usr/local/PiHome
/usr/bin/python3 /usr/local/PiHome/main.py &
PIHOME_PID=$!

# Step 4: Wait for Kivy/SDL to initialize (15 seconds should be enough)
echo "[$(date)] Waiting for PiHome initialization (15s)..." >> /var/log/pihome_safe_start.log
sleep 15

# Step 5: Reload DAC drivers (card1 comes back)
echo "[$(date)] Reloading DAC drivers..." >> /var/log/pihome_safe_start.log
modprobe snd_soc_pcm512x
modprobe snd_soc_pcm512x_i2c
modprobe snd_soc_rpi_simple_soundcard

# Verify card1 is back
if [ -e /sys/devices/platform/soc/soc:sound/sound/card1 ]; then
    echo "[$(date)] card1 successfully restored" >> /var/log/pihome_safe_start.log
else
    echo "[$(date)] WARNING: card1 failed to restore!" >> /var/log/pihome_safe_start.log
fi

# Step 6: Restart shairport-sync
echo "[$(date)] Starting shairport-sync..." >> /var/log/pihome_safe_start.log
systemctl start shairport-sync 2>/dev/null || true

# Step 7: Wait for PiHome to exit
echo "[$(date)] PiHome running (PID: $PIHOME_PID)" >> /var/log/pihome_safe_start.log
wait $PIHOME_PID
EXIT_CODE=$?

echo "[$(date)] PiHome exited with code $EXIT_CODE" >> /var/log/pihome_safe_start.log
exit $EXIT_CODE
