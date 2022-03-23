#!/bin/sh

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

echo "Installing Kivy..."
python3 -m pip install kivy[base] >> $LOG

echo "Setting up environment..."

echo "" >> $PROFILE
echo 'alias pihome="cd /usr/local/PiHome && ./launch.sh"' >> $PROFILE
echo 'alias pihome-update="cd /usr/local/PiHome && ./update.sh"' >> $PROFILE
echo "" >> $PROFILE
source $PROFILE
clear

echo $PINK
echo ""
echo "Preparing to launch PiHome..."
echo ""
echo $ENDCOLOR
cd $PIHOME
chmod 755 ./launch.sh
chmod 755 ./update.sh
./launch.sh
