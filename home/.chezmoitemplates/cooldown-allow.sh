{{- /* Exact releases explicitly allowed past the release cooldown (.chezmoidata/cooldown.json,
       written by `cooldown-allow`), for the packages this host declares. Called with
       (dict "allow" .cooldownAllow "npm" <declared npm names> "uv" <declared uv names>);
       appends failures to the caller's `failed` array. Only the named package is exempt, so
       its dependencies still follow the cooldown. An entry past `until` renders nothing: the
       release has cleared the cooldown, and the package's updates follow it again. */ -}}
{{- $npm := .npm }}
{{- $uv := .uv }}
{{- range .allow }}
{{- if (now).Before (toDate "2006-01-02T15:04:05Z07:00" .until) }}
{{- if and (eq .kind "npm") (has .pkg $npm) }}
npm ls -g --depth=0 {{ printf "%s@%s" .pkg .version | quote }} >/dev/null 2>&1 || { echo "==> npm {{ .pkg }}@{{ .version }} (cooldown-allow until {{ .until }})"; npm install -g --no-fund --no-audit --min-release-age-exclude={{ .pkg | quote }} {{ printf "%s@%s" .pkg .version | quote }} || failed+=({{ .pkg | quote }}); }
{{- else if and (eq .kind "uv") (has .pkg $uv) }}
uv tool list 2>/dev/null | grep -qxF {{ printf "%s v%s" .pkg .version | quote }} || { echo "==> uv tool {{ .pkg }}=={{ .version }} (cooldown-allow until {{ .until }})"; uv tool install {{ printf "%s==%s" .pkg .version | quote }} --exclude-newer-package {{ printf "%s=%s" .pkg .cutoff | quote }} || failed+=({{ .pkg | quote }}); }
{{- end }}
{{- end }}
{{- end }}
