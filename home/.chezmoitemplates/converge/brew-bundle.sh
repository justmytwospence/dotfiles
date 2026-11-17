{{- if hasPrefix "mac-" .host -}}
# Homebrew: install what ~/.Brewfile lists and is missing (--no-upgrade: upgrades stay
# `brew upgrade`). Reruns when the Brewfile changes; drift is `bin/converge brew-bundle`.
converge_brew_bundle() {
    eval "$(/opt/homebrew/bin/brew shellenv 2>/dev/null || /usr/local/bin/brew shellenv)"
    if ! brew bundle check --global --no-upgrade >/dev/null 2>&1; then
        step "brew bundle"
        brew bundle install --global --no-upgrade || return 1
    fi
}
run converge_brew_bundle
{{- end }}
