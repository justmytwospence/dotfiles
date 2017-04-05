#!/usr/bin/env zsh

_dwim_add_transform \
    '^(gem|bundle) install' \
    '_dwim_sed "s/.*/rbenv rehash/"'
