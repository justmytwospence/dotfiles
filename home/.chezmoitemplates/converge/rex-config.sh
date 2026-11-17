{{- if or (hasPrefix "mac-" .host) (eq .host "nuc") -}}
# Rex's servers are session owners: reload Lua locally, never restart them on apply.
rex_reload_config() {
    local socket=$1 config="$HOME/.config/rex/init.lua"
    [ -r "$config" ] && have rex || { echo "rex: CLI or Lua config missing (install and open Rex Beta on a Mac)" >&2; return 1; }
    rex config check "$config" >/dev/null || return 1
    # A stopped Mac app will read the new file when it starts. Do not autostart it.
    [ -S "$socket" ] || return 0
    rex --autostart=false -S "$socket" --timeout 3s server status --json >/dev/null 2>&1 || {
        echo "rex: local socket exists but its server is unavailable" >&2; return 1;
    }
    step "rex: reload Lua config"
    rex --autostart=false -S "$socket" config reload >/dev/null || return 1
}
converge_rex_config() {
    rex_reload_config {{ if eq .host "nuc" }}"{{ .rex.nuc.remoteSocket }}"{{ else }}"$HOME/{{ .rex.macSocket }}"{{ end }}
}
run converge_rex_config
{{- end }}
