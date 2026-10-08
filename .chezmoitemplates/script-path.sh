# PATH for setup scripts, which may run from a non-interactive ssh session that
# never read ~/.zshenv: Homebrew first on the Mac (as .zshenv does), then
# ~/.local/bin, then nvm's default node, so npm-built plugins and npx work.
export PATH="/opt/homebrew/bin:$HOME/.local/bin:/usr/local/bin:$PATH"
if [ -s "$HOME/.nvm/nvm.sh" ]; then
    set +u
    export NVM_DIR="$HOME/.nvm"
    . "$NVM_DIR/nvm.sh" >/dev/null 2>&1
    nvm use --silent default >/dev/null 2>&1 || true
    set -u
fi
{{- if eq .host "agentbox-box" }}
# AgentBox box: `git` on PATH is AgentBox's shim (/usr/local/bin/git), which relays
# clone/fetch/pull/push to the hub and refuses most flags. Setup only reads public
# repos (plugins, skills, vim plugins), so it uses the real git; the agent keeps the shim.
mkdir -p "$HOME/.local/libexec/real-git" && ln -sfn /usr/bin/git "$HOME/.local/libexec/real-git/git"
export PATH="$HOME/.local/libexec/real-git:$PATH"
{{- end }}
# systemctl --user needs the runtime dir, which exe.dev ssh sessions do not set.
if [ -z "${XDG_RUNTIME_DIR:-}" ] && [ -d "/run/user/$(id -u)" ]; then
    export XDG_RUNTIME_DIR="/run/user/$(id -u)"
fi
