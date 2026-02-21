#!/bin/bash

# PiHome Service Installation Script
# This script installs and enables the PiHome systemd service

# Colors
PINK=`tput setaf 200`
GREEN=`tput setaf 2`
ENDCOLOR=`tput sgr0`

echo "${PINK}Installing PiHome systemd service...${ENDCOLOR}"
echo ""

# Copy service file to systemd directory
echo "Copying service file..."
sudo cp /usr/local/PiHome/setup/pihome.service /etc/systemd/system/

# Reload systemd daemon
echo "Reloading systemd daemon..."
sudo systemctl daemon-reload

# Enable the service to start on boot
echo "Enabling PiHome service..."
sudo systemctl enable pihome.service

# Start the service now
echo "Starting PiHome service..."
sudo systemctl start pihome.service

echo ""
echo "${GREEN}✓ PiHome service installed successfully!${ENDCOLOR}"
echo ""
echo "Useful commands:"
echo "  sudo systemctl status pihome    - Check service status"
echo "  sudo systemctl stop pihome      - Stop the service"
echo "  sudo systemctl start pihome     - Start the service"
echo "  sudo systemctl restart pihome   - Restart the service"
echo "  sudo systemctl disable pihome   - Disable autostart"
echo "  sudo journalctl -u pihome -f    - View live logs"
echo ""
