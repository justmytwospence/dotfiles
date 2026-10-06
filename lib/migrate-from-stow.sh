#!/usr/bin/env bash
# migrate-from-stow.sh <host> [extras] -- move a host still on the stow layout to chezmoi.
#
# Run it from the old checkout without pulling first (the pull deletes the stow
# packages that `stow -D` needs):
#
#   cd ~/dotfiles && git fetch -q && git show origin/main:lib/migrate-from-stow.sh | bash -s -- mac-air
#
# It finds the stowed packages itself, keeps what programs wrote through the links
# (Claude/Codex/pi settings, .gitconfig) as real files for chezmoi to merge into,
# unstows, moves the checkout to origin/main, installs chezmoi and applies.
# docs/migration.md has the long form.
set -euo pipefail

host=${1:?usage: migrate-from-stow.sh <host> [extras]}
extras=${2-}
cd ~/dotfiles

if [ -d shell ]; then
    pkgs=$(find ~ -maxdepth 7 -type l -lname '*dotfiles/*' -not -path "$HOME/dotfiles/*" 2>/dev/null |
        while read -r l; do readlink "$l"; done | sed -nE 's|.*dotfiles/([^/]+)/.*|\1|p' | sort -u |
        while read -r p; do [ -d "$p" ] && echo "$p"; done | tr '\n' ' ')
    echo "==> stowed packages: ${pkgs:-none}"
    keep=".claude/settings.json .codex/hooks.json .pi/agent/settings.json .gitconfig"
    for f in $keep; do [ -L ~/"$f" ] && [ -e ~/"$f" ] && cp -L ~/"$f" ~/"$f.keep"; done
    # shellcheck disable=SC2086
    [ -n "$pkgs" ] && stow -d ~/dotfiles -t ~ -D $pkgs
    for f in $keep; do [ -f ~/"$f.keep" ] && mv ~/"$f.keep" ~/"$f"; done
    rm -f ~/.agents/skills/{dotfiles-sync,herdr,jev-judgments,paseo-machine0}
fi

echo "==> dotfiles to origin/main"
git fetch -q origin
git checkout -q main
git reset -q --hard origin/main
git clean -fdq

if ! command -v chezmoi >/dev/null; then
    echo "==> installing chezmoi"
    if command -v brew >/dev/null; then brew install chezmoi
    else sh -c "$(curl -fsLS get.chezmoi.io)" -- -b ~/.local/bin -t v2.73.0; export PATH=~/.local/bin:$PATH; fi
fi

echo "==> chezmoi init as $host"
chezmoi init --source ~/dotfiles --apply --force --promptChoice host="$host" --promptString extras="$extras"
chezmoi apply --force
chezmoi verify && echo "==> done: chezmoi verify passes"
[ -f ~/.config/chezmoi/key.txt ] || cat <<'EOF'

API keys: copy ~/.config/chezmoi/key.txt from another Mac to the same path here
(chmod 600), then run `chezmoi apply`.
EOF
