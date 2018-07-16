#!/bin/bash
basepath="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )" 
sudo chmod a+x "$basepath/aptik"
sudo "$basepath/aptik" --restore-all --basepath "$basepath"
