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
