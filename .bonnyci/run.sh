#!/bin/bash

set -eux
set -o pipefail

sudo apt-get install -y python3 python3-dev python3-pip swig portaudio19-dev
sudo pip3 install tox

tox -e py35
tox -e lint
