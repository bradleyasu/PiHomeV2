#!/bin/sh


# Colors

PINK=`tput setaf 200`
ENDCOLOR=`tput sgr0`

# Vars
PROFILE=~/.bashrc
PIHOME=/usr/local/PiHome
LOG=$PIHOME/install.log
clear
echo $PINK
echo "______ _ _   _                      ";
echo "| ___ (_) | | |                     ";
echo "| |_/ /_| |_| | ___  _ __ ___   ___ ";
echo "|  __/| |  _  |/ _ \| '_ V _  \ / _ \\";
echo "| |   | | | | | (_) | | | | | |  __/";
echo "\_|   |_\_| |_/\___/|_| |_| |_|\___|";
echo $ENDCOLOR
echo "------------------------------------";
echo ""

echo "Starting PiHome..."
cd /usr/local/PiHome
sudo -E python3 main.py