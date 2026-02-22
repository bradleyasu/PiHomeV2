# setup/ Directory

Configuration files and scripts for deploying PiHome on Raspberry Pi.

## Files

### Service Configuration
- **`pihome.service`** - systemd service unit file for PiHome
  - Runs as `pihome-user` user (non-root) for security
  - Restricted to `pihome-grp` group (hw:0,0 access only)
  - Auto-restart on failure

### Setup Scripts
- **`setup_audio_permissions.sh`** - **RUN THIS FIRST on Raspberry Pi**
  - Creates `pihome-user` system user and `pihome-grp` group
  - Creates `shairport` group for hw:1,0 isolation
  - Sets up udev rules to restrict DAC Pro (hw:1,0) access
  - Configures group memberships
  - **Usage:** `sudo bash setup_audio_permissions.sh`

- **`test_audio_permissions.sh`** - Verify setup is working
  - Tests user permissions
  - Verifies device access (pihome-user should NOT access hw:1,0)
  - Checks service status
  - **Provides troubleshooting if isolation is broken**
  - **Usage:** `bash test_audio_permissions.sh`

- **`fix_audio_isolation.sh`** - **Emergency fix if isolation is broken**
  - Removes pihome-user from audio group
  - Manually fixes device permissions
  - Reloads udev rules
  - Tests isolation after fix
  - **Usage:** `sudo bash fix_audio_isolation.sh`

- **`install.sh`** - Original installation script (deprecated)
- **`install-service.sh`** - Service installation (use setup_audio_permissions.sh instead)
- **`macosx.sh`** - macOS development setup

### Documentation
- **`AUDIO_ISOLATION_GUIDE.md`** - **READ THIS** - Complete deployment guide
  - Explains the audio isolation strategy
  - Step-by-step deployment instructions
  - Troubleshooting guide
  - Architecture diagrams

- **`SERVICE_README.md`** - Original service documentation

---

## Quick Start (Raspberry Pi)

```bash
# 1. Upload code to Pi
rsync -avz --exclude '__pycache__' ./ pi@raspberrypi:/tmp/pihome-update/

# 2. SSH to Pi
ssh pi@raspberrypi

# 3. Run permission setup
cd /tmp/pihome-update/setup
sudo bash setup_audio_permissions.sh

# 4. Install code
sudo cp -r /tmp/pihome-update/* /usr/local/PiHome/
sudo chown -R pihome-user:pihome-grp /usr/local/PiHome

# 5. Install service
sudo cp /usr/local/PiHome/setup/pihome.service /etc/systemd/system/
sudo systemctl daemon-reload

# 6. Grant X11 access
xhost +local:pihome-user

# 7. Start service
sudo systemctl start pihome

# 8. Test permissions
bash /usr/local/PiHome/setup/test_audio_permissions.sh

# If test shows pihome-user can access hw:1,0, run emergency fix:
# sudo bash /usr/local/PiHome/setup/fix_audio_isolation.sh
```

See **AUDIO_ISOLATION_GUIDE.md** for full details.

---

## Audio Isolation Strategy

**Problem:** PiHome's SDL2 was scanning/interfering with shairport-sync's hw:1,0 DAC

**Solution:** OS-level device permissions
- PiHome runs as `pihome-user` user → can access hw:0,0 only (via `pihome-grp` group)
- shairport-sync runs as `shairport-sync` user → can access hw:1,0 only (via `audio` group)
- udev rules enforce permissions at kernel level
- Even if SDL2 scans, kernel denies access to hw:1,0

**Result:** Zero interference, complete isolation  

---

## Device Layout

```
hw:0,0 (bcm2835 Headphones)
├── Group: pihome-grp
├── Access: pihome-user ✓
└── PiHome plays here

hw:1,0 (DAC Pro PCM5122)
├── Group: audio
├── Access: pihome-user ✗ (permission denied)
├── Access: shairport-sync user ✓
└── AirPlay audio plays here
```

---

## Troubleshooting

**Service won't start:**
```bash
sudo journalctl -u pihome -n 50
# Check for permission errors
```

**No GUI display:**
```bash
# Grant X11 access
xhost +local:pihome-user
```

**Still accessing hw:1,0:**
```bash
# THIS IS CRITICAL - Isolation is broken!

# Run emergency fix script
sudo bash /usr/local/PiHome/setup/fix_audio_isolation.sh

# Or manually:
# 1. Remove pihome-user from audio group
sudo gpasswd -d pihome-user audio

# 2. Reload udev rules
sudo udevadm control --reload-rules
sudo udevadm trigger

# 3. Reboot
sudo reboot

# 4. Test again
bash /usr/local/PiHome/setup/test_audio_permissions.sh
```

**pihome-user is in audio group (causes hw:1,0 access):**
```bash
# Remove from audio group immediately
sudo gpasswd -d pihome-user audio
sudo systemctl restart pihome

# Verify
groups pihome-user
# Should show: pihome-grp (NOT audio)
```

---

Last updated: 2026-02-22
