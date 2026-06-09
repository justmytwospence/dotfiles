#!/bin/bash
#
# SwiftBar plugin: toggle macOS lid-close sleep via `pmset disablesleep`.
# Lets the Mac keep running with the lid shut, no external display needed.
# Caffeinate/Caffeine/KeepingYouAwake only block *idle* sleep, not lid-close
# sleep; `pmset disablesleep` is the mechanism that actually does it (the same
# one Amphetamine wraps).
#
# Requires a passwordless sudoers entry scoped to exactly these two commands:
#   spencerboucher ALL=(root) NOPASSWD: /usr/bin/pmset -a disablesleep 1, /usr/bin/pmset -a disablesleep 0
# installed at /etc/sudoers.d/lid-caffeine
#
# <bitbar.title>Lid Caffeine</bitbar.title>
# <bitbar.version>1.0</bitbar.version>
# <bitbar.desc>Toggle pmset disablesleep to keep the Mac awake with the lid closed.</bitbar.desc>
# <swiftbar.hideAbout>true</swiftbar.hideAbout>
# <swiftbar.hideRunInTerminal>true</swiftbar.hideRunInTerminal>
# <swiftbar.hideLastUpdated>true</swiftbar.hideLastUpdated>
# <swiftbar.hideDisablePlugin>true</swiftbar.hideDisablePlugin>

PMSET=/usr/bin/pmset

case "$1" in
  on)  /usr/bin/sudo -n "$PMSET" -a disablesleep 1 ;;
  off) /usr/bin/sudo -n "$PMSET" -a disablesleep 0 ;;
esac

state="$("$PMSET" -g | /usr/bin/awk 'tolower($1)=="sleepdisabled"{print $2}')"
[ "$state" = "1" ] || state=0

if [ "$state" = "1" ]; then
  echo ":cup.and.saucer.fill:"
  echo "---"
  echo "Lid-close sleep: DISABLED — stays awake when closed | color=orange"
  echo "Allow sleep | bash='$0' param1=off terminal=false refresh=true"
else
  echo ":cup.and.saucer:"
  echo "---"
  echo "Lid-close sleep: normal (closing lid sleeps)"
  echo "Keep awake with lid closed | bash='$0' param1=on terminal=false refresh=true"
fi
echo "---"
echo "disablesleep = $state | font=Menlo size=11"
echo "Refresh | refresh=true"
