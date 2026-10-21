{{- if hasPrefix "mac-" .host -}}
# aac-touchid (Bitwarden Agent Access listener with Touch ID approvals): (re)load its
# LaunchAgent when the deployed plist or the pinned binary changes, or when it is not
# loaded. Restarting locks the vault; the next agent request asks for the master password.
converge_aac_touchid() {
    local label=com.justmytwospence.aac-touchid domain="gui/$(id -u)" key
    local plist="$HOME/Library/LaunchAgents/$label.plist" bin="$HOME/.local/libexec/aac-touchid/Bitwarden"
    if [ ! -x "$bin" ] || [ ! -f "$plist" ]; then
        echo "aac-touchid: binary or LaunchAgent missing; skipping" >&2
        return 0
    fi
    key=$(digest "$plist" "$bin")
    if launchctl print "$domain/$label" >/dev/null 2>&1; then
        stamped aac-touchid "$key" && return 0
        # No stamp yet: the loaded job is what the old onchange script loaded; adopt it
        # rather than lock the vault for nothing.
        [ -f "$STATE/aac-touchid" ] || { stamp aac-touchid "$key"; return 0; }
    fi
    step "aac-touchid: reload (the vault locks)"
    launchctl bootout "$domain/$label" 2>/dev/null || true
    # bootout returns before the job is gone; bootstrapping too early fails with error 5.
    for _ in $(seq 1 20); do
        launchctl print "$domain/$label" >/dev/null 2>&1 || break
        sleep 0.5
    done
    launchctl bootstrap "$domain" "$plist" || { sleep 2; launchctl bootstrap "$domain" "$plist"; } || return 1
    stamp aac-touchid "$key"
}
run converge_aac_touchid
{{- end }}
