#!/bin/bash

# @raycast.schemaVersion 1
# @raycast.title Toggle Lid Sleep
# @raycast.mode silent
# @raycast.packageName System
# @raycast.description Keep the Mac awake with the lid closed (pmset disablesleep)

# Raycast script command: toggle macOS lid-close sleep via `pmset disablesleep`.
# Same mechanism as the SwiftBar plugin dot_config/swiftbar/plugins/lid-caffeine.
# Requires /etc/sudoers.d/lid-caffeine, installed by .chezmoiscripts/run_onchange_after_75-lid-sleep-sudoers.sh.tmpl:
#   spencerboucher ALL=(root) NOPASSWD: /usr/bin/pmset -a disablesleep 1, /usr/bin/pmset -a disablesleep 0
#

PMSET=/usr/bin/pmset

state() {
  "$PMSET" -g | /usr/bin/awk 'tolower($1)=="sleepdisabled"{print $2}'
}

if [ "$(state)" = "1" ]; then target=0; else target=1; fi

if ! /usr/bin/sudo -n "$PMSET" -a disablesleep "$target" 2>/dev/null; then
  echo "Failed: sudoers entry /etc/sudoers.d/lid-caffeine missing"
  exit 1
fi

# Show/hide the SwiftBar indicator immediately instead of waiting for its 30s poll.
/usr/bin/open -g "swiftbar://refreshplugin?name=lid-caffeine" 2>/dev/null || true

if [ "$(state)" = "1" ]; then
  echo "Lid sleep DISABLED: stays awake when closed"
else
  echo "Lid sleep normal: closing lid sleeps"
fi
