#!/bin/sh

echo "Updating PiHome...."
cd /usr/local/PiHome
sudo git pull
sudo systemctl restart pihome