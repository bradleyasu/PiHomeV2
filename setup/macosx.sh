#!/bin/sh

alias python=python3
alias pip=pip3
LOG=./install.log
pip install kivy

echo "Installing ffpyplayer as audio provider..."
pip install ffpyplayer >> $LOG
pip install ffmpeg >> $LOG
pip install numpy >> $LOG

#python -m pip install kivy

# MQTT Services
pip install paho-mqtt >> $LOG

# QR Code Services
pip install qrcode[pil] >> $LOG

pip install mplayer.py >> $LOG

pip install websockets >> $LOG

echo "Installing Kivy..."
python3 -m pip install kivy[base] >> $LOG

#echo "Installing Flowers..."
#garden install mapview >> $LOG

python3 -m pip install eyed3 >> $LOG
