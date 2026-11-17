{{- $mine := list }}
{{- range .herdrPlugins }}{{ if has $.host .hosts }}{{ $mine = append $mine . }}{{ end }}{{ end }}
{{- if $mine -}}
# Herdr plugins pinned in .chezmoidata/herdr_plugins.json, installed natively when
# `herdr plugin list` does not show them at their ref; GitHub plugins not pinned for this
# host are uninstalled (local: development installs stay).
converge_herdr_plugins() {
    if ! have herdr; then
        echo "herdr is required for this host's plugins" >&2
        return 1
    fi
    local list rc=0 spec
    list=$(herdr plugin list 2>&1) || { echo "$list" >&2; return 1; }
    # Before any install: herdr will not install a plugin over an id another source holds.
    while read -r spec; do
        [ -n "$spec" ] || continue
        case " {{ range $mine }}{{ .spec }} {{ end }}" in *" $spec "*) continue ;; esac
        step "herdr plugin uninstall $spec (not pinned for this host)"
        herdr plugin uninstall "$spec" >/dev/null || rc=1
    done < <(sed -n 's/.*\[github:\(.*\)@[^]@]*\]$/\1/p' <<<"$list")
{{- range $mine }}
    grep -qF {{ printf "[github:%s@%s]" .spec .ref | quote }} <<<"$list" ||
        { step "herdr plugin {{ .spec }}"; {{ with get . "env" }}{{ . }} {{ end }}herdr plugin install {{ .spec }} --ref {{ .ref }} --yes || rc=1; }
{{- end }}
    return $rc
}
run converge_herdr_plugins
{{- end }}
