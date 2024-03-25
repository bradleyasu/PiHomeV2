#!/bin/zsh

alias python=python3
alias pip=pip3
pip install kivy

echo "Installing ffpyplayer as audio provider..."
pip install ffpyplayer >> $LOG

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
garden install mapview >> $LOG