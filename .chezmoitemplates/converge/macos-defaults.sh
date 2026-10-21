{{- if hasPrefix "mac-" .host -}}
# macOS defaults. Each value is read first and written only when it differs; only the
# apps whose domains changed are restarted.
defaults_changed=()
# ensure_default DOMAIN KEY TYPE VALUE, TYPE as for `defaults write` (-bool, -int, -float, -string).
ensure_default() {
    local domain=$1 key=$2 type=$3 value=$4 current
    current=$(defaults read "$domain" "$key" 2>/dev/null) || current=
    case $type in
        -bool) [[ $current == "$([[ $value == true ]] && echo 1 || echo 0)" ]] && return 0 ;;
        -int | -float)
            [[ $current =~ ^-?[0-9.]+$ ]] && awk -v a="$current" -v b="$value" 'BEGIN { exit !(a == b) }' && return 0 ;;
        *) [[ $current == "$value" ]] && return 0 ;;
    esac
    step "defaults $domain $key = $value"
    defaults write "$domain" "$key" "$type" "$value" || return 1
    defaults_changed+=("$domain")
}

converge_macos_defaults() {
    local rc=0 apps=() domain key type value
    while read -r domain key type value; do
        [[ -z $domain || $domain == \#* ]] && continue
        ensure_default "$domain" "$key" "$type" "$value" || rc=1
    done <<'EOF'
# Keyboard: fast repeat, no accent popup.
NSGlobalDomain KeyRepeat -int 2
NSGlobalDomain InitialKeyRepeat -int 15
NSGlobalDomain ApplePressAndHoldEnabled -bool false

# Dock
com.apple.dock autohide -bool true
com.apple.dock autohide-delay -float 0
com.apple.dock autohide-time-modifier -float 0.2
com.apple.dock mru-spaces -bool false
com.apple.dock show-recents -bool false
com.apple.dock tilesize -int 48

# Snappier UI: shorten or drop decorative animations.
com.apple.dock expose-animation-duration -float 0.1
com.apple.dock expose-group-apps -bool false
com.apple.dock launchanim -bool false
com.apple.dock mineffect -string scale
NSGlobalDomain NSAutomaticWindowAnimationsEnabled -bool false
NSGlobalDomain NSWindowResizeTime -float 0.001
NSGlobalDomain QLPanelAnimationDuration -float 0
NSGlobalDomain NSToolbarTitleViewRolloverDelay -float 0
com.apple.finder DisableAllAnimations -bool true

# Menu bar never auto-hides, including in full screen.
NSGlobalDomain _HIHideMenuBar -bool false
NSGlobalDomain AppleMenuBarVisibleInFullscreen -bool true

# Finder
com.apple.finder AppleShowAllExtensions -bool true
com.apple.finder ShowPathbar -bool true
com.apple.finder ShowStatusBar -bool true
com.apple.finder FXEnableExtensionChangeWarning -bool false

# No autocorrect or smart punctuation.
NSGlobalDomain NSAutomaticSpellingCorrectionEnabled -bool false
NSGlobalDomain NSAutomaticCapitalizationEnabled -bool false
NSGlobalDomain NSAutomaticDashSubstitutionEnabled -bool false
NSGlobalDomain NSAutomaticPeriodSubstitutionEnabled -bool false
NSGlobalDomain NSAutomaticQuoteSubstitutionEnabled -bool false

# Screenshots
com.apple.screencapture disable-shadow -bool true
com.apple.screencapture type -string png

# Trackpad: three-finger drag.
com.apple.AppleMultitouchTrackpad TrackpadThreeFingerDrag -bool true
com.apple.driver.AppleBluetoothMultitouch.trackpad TrackpadThreeFingerDrag -bool true
EOF

    # Reduce motion. Writing these needs Full Disk Access for the terminal running apply.
    if ! { ensure_default com.apple.universalaccess reduceMotion -bool true &&
        ensure_default com.apple.Accessibility ReduceMotionEnabled -int 1; } 2>/dev/null; then
        echo "macos-defaults: could not set Reduce motion; enable it in Accessibility > Display" >&2
    fi

    for domain in "${defaults_changed[@]}"; do
        case $domain in
            com.apple.dock) apps+=(Dock) ;;
            com.apple.finder) apps+=(Finder) ;;
            NSGlobalDomain | com.apple.screencapture) apps+=(SystemUIServer) ;;
        esac
    done
    ((${#apps[@]})) && { killall $(printf '%s\n' "${apps[@]}" | sort -u) 2>/dev/null || true; }
    return $rc
}
run converge_macos_defaults
{{- end }}
