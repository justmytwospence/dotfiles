{{- if has .host (list "nuc" "agentbox-box") -}}
{{- $uv := concat .linux.uv.common (get .linux.uv .host | default (list)) }}
{{- $npm := get .linux.npm .host | default (list) }}
{{- $pnpm := get .linux.pnpm .host | default (list) }}
{{- $inst := get .linux.installers .host | default (list) }}
# Linux user-level tools from .chezmoidata/linux.json: uv tools, global npm and pnpm packages
# and vendor installers. Keyed by the executable: a tool already on PATH (however it got
# there) is left alone, so this never upgrades or fights a tool's own updater. pnpm's global
# bins go to ~/.local/bin (globalBinDir in its config), like npm's.
converge_linux_tools() {
    # npm 10 ignores min-release-age (the 7-day cooldown in ~/.npmrc); npm 11 honours it.
    # Pinned to a release past the cooldown; it lands in the npm prefix, ahead of /usr/bin.
    if [ "$(npm --version | cut -d. -f1)" -lt 11 ]; then
        step "npm 11"
        npm install -g --no-fund --no-audit npm@11.21.0 || failed+=(npm)
        hash -r
    fi
{{- range $uv }}
    have {{ .bin | quote }} || { step "uv tool {{ .pkg }}"; uv tool install {{ .pkg | quote }} || failed+=({{ .pkg | quote }}); }
{{- end }}
{{- range $npm }}
    have {{ .bin | quote }} || { step "npm {{ .pkg }}"; npm install -g --no-fund --no-audit {{ .pkg | quote }} || failed+=({{ .pkg | quote }}); }
{{- end }}
{{- if $pnpm }}
    hash -r
{{- end }}
{{- range $pnpm }}
    have {{ .bin | quote }} || { step "pnpm {{ .pkg }}"; pnpm add -g {{ if hasKey . "allow_build" }}--allow-build={{ .pkg | quote }} {{ end }}{{ .pkg | quote }} || failed+=({{ .pkg | quote }}); }
{{- end }}
{{- range $inst }}
    have {{ .bin | quote }} || { step "{{ .bin }} (vendor installer)"; bash -c {{ .cmd | quote }} || failed+=({{ .bin | quote }}); }
{{- end }}
}
run converge_linux_tools
{{- end }}
