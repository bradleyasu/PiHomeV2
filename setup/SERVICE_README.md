# PiHome Systemd Service

This directory contains the systemd service configuration for running PiHome automatically on boot.

## Files

- **pihome.service** - Systemd service unit file
- **install-service.sh** - Installation script for the service

## Automatic Installation

If you ran the main install script (`install.sh`), the service is already installed and enabled. PiHome will start automatically on boot.

## Manual Installation

If you need to install the service manually:

```bash
cd /usr/local/PiHome/setup
chmod +x install-service.sh
./install-service.sh
```

Or manually:

```bash
sudo cp /usr/local/PiHome/setup/pihome.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable pihome.service
sudo systemctl start pihome.service
```

## Service Management Commands

### Check service status
```bash
sudo systemctl status pihome
```

### Start the service
```bash
sudo systemctl start pihome
```

### Stop the service
```bash
sudo systemctl stop pihome
```

### Restart the service
```bash
sudo systemctl restart pihome
```

### Enable autostart on boot
```bash
sudo systemctl enable pihome
```

### Disable autostart on boot
```bash
sudo systemctl disable pihome
```

## Viewing Logs

### View recent logs
```bash
sudo journalctl -u pihome
```

### Follow logs in real-time
```bash
sudo journalctl -u pihome -f
```

### View logs since boot
```bash
sudo journalctl -u pihome -b
```

### View last 100 lines
```bash
sudo journalctl -u pihome -n 100
```

## Troubleshooting

### Service won't start

1. Check the service status:
   ```bash
   sudo systemctl status pihome
   ```

2. View error logs:
   ```bash
   sudo journalctl -u pihome -n 50
   ```

3. Verify the main.py file exists:
   ```bash
   ls -la /usr/local/PiHome/main.py
   ```

4. Test running manually:
   ```bash
   cd /usr/local/PiHome
   sudo python3 main.py
   ```

### Service restarts repeatedly

Check the logs for Python errors:
```bash
sudo journalctl -u pihome -f
```

The service is configured to restart automatically on failure with a 10-second delay.

## Service Configuration

The service runs with the following settings:

- **User**: root (required for access to /usr/local/PiHome)
- **Working Directory**: /usr/local/PiHome
- **Auto-restart**: Enabled (10-second delay on failure)
- **Start Trigger**: After network and sound system are available
- **Environment**: 
  - KIVY_AUDIO=ffpyplayer
  - KIVY_VIDEO=video_ffpyplayer
  - DISPLAY=:0

## Uninstalling

To remove the service:

```bash
sudo systemctl stop pihome
sudo systemctl disable pihome
sudo rm /etc/systemd/system/pihome.service
sudo systemctl daemon-reload
```
