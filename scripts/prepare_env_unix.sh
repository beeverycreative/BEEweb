#!/usr/bin/env bash

sudo apt-get install -y git python2.7 python-setuptools python-dev build-essential
sudo easy_install pip

# Downloads BEEwebPi just to easily install settings files
echo "Installing settings files"
if [ -d BEEwebPi ]
then
    rm -rf BEEwebPi/
fi
git clone https://github.com/beeverycreative/BEEwebPi.git

# creates the service settings
sudo cp BEEwebPi/src/filesystem/root/etc/init.d/beeweb /etc/init.d/
sudo cp BEEwebPi/src/filesystem/root/etc/default/beeweb /etc/default/beeweb
sudo sed -i 's/\/home\/pi\/oprint\/bin\/beeweb/\/usr\/local\/bin\/beeweb/g' /etc/default/beeweb
sudo sed -i 's/pi/vagrant/g' /etc/default/beeweb

# copies the configuration files to the user directory
cp -R BEEwebPi/src/filesystem/home/pi/.beeweb ~/.beeweb

# Installs the default slicer
sudo cp BEEwebPi/src/slicers/Cura/Linux/CuraEngine /usr/local/bin/cura_engine
sudo cp BEEwebPi/src/slicers/Cura/Linux/CuraEngine2 /usr/local/bin/cura_engine2
sudo chmod +x /usr/local/bin/cura_engine
sudo chmod +x /usr/local/bin/cura_engine2

# installs dependencies
python setup.py install

