{{- if has .host (list "nuc" "agentbox-box") -}}
{{- $uv := concat .linux.uv.common (get .linux.uv .host | default (list)) }}
{{- $npm := get .linux.npm .host | default (list) }}
{{- $inst := get .linux.installers .host | default (list) }}
{{- $npmNames := list }}{{ range $npm }}{{ $npmNames = append $npmNames .pkg }}{{ end }}
{{- $uvNames := list }}{{ range $uv }}{{ $uvNames = append $uvNames .pkg }}{{ end }}
{{- $allow := includeTemplate "cooldown-allow.sh" (dict "allow" .cooldownAllow "npm" $npmNames "uv" $uvNames) | trim }}
# Linux user-level tools from .chezmoidata/linux.json: uv tools, global npm packages and
# vendor installers. Keyed by the executable: a tool already on PATH (however it got
# there) is left alone, so this never upgrades or fights a tool's own updater.
converge_linux_tools() {
    # npm 10 ignores min-release-age (the 7-day cooldown in ~/.npmrc); npm 11 honours it.
    # Pinned to a release past the cooldown; it lands in the npm prefix, ahead of /usr/bin.
    if [ "$(npm --version | cut -d. -f1)" -lt 11 ]; then
        step "npm 11"
        npm install -g --no-fund --no-audit npm@11.21.0 || failed+=(npm)
        hash -r
    fi
{{- if $allow }}
    # Explicitly allowed fresh releases (docs/cooldown.md): installed, or upgraded to, before
    # the lists below, which then find the executable already on PATH.
    {{ $allow | nindent 4 | trim }}
{{- end }}
{{- range $uv }}
    have {{ .bin | quote }} || { step "uv tool {{ .pkg }}"; uv tool install {{ .pkg | quote }} || failed+=({{ .pkg | quote }}); }
{{- end }}
{{- range $npm }}
    have {{ .bin | quote }} || { step "npm {{ .pkg }}"; npm install -g --no-fund --no-audit {{ if hasKey . "allow_scripts" }}--allow-scripts={{ .pkg | quote }} {{ end }}{{ .pkg | quote }} || failed+=({{ .pkg | quote }}); }
{{- end }}
{{- range $inst }}
    have {{ .bin | quote }} || { step "{{ .bin }} (vendor installer)"; bash -c {{ .cmd | quote }} || failed+=({{ .bin | quote }}); }
{{- end }}
}
run converge_linux_tools
{{- end }}
