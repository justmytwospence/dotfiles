{{- if hasPrefix "mac-" .host -}}
# Local Tor client for the wallet apps (SOCKS 127.0.0.1:9050) holding the client-authorization
# keys for the homelab node onions (docs/tor.md). Reload only when its inputs change.
converge_tor_client() {
    local label=com.spencerboucher.tor domain="gui/$(id -u)" key i
    local plist="$HOME/Library/LaunchAgents/$label.plist" torrc="$HOME/.config/tor/torrc"
    [ -x /opt/homebrew/bin/tor ] && [ -f "$plist" ] && [ -f "$torrc" ] || {
        echo "tor: binary, LaunchAgent or torrc missing" >&2; return 1;
    }
    key=$(digest "$plist" "$torrc" "$HOME"/.config/tor/onion-auth/*.auth_private 2>/dev/null)
    [ -d "$HOME/.local/share/tor" ] || { mkdir -p "$HOME/.local/share/tor" && chmod 700 "$HOME/.local/share/tor"; } || return 1
    if ! { launchctl print "$domain/$label" >/dev/null 2>&1 && stamped tor-client "$key"; }; then
        step "tor: (re)load client"
        /opt/homebrew/bin/tor --verify-config -f "$torrc" >/dev/null || return 1
        if launchctl print "$domain/$label" >/dev/null 2>&1; then
            launchctl bootout "$domain/$label" || return 1
            for ((i=0; i<20; i++)); do
                launchctl print "$domain/$label" >/dev/null 2>&1 || break
                sleep 0.5
            done
        fi
        launchctl bootstrap "$domain" "$plist" || { sleep 2; launchctl bootstrap "$domain" "$plist"; } || return 1
        launchctl print "$domain/$label" >/dev/null 2>&1 || return 1
        stamp tor-client "$key" || return 1
    fi
}
run converge_tor_client
{{- end }}
