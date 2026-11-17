{{- if hasPrefix "mac-" .host -}}
converge_rex_tunnel() {
    local label=com.spencerboucher.rex-nuc-tunnel domain="gui/$(id -u)" key i
    local plist="$HOME/Library/LaunchAgents/$label.plist" wrapper="$HOME/.local/bin/rex-nuc-tunnel"
    local ssh_config="$HOME/.ssh/config.d/00-rex-nuc"
    [ -f "$HOME/.ssh/nuc_ed25519" ] && [ -f "$plist" ] && [ -x "$wrapper" ] && [ -f "$ssh_config" ] || {
        echo "rex: tunnel definition or ~/.ssh/nuc_ed25519 missing; see docs/rex.md" >&2; return 1;
    }
    key=$(digest "$plist" "$wrapper" "$ssh_config")
    local loaded=0 reload=1
    launchctl print "$domain/$label" >/dev/null 2>&1 && loaded=1
    # A loaded job on a legacy stamp is current; a manual run only ensures it is loaded.
    if adopted rex-tunnel "$key"; then reload=0; fi
    if [ "$loaded" = 1 ] && ! inputs_changed; then reload=0; fi
    [ "$loaded" = 0 ] && reload=1
    if [ "$reload" = 1 ]; then
        step "rex: load reconnecting NUC tunnel"
        if [ "$loaded" = 1 ]; then
            launchctl bootout "$domain/$label" || return 1
            for ((i=0; i<20; i++)); do
                launchctl print "$domain/$label" >/dev/null 2>&1 || break
                sleep 0.5
            done
        fi
        launchctl bootstrap "$domain" "$plist" || { sleep 2; launchctl bootstrap "$domain" "$plist"; } || return 1
        launchctl print "$domain/$label" >/dev/null 2>&1 || return 1
    fi
}
run converge_rex_tunnel
{{- end }}
