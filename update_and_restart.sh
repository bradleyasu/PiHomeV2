#!/bin/sh

echo "Updating PiHome...."
cd /usr/local/PiHome
sudo git pull
sudo pkill -9 -f main.py
clear
sudo -E python3 main.py