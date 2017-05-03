#!/bin/bash

set -eux
set -o pipefail

sudo apt-get install -y python3 python3-dev swig portaudio19-dev
tox
