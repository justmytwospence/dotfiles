{{- $mine := list }}
{{- range .herdrPlugins }}{{ if has $.host .hosts }}{{ $mine = append $mine . }}{{ end }}{{ end }}
{{- if $mine -}}
# Herdr plugins pinned in .chezmoidata/herdr_plugins.json, installed natively when
# `herdr plugin list` does not show them at their ref.
converge_herdr_plugins() {
    if ! have herdr; then
        echo "herdr is required for this host's plugins" >&2
        return 1
    fi
    local list rc=0
    list=$(herdr plugin list 2>&1) || { echo "$list" >&2; return 1; }
{{- range $mine }}
    grep -qF {{ printf "[github:%s@%s]" .spec .ref | quote }} <<<"$list" ||
        { step "herdr plugin {{ .spec }}"; {{ with get . "env" }}{{ . }} {{ end }}herdr plugin install {{ .spec }} --ref {{ .ref }} --yes || rc=1; }
{{- end }}
    return $rc
}
run converge_herdr_plugins
{{- end }}
