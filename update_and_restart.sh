#!/bin/sh

echo "Updating PiHome...."
cd /usr/local/PiHome
sudo git pull
sudo pkill -9 -f main.py
clear
python3 main.py