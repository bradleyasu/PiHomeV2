#!/bin/sh

echo "Updating PiHome...."
cd /usr/local/PiHome
sudo git pull
echo "PiHome is up-to-date! Run `pihome` to start"