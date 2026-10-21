{{- $herdr := "" -}}
{{- if eq .chezmoi.os "darwin" -}}{{ $herdr = "/opt/homebrew/bin/herdr" }}{{ else }}{{ $herdr = joinPath .chezmoi.homeDir ".local/bin/herdr" }}{{ end -}}
{{- if stat $herdr -}}
# herdr's agent hooks (docs/herdr.md). `herdr integration install` writes herdr's own hook
# scripts (~/.claude/hooks/herdr-agent-state.sh and the like) and an entry in each
# harness's settings; it runs for any harness `herdr integration status` does not report
# current (a herdr release can bump a hook's version).
converge_herdr_hooks() {
    local status agent stale=() rc=0 pair live
    status=$({{ $herdr | quote }} integration status 2>&1)
    for agent in claude codex pi opencode; do
        grep -q "^$agent: current" <<<"$status" || stale+=("$agent")
    done
    ((${#stale[@]})) || return 0
    step "herdr integration install ${stale[*]}"
    for agent in "${stale[@]}"; do
        {{ $herdr | quote }} integration install "$agent" || rc=1
    done
    # The repo's managed hooks already carry herdr's entry with a portable $HOME path;
    # fold the installer's absolute-path copies into them now, with the same merge the
    # modify_ targets use, so the host converges without a second apply.
    for pair in private_dot_claude/modify_settings.json:.claude/settings.json private_dot_codex/modify_hooks.json:.codex/hooks.json; do
        live=$HOME/${pair#*:}
        [ -f "$live" ] || continue
        python3 "$CHEZMOI_SOURCE_DIR/${pair%%:*}" <"$live" >"$live.merge" && mv "$live.merge" "$live" || rc=1
    done
    return $rc
}
run converge_herdr_hooks
{{- end }}
