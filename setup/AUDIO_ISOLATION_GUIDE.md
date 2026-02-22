# Audio Device Isolation - Deployment Guide

## Problem Summary

PiHome (Kivy/SDL2) was interfering with shairport-sync's DAC Pro (hw:1,0) by scanning/probing all ALSA devices during initialization, even with `SDL_AUDIODRIVER=dummy` set.

## Solution: OS-Level Device Permissions

Block PiHome from accessing hw:1,0 entirely using Linux user permissions and udev rules.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Raspberry Pi                            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐                    ┌──────────────┐      │
│  │   PiHome     │                    │ shairport-   │      │
│  │   Service    │                    │   sync       │      │
│  │              │                    │              │      │
│  │ User: pihome │                    │ User: shair* │      │
│  │ Group:pihome │                    │ Group: audio │      │
│  └──────┬───────┘                    └──────┬───────┘      │
│         │                                   │              │
│         │ ✓ CAN ACCESS                     │ ✓ CAN ACCESS│
│         │                                   │              │
│  ┌──────▼──────────┐              ┌────────▼──────────┐   │
│  │   hw:0,0        │              │    hw:1,0         │   │
│  │  bcm2835 🔊     │              │   DAC Pro 🔊      │   │
│  │                 │              │   PCM5122          │   │
│  │ Group: pihome   │              │ Group: audio      │   │
│  │ Mode: 0660      │              │ Mode: 0660        │   │
│  └─────────────────┘              └───────────────────┘   │
│         ▲                                   ▲              │
│         │                                   │              │
│         │ ✗ CANNOT ACCESS                  │              │
│         │                                   │              │
│         └───────────────────────────────────┘              │
│                    Permission Denied                       │
└─────────────────────────────────────────────────────────────┘
```

**Key Points:**
- `pihome` user is in `pihome` group → can access hw:0,0 only
- `shairport-sync` user is in `audio` group → can access hw:1,0 only
- hw:0,0 device permissions: owned by `pihome` group, mode `0660`
- hw:1,0 device permissions: owned by `audio` group, mode `0660`
- PiHome **physically cannot** open hw:1,0 (permission denied)

---

## Deployment Steps on Raspberry Pi

### 1. Prepare Files

```bash
# On your Mac, upload to Raspberry Pi
cd /Users/bradsheets/Projects/pihome
rsync -avz --exclude '__pycache__' --exclude '.git' \
  ./ pi@raspberrypi:/home/pi/PiHome-staging/

# Or use git pull on the Pi
```

### 2. Stop Current Service

```bash
ssh pi@raspberrypi
sudo systemctl stop pihome
```

### 3. Run Permission Setup Script

```bash
cd /home/pi/PiHome-staging/setup
sudo bash setup_audio_permissions.sh
```

**This script will:**
- Create `pihome` system user and group
- Add `pihome` user to `pihome` group (hw:0,0 access)
- Add `shairport-sync` to `audio` group (hw:1,0 access)
- Create udev rules to set hw:0,0 to `pihome` group
- Create udev rules to set hw:1,0 to `audio` group
- Reload udev rules

### 4. Install Updated Code

```bash
# Move new code to /usr/local/PiHome
sudo cp -r /home/pi/PiHome-staging/* /usr/local/PiHome/

# Set ownership to pihome user
sudo chown -R pihome:pihome /usr/local/PiHome

# Keep execute permissions on scripts
sudo chmod +x /usr/local/PiHome/*.sh
```

### 5. Install Updated Service

```bash
# Copy new service file
sudo cp /usr/local/PiHome/setup/pihome.service /etc/systemd/system/

# Reload systemd 
sudo systemctl daemon-reload
```

### 6. Grant X11 Access to pihome User

Since PiHome needs GUI access but runs as non-root:

```bash
# Allow pihome user to access X11 display
xhost +local:pihome

# Make persistent by adding to ~/.xinitrc or display manager config
echo "xhost +local:pihome" | sudo tee -a /etc/X11/Xsession.d/90-pihome-xhost
```

### 7. Test Device Permissions

```bash
# Check device ownership
ls -l /dev/snd/

# Should see:
# - controlC0 owned by pihome group
# - controlC1 owned by audio group

# Test as pihome user (should FAIL for hw:1,0)
sudo -u pihome speaker-test -D hw:1,0 -c 2 -t sine
# Expected: "Permission denied" or "Device or resource busy"

# Test as pihome user (should WORK for hw:0,0)
sudo -u pihome speaker-test -D hw:0,0 -c 2 -t sine -l 1
# Expected: Plays test tone on bcm2835
```

### 8. Start PiHome Service

```bash
sudo systemctl start pihome
sudo systemctl status pihome

# Check logs
tail -f /usr/local/PiHome/pihome.log
tail -f /usr/local/PiHome/pihome-error.log
```

### 9. Verify hw:1,0 Still Works

```bash
# Start shairport-sync
sudo systemctl start shairport-sync

# From another device, play audio via AirPlay to your Pi
# hw:1,0 should work normally

# Check shairport-sync can still access hw:1,0
sudo -u shairport-sync speaker-test -D hw:1,0 -c 2 -t sine -l 1
# Expected: Plays test tone on DAC Pro
```

---

## Verification Checklist

- [ ] PiHome service starts successfully as `pihome` user
- [ ] PiHome GUI displays on screen
- [ ] PiHome music plays on hw:0,0 (bcm2835)
- [ ] shairport-sync plays on hw:1,0 (DAC Pro)
- [ ] No audio interference between the two
- [ ] Logs show no permission errors

---

## Troubleshooting

### PiHome won't start

```bash
# Check journal for errors
sudo journalctl -u pihome -n 50

# Common issues:
# - File ownership: sudo chown -R pihome:pihome /usr/local/PiHome
# - X11 access: xhost +local:pihome
# - Missing dependencies: pip3 install -r requirements.txt
```

### "Permission denied" on hw:0,0

```bash
# Verify pihome user is in pihome group
groups pihome

# Should show: pihome

# If not, fix it
sudo usermod -g pihome pihome
sudo systemctl restart pihome

# Verify hw:0,0 devices are owned by pihome group
ls -l /dev/snd/controlC0

# If not, reload udev
sudo udevadm control --reload-rules
sudo udevadm trigger
```

### shairport-sync won't play

```bash
# Verify shairport-sync user is in audio group
groups shairport-sync

# Should include: audio

# If not, add and restart
sudo usermod -a -G audio shairport-sync
sudo systemctl restart shairport-sync
```

### udev rules not applying

```bash
# Reload udev
sudo udevadm control --reload-rules
sudo udevadm trigger

# Reboot if still not working
sudo reboot
```

---

### PiHome Can Access hw:1,0 (Isolation Broken)

**This is the critical issue!** If pihome can access hw:1,0, the isolation isn't working.

**Diagnosis Steps:**

```bash
# 1. Check if pihome is in audio group (SHOULD NOT BE)
groups pihome
# Should show: pihome
# Should NOT show: audio

# 2. Check device permissions
ls -l /dev/snd/controlC1
# Should show: crw-rw---- 1 root audio

# 3. Try to access as pihome (should fail)
sudo -u pihome speaker-test -D hw:1,0 -c 2 -t sine -l 1
# Should show: "Permission denied" or "No such device"
```

**Fix Steps:**

```bash
# QUICK FIX: Run the emergency fix script
cd /usr/local/PiHome/setup
sudo bash fix_audio_isolation.sh

# This script will automatically:
# - Remove pihome from audio group
# - Fix device permissions
# - Reload udev rules
# - Test the isolation

# OR manually:

# Step 1: Remove pihome from audio group if present
sudo gpasswd -d pihome audio

# Step 2: Verify udev rules file exists and is correct
cat /etc/udev/rules.d/99-audio-isolation.rules
# Should show hw:1,0 devices assigned to audio group

# Step 3: Fix device ownership manually (temporary)
sudo chgrp audio /dev/snd/controlC1
sudo chgrp audio /dev/snd/pcmC1D0p
sudo chmod 0660 /dev/snd/controlC1
sudo chmod 0660 /dev/snd/pcmC1D0p

# Step 4: Reload udev rules
sudo udevadm control --reload-rules
sudo udevadm trigger

# Step 5: Test again
sudo -u pihome speaker-test -D hw:1,0 -c 2 -t sine -l 1
# Should now fail with "Permission denied"

# Step 6: If still not working, rerun setup script
cd /usr/local/PiHome/setup
sudo bash setup_audio_permissions.sh

# Step 7: Reboot to ensure all changes take effect
sudo reboot
```

**After reboot, verify:**
```bash
groups pihome                    # Should NOT include 'audio'
ls -l /dev/snd/controlC1         # Should be owned by 'audio' group
sudo -u pihome aplay -D hw:1,0   # Should fail with permission denied
```

---

## Rollback (if needed)

```bash
# Restore old service
sudo systemctl stop pihome
sudo cp /usr/local/PiHome/setup/pihome.service.backup /etc/systemd/system/pihome.service
sudo systemctl daemon-reload
sudo systemctl start pihome

# Remove udev rules
sudo rm /etc/udev/rules.d/99-dac-pro.rules
sudo udevadm control --reload-rules
```

---

## Technical Details

### Why This Works

1. **User Isolation**: PiHome runs as `pihome` (non-root), not as `root`
2. **Group-Based Access**: 
   - `pihome` group: Custom group exclusively for hw:0,0 access
   - `audio` group: Standard Linux group for hw:1,0 DAC access
3. **Device Permissions**: udev rules set permissions per device
   - hw:0,0: `0660` (rw-rw----), group `pihome`
   - hw:1,0: `0660` (rw-rw----), group `audio`
4. **Kernel Enforcement**: The kernel blocks unauthorized access at the syscall level

### What If SDL2 Still Tries?

**It doesn't matter.** The kernel will block the `open()` syscall:

```c
// SDL2 tries:
int fd = open("/dev/snd/controlC1", O_RDWR);
// Kernel returns: -1 (errno = EACCES "Permission denied")
// PiHome continues normally, hw:1,0 never touched
```

SDL2 typically logs a warning and moves on to the next device. Since hw:0,0 is explicitly specified in your ffmpeg commands, audio works fine.

---

## Files Modified

- `setup/setup_audio_permissions.sh` (new)
- `setup/pihome.service` (User changed from `root` to `pihome`)
- `setup/AUDIO_ISOLATION_GUIDE.md` (this file)

---

## Success Criteria

✅ PiHome plays audio on hw:0,0  
✅ shairport-sync plays audio on hw:1,0  
✅ No interference between the two  
✅ hw:1,0 continues working after PiHome starts  
✅ Logs show no audio device conflicts  

---

Last updated: 2026-02-22
