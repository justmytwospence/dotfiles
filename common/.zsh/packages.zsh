#!/usr/bin/env zsh

zplug $ZSH/after_zplug, from:local, defer:3
zplug $ZSH/before_zplug, from:local, defer:0
zplug hchbaw/opp.zsh, if:"(( ${ZSH_VERSION%%.*} < 5 ))"
zplug hlissner/zsh-autopair, if:"(( ${ZSH_VERSION%%.*} >= 5))", defer:2
zplug oknowton/zsh-dwim
zplug tarrasch/zsh-autoenv
zplug tarrasch/zsh-bd
zplug termoshtt/zaw-systemd
zplug vifon/deer, use:deer
zplug zsh-users/zaw, hook-build:$ZPLUG_CHMOD
zplug zsh-users/zsh-completions, hook-build:$ZPLUG_CHMOD
zplug zsh-users/zsh-syntax-highlighting, defer:2

if [[ $(uname) == Darwin ]]; then
    zplug $(brew --prefix rbenv)/completions, from:local
    zplug /usr/local/etc/bash_completion.d, from:local, use:arcanist, defer:2
fi

if ! zplug check; then
    zplug install
fi
