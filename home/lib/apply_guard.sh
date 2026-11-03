#!/bin/sh
# chezmoi pre-apply/pre-update hook (.chezmoi.toml.tmpl): $HOME tracks committed main.
# Refuses unless the source is the main checkout, on branch main, with nothing
# uncommitted under home/. Worktrees never deploy; they land through bin/land.
# DOTFILES_ALLOW_DIRTY_APPLY=1 skips the check for one deliberate command.
[ -n "${DOTFILES_ALLOW_DIRTY_APPLY:-}" ] && exit 0

tree=${CHEZMOI_WORKING_TREE:-}
cmd=${CHEZMOI_COMMAND:-apply}
refuse() {
    printf 'chezmoi %s: refused by home/lib/apply_guard.sh: %s\n' "$cmd" "$1" >&2
    [ -n "${2:-}" ] && printf '%s\n' "$2" | sed 's/^/  /' >&2
    printf '  Land changes with bin/land; DOTFILES_ALLOW_DIRTY_APPLY=1 overrides once.\n' >&2
    exit 1
}

[ -n "$tree" ] || refuse "CHEZMOI_WORKING_TREE is unset"
git_dir=$(git -C "$tree" rev-parse --absolute-git-dir 2>/dev/null) ||
    refuse "$tree is not a Git checkout"
common=$(cd "$tree" && cd "$(git rev-parse --git-common-dir)" && pwd -P) ||
    refuse "cannot read the Git common directory of $tree"
[ "$git_dir" = "$common" ] ||
    refuse "$tree is a linked worktree; only the main checkout deploys"
branch=$(git -C "$tree" symbolic-ref --short -q HEAD) || branch="(detached)"
[ "$branch" = main ] || refuse "$tree is on $branch, not main"
dirty=$(git -C "$tree" status --porcelain --untracked-files=all -- home) ||
    refuse "git status failed in $tree"
[ -z "$dirty" ] ||
    refuse "uncommitted changes under home/ would deploy:" "$(printf '%s\n' "$dirty" | head -n 8)"
exit 0
