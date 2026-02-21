#!/bin/bash


# Install Script: sudo curl -sSL https://pihome.io/install | bash


# Colors

PINK=`tput setaf 200`
ENDCOLOR=`tput sgr0`

# Vars
PROFILE=/home/$USER/.bashrc
PIHOME=/usr/local/PiHome
LOG=$PIHOME/install.log

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

echo "Setting up..."
mkdir $PIHOME
cd $PIHOME


echo "Preparing system..."
sudo apt-get -y update  >> $LOG

echo "Installing Dependencies, this may take a few minutes..."
sudo apt-get -y install python3-setuptools git-core python3-dev python3-pip >> $LOG

sudo apt-get -y install pkg-config libgl1-mesa-dev libgles2-mesa-dev \
   libgstreamer1.0-dev \
   gstreamer1.0-plugins-{bad,base,good,ugly} \
   gstreamer1.0-{omx,alsa} libmtdev-dev \
   xclip xsel libjpeg-dev >> $LOG

# Install GStreamer
# Kivy needs this for soundboard
sudo apt-get -y install gstreamer1.0-pulseaudio >> $LOG

sudo apt-get -y install libfreetype6-dev libgl1-mesa-dev libgles2-mesa-dev libdrm-dev libgbm-dev libudev-dev libasound2-dev liblzma-dev libjpeg-dev libtiff-dev libwebp-dev git build-essential >> $LOG
sudo apt-get -y install gir1.2-ibus-1.0 libdbus-1-dev libegl1-mesa-dev libibus-1.0-5 libibus-1.0-dev libice-dev libsm-dev libsndio-dev libwayland-bin libwayland-dev libxi-dev libxinerama-dev libxkbcommon-dev libxrandr-dev libxss-dev libxt-dev libxv-dev x11proto-randr-dev x11proto-scrnsaver-dev x11proto-video-dev x11proto-xinerama-dev >> $LOG

echo "Setting up Simple DirectMedia Layer, please wait..."
# Install SDL2
wget https://cdn.pihome.io/bin/SDL2-2.0.10.tar.gz
tar -zxvf SDL2-2.0.10.tar.gz
pushd SDL2-2.0.10
./configure --enable-video-kmsdrm --disable-video-opengl --disable-video-x11 --disable-video-rpi
make -j$(nproc)
sudo make install
popd

# Install SDL2_image:

wget https://cdn.pihome.io/bin/SDL2_image-2.0.5.tar.gz
tar -zxvf SDL2_image-2.0.5.tar.gz
pushd SDL2_image-2.0.5
./configure
make -j$(nproc)
sudo make install
popd

# Install SDL2_mixer:

wget https://cdn.pihome.io/bin/SDL2_mixer-2.0.4.tar.gz
tar -zxvf SDL2_mixer-2.0.4.tar.gz
pushd SDL2_mixer-2.0.4
./configure
make -j$(nproc)
sudo make install
popd

# Install SDL2_ttf:

wget https://cdn.pihome.io/bin/SDL2_ttf-2.0.15.tar.gz
tar -zxvf SDL2_ttf-2.0.15.tar.gz
pushd SDL2_ttf-2.0.15
./configure
make -j$(nproc)
sudo make install
popd


sudo apt-get -y install mesa-common-dev libsdl2-dev libsdl2-image-dev libsdl2-ttf-dev libsdl2-mixer-dev >> $LOG
sudo apt-get -y install libmtdev1 >> $LOG

# Image manipulation
sudo apt-get -y install libopenjp2-7 >> $LOG

# FFMPEG 
sudo apt-get -y install ffmpeg >> $LOG

# MPG123 to play audio effects
# sudo apt-get -y install mpg123 >> $LOG
sudo apt-get -y install mplayer >> $LOG
sudo apt-get -y install mpv libmpv1 >> $LOG

# VLC
# sudo apt-get -y install vlc >> $LOG

# MQTT Services
python3 -m pip install --break-system-packages paho-mqtt >> $LOG

# QR Code Services
python3 -m pip install --break-system-packages qrcode[pil] >> $LOG

# VLC 
# python3 -m pip install python-vlc >> $LOG

# Playsound
# python3 -m pip install playsound >> $LOG

# python3 -m pip install mpyg321 >> $LOG
python3 -m pip install --break-system-packages mplayer.py >> $LOG
python3 -m pip install --break-system-packages python-mpv >> $LOG

python3 -m pip install --break-system-packages websockets >> $LOG

# Update MPV

curl https://non-gnu.uvt.nl/debian/uvt_key.gpg --output uvt_key.gpg
sudo mv uvt_key.gpg /etc/apt/trusted.gpg.d
sudo apt-get -y install apt-transport-https
sudo sh -c 'echo "deb https://non-gnu.uvt.nl/debian $(lsb_release -sc) uvt" >> /etc/apt/sources.list.d/non-gnu-uvt.list'
sudo apt-get -y update
sudo apt-get -y install -t "o=UvT" mpv


# Install AirPlay services 'shairport'
sudo apt-get -y install --no-install-recommends build-essential git autoconf automake libtool system-dev\
   libpopt-dev libconfig-dev libasound2-dev avahi-daemon libavahi-client-dev libssl-dev libsoxr-dev \
   libplist-dev libsodium-dev uuid-dev libgcrypt-dev xxd libplist-utils \
   libavutil-dev libavcodec-dev libavformat-dev >> $LOG

# Installing nqptp, a shairport dependency 

sudo git clone https://github.com/mikebrady/nqptp.git
cd nqptp
sudo autoreconf -fi # about a minute on a Raspberry Pi.
sudo ./configure --with-systemd-startup
sudo make
sudo make install
cd ..

sudo systemctl enable nqptp
sudo systemctl start nqptp


# Install shairport sync
sudo git clone https://github.com/mikebrady/shairport-sync.git
cd shairport-sync
sudo autoreconf -fi # about 1.5 minutes on a Raspberry Pi B
sudo ./configure --sysconfdir=/etc --with-alsa --with-soxr --with-avahi --with-ssl=openssl --with-systemd-startup --with-airplay-2
sudo  make 
sudo make install
sh user-service-install.sh
cd ..

# IMPORTANT, MAKE SURE THE CURRENT USER HAS AUDIO GROUP PERMISSIONS TO USE SHAIRPORT SYNC
CURRENT_USER=$(whoami)
sudo usermod -aG audio "$CURRENT_USER"  


# make install

echo "Installing Kivy..."
python3 -m pip install --break-system-packages kivy[base] >> $LOG

echo "Installing ffpyplayer as audio provider..."
python3 -m pip install --break-system-packages ffpyplayer >> $LOG

# required for numpy
sudo apt-get -y install libopenblas-dev >> $LOG

# required for sounddevice
sudo apt-get -y install libportaudio2 >> $LOG
sudo apt-get -y install python3-cffi >> $LOG

python3 -m pip install --break-system-packages ffmpeg-python==0.2.0 >> $LOG
python3 -m pip install --break-system-packages numpy==1.26.4 >> $LOG
python3 -m pip install --break-system-packages sounddevice==0.4.6 >> $LOG
python3 -m pip install --break-system-packages Pillow==10.2.0 >> $LOG

# ID3 Tag parsing
python3 -m pip install --break-system-packages eyed3 >> $LOG
# TODO install yt-dlp from cdn

echo "Installing Flowers..."
#garden install mapview >> $LOG

echo "Setting up environment..."

echo "" >> $PROFILE
echo 'alias pihome="cd /usr/local/PiHome && ./launch.sh"' >> $PROFILE
echo 'alias pihome-update="cd /usr/local/PiHome && ./update.sh"' >> $PROFILE
echo "" >> $PROFILE
source $PROFILE
clear

echo $PINK
echo ""
echo "Setting up PiHome systemd service..."
echo ""
echo $ENDCOLOR

# Make scripts executable
cd $PIHOME
chmod 755 ./launch.sh
chmod 755 ./update.sh
chmod 755 ./setup/install-service.sh

# Install and enable the systemd service
echo "Installing PiHome as a system service..."
sudo cp $PIHOME/setup/pihome.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable pihome.service

echo $PINK
echo ""
echo "╔════════════════════════════════════════════╗"
echo "║  PiHome Installation Complete!             ║"
echo "╚════════════════════════════════════════════╝"
echo ""
echo $ENDCOLOR
echo "PiHome has been configured to start automatically on boot."
echo ""
echo "Commands:"
echo "  sudo systemctl start pihome     - Start PiHome now"
echo "  sudo systemctl status pihome    - Check service status"
echo "  sudo systemctl stop pihome      - Stop the service"
echo "  sudo systemctl restart pihome   - Restart the service"
echo "  tail -f /usr/local/PiHome/pihome.log         - View live logs"
echo ""
echo "To start PiHome now, run: sudo systemctl start pihome"
echo "Or reboot the system to start automatically."
echo ""

echo "Restarting system to apply changes..."
sudo reboot