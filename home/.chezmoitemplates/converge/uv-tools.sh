{{- if or (hasPrefix "mac-" .host) (has .host (list "nuc" "agentbox-box")) -}}
{{- $declared := list }}
{{- if hasPrefix "mac-" .host }}
{{- $brewfile := includeTemplate "dot_Brewfile.tmpl" . }}
{{- range regexFindAll "(?m)^\\s*uv '[^']+'" $brewfile -1 }}{{ $declared = append $declared (regexReplaceAll "^\\s*uv '([^']+)'" . "${1}") }}{{ end }}
{{- else }}
{{- range concat .linux.uv.common (get .linux.uv .host | default (list)) }}{{ $declared = append $declared .pkg }}{{ end }}
{{- end }}
{{- $allow := list }}
{{- range .cooldownAllow }}
{{- if and (eq .kind "uv") ((now).Before (toDate "2006-01-02T15:04:05Z07:00" .until)) }}
{{- $allow = append $allow (printf "--allow %s" (printf "%s==%s@%s" .pkg .version .cutoff | squote)) }}
{{- end }}
{{- end }}
# uv tool receipts (lib/uv_tools.py, docs/cooldown.md): tools that use a package I maintain
# exempt it in their receipt, a declared tool pinned by a lapsed cooldown allowance goes back
# to unpinned, and the retired 2999 sentinels leave every receipt. Reinstalls rewrite the
# receipt only; nothing is upgraded. Silent when converged.
converge_uv_tools() {
    have uv || return 0
    python3 -B {{ joinPath .chezmoi.sourceDir "lib/uv_tools.py" | quote }} --declared {{ join "," $declared | squote }} --maintained {{ join "," .cooldownExempt.uv | squote }}{{ range $allow }} {{ . }}{{ end }}
}
run converge_uv_tools
{{- end }}
