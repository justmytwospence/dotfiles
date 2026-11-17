{{- if hasPrefix "mac-" .host -}}
converge_rex_preferences() {
    python3 -B "{{ .chezmoi.sourceDir }}/lib/rex_settings.py" --settings "{{ .chezmoi.sourceDir }}/.chezmoidata/rex.json"
}
run converge_rex_preferences
{{- end }}
