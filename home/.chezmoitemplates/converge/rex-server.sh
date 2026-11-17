{{- if eq .host "nuc" -}}
converge_rex_server() {
    local unit="$HOME/.config/systemd/user/rex.service" socket="{{ .rex.nuc.remoteSocket }}" ready=0 i
    [ -x "$HOME/.local/bin/rex" ] && [ -r "$unit" ] || {
        echo "rex: pinned binary or user unit missing" >&2; return 1;
    }
    [ "$(loginctl show-user "$(id -u)" -p Linger --value)" = yes ] || {
        echo "rex: enable persistent user services with: loginctl enable-linger" >&2; return 1;
    }
    if [[ $(systemctl --user show rex.service -p NeedDaemonReload --value 2>/dev/null) == yes ]]; then
        step "rex: reload systemd unit definition (live server is not restarted)"
        systemctl --user daemon-reload || return 1
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
}
run converge_rex_server
{{- end }}
