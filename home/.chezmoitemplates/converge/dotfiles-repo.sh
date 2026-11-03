{{- if ne .host "agentbox-box" -}}
# This checkout's own Git settings, shared by its worktrees: the tracked pre-push hook
# (.githooks: tests gate every push of main) and rerere, which replays a resolved
# conflict when bin/land rebases a branch again. Boxes reset their checkout each start.
converge_dotfiles_repo() {
    local tree={{ .chezmoi.workingTree | quote }} setting key value
    [ -d "$tree/.git" ] || return 0
    for setting in core.hooksPath=.githooks rerere.enabled=true; do
        key=${setting%%=*} value=${setting#*=}
        [ "$(git -C "$tree" config --local --get "$key")" = "$value" ] && continue
        git -C "$tree" config --local "$key" "$value" || return 1
        step "dotfiles repo: git config $key $value"
    done
}
run converge_dotfiles_repo
{{- end }}
