{{- if hasPrefix "mac-" .host -}}
{{- $brewfile := includeTemplate "dot_Brewfile.tmpl" . }}
# Homebrew: install what ~/.Brewfile lists and is missing (--no-upgrade: upgrades stay
# `brew upgrade`). `brew bundle check` takes seconds, so it runs when the Brewfile changes, and
# otherwise once a day to catch drift.
converge_brew_bundle() {
    eval "$(/opt/homebrew/bin/brew shellenv 2>/dev/null || /usr/local/bin/brew shellenv)"
    local key={{ $brewfile | sha256sum | quote }}
    if stamped brew-bundle "$key" && [[ -n $(find "$STATE/brew-bundle" -mmin -1440 2>/dev/null) ]]; then
        return 0
    fi
    if ! brew bundle check --global --no-upgrade >/dev/null 2>&1; then
        step "brew bundle"
        brew bundle install --global --no-upgrade || return 1
    fi
    stamp brew-bundle "$key"
}
run converge_brew_bundle
{{- end }}
