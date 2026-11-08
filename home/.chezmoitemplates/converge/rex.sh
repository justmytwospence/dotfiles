{{- if or (hasPrefix "mac-" .host) (eq .host "nuc") -}}
# Rex's servers are session owners: reload Lua locally, never restart them on apply.
rex_reload_config() {
    local socket=$1 config="$HOME/.config/rex/init.lua" key
    [ -r "$config" ] && have rex || { echo "rex: CLI or Lua config missing (install and open Rex Beta on a Mac)" >&2; return 1; }
    key=$(digest "$config")
    stamped rex-config "$key" && return 0
    rex config check "$config" >/dev/null || return 1
    # A stopped Mac app will read the new file when it starts. Do not autostart it.
    [ -S "$socket" ] || return 0
    rex --autostart=false -S "$socket" --timeout 3s server status --json >/dev/null 2>&1 || {
        echo "rex: local socket exists but its server is unavailable" >&2; return 1;
    }
    step "rex: reload Lua config"
    rex --autostart=false -S "$socket" config reload >/dev/null || return 1
    stamp rex-config "$key"
}
{{- end }}
{{ if eq .host "nuc" -}}
converge_rex_server() {
    local unit="$HOME/.config/systemd/user/rex.service" key socket="{{ .rex.nuc.remoteSocket }}" ready=0 i
    [ -x "$HOME/.local/bin/rex" ] && [ -r "$unit" ] || {
        echo "rex: pinned binary or user unit missing" >&2; return 1;
    }
    [ "$(loginctl show-user "$(id -u)" -p Linger --value)" = yes ] || {
        echo "rex: enable persistent user services with: loginctl enable-linger" >&2; return 1;
    }
    key=$(digest "$unit")
    if ! stamped rex-unit "$key"; then
        step "rex: reload systemd unit definition (live server is not restarted)"
        systemctl --user daemon-reload || return 1
        stamp rex-unit "$key" || return 1
    fi
    if ! systemctl --user is-active --quiet rex.service; then
        if [ -S "$socket" ]; then
            echo "rex: unmanaged socket exists; leave its server alone and move it under systemd at a safe stopping point (docs/rex.md)" >&2
            return 1
        fi
        step "rex: start personal server"
        systemctl --user start rex.service || return 1
    fi
    # Type=simple returns before the socket is ready; wait briefly, without autostart.
    for ((i=0; i<20; i++)); do
        if rex --autostart=false -S "$socket" --timeout 1s server status --json >/dev/null 2>&1; then ready=1; break; fi
        sleep 0.25
    done
    [ "$ready" = 1 ] || { echo "rex: supervised server did not become ready" >&2; return 1; }
    if ! infocmp xterm-rex >/dev/null 2>&1; then
        step "rex: install user terminfo (SSH config stays unchanged)"
        rex terminfo setup --entry-only >/dev/null || return 1
        infocmp xterm-rex >/dev/null 2>&1 || { echo "rex: terminfo installation did not converge" >&2; return 1; }
    fi
    rex_reload_config "$socket"
}
run converge_rex_server
{{- end }}
{{ if hasPrefix "mac-" .host -}}
converge_rex_tunnel() {
    local label=com.spencerboucher.rex-nuc-tunnel domain="gui/$(id -u)" key i
    local plist="$HOME/Library/LaunchAgents/$label.plist" wrapper="$HOME/.local/bin/rex-nuc-tunnel"
    local ssh_config="$HOME/.ssh/config.d/00-rex-nuc"
    [ -f "$HOME/.ssh/nuc_ed25519" ] && [ -f "$plist" ] && [ -x "$wrapper" ] && [ -f "$ssh_config" ] || {
        echo "rex: tunnel definition or ~/.ssh/nuc_ed25519 missing; see docs/rex.md" >&2; return 1;
    }
    key=$(digest "$plist" "$wrapper" "$ssh_config")
    if ! { launchctl print "$domain/$label" >/dev/null 2>&1 && stamped rex-tunnel "$key"; }; then
        step "rex: load reconnecting NUC tunnel"
        if launchctl print "$domain/$label" >/dev/null 2>&1; then
            launchctl bootout "$domain/$label" || return 1
            for ((i=0; i<20; i++)); do
                launchctl print "$domain/$label" >/dev/null 2>&1 || break
                sleep 0.5
            done
        fi
        launchctl bootstrap "$domain" "$plist" || { sleep 2; launchctl bootstrap "$domain" "$plist"; } || return 1
        launchctl print "$domain/$label" >/dev/null 2>&1 || return 1
        stamp rex-tunnel "$key" || return 1
    fi
    # A loaded tunnel may be retrying while WireGuard is down; that is not apply drift.
    rex_reload_config "$HOME/{{ .rex.macSocket }}"
}
run converge_rex_tunnel

converge_rex_preferences() {
    python3 -B "{{ .chezmoi.sourceDir }}/lib/rex_settings.py" --settings "{{ .chezmoi.sourceDir }}/.chezmoidata/rex.json"
}
run converge_rex_preferences
{{- end }}
