{{- if hasPrefix "mac-" .host }}
# Own only declared non-secret settings; credentials and unrelated app state stay local.
# The helper reads real state and restarts a running app only when managed values differ.
converge_codexbar() {
    python3 -B {{ joinPath .chezmoi.sourceDir "lib/codexbar_settings.py" | quote }} --settings {{ joinPath .chezmoi.sourceDir ".chezmoidata/codexbar.json" | quote }}
}
run converge_codexbar
{{- end }}
