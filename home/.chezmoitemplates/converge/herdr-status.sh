{{- $herdr := "" -}}
{{- if eq .chezmoi.os "darwin" -}}{{ $herdr = "/opt/homebrew/bin/herdr" }}{{ else }}{{ $herdr = joinPath .chezmoi.homeDir ".local/bin/herdr" }}{{ end -}}
{{- if stat $herdr -}}
# The running herdr server (docs/herdr.md "Stale servers after an upgrade"). A new binary
# does not replace a running server, and restarting one ends every non-agent pane
# process, so this only says so, once per client/server version pair. On the NUC it
# also reloads systemd when herdr.service changed, so the next restart uses it.
converge_herdr_status() {
    local status key
{{- if eq .host "nuc" }}
    if [[ $(systemctl --user show herdr -p NeedDaemonReload --value 2>/dev/null) == yes ]]; then
        step "systemctl --user daemon-reload (herdr.service changed)"
        systemctl --user daemon-reload || return 1
    fi
{{- end }}
    status=$({{ $herdr | quote }} status --json 2>/dev/null) || return 0
    key=$(python3 -c '
import json, sys
s = json.load(sys.stdin)
if (s.get("update") or {}).get("server_binary_stale"):
    print(s["client"]["version"], (s.get("server") or {}).get("version"))
' <<<"$status" 2>/dev/null)
    [[ -n $key ]] || return 0
    stamped herdr-stale-server "$key" && return 0
    step "herdr server ${key#* } still runs; the binary is ${key%% *}"
{{- if eq .host "nuc" }}
    echo "    restart it when no agent is working: systemctl --user restart herdr"
{{- else }}
    echo "    restart it when nothing in a pane must survive: herdr server stop, then attach again"
    echo "    (or the experimental herdr server live-handoff, which keeps panes)"
{{- end }}
    stamp herdr-stale-server "$key"
}
run converge_herdr_status
{{- end }}
