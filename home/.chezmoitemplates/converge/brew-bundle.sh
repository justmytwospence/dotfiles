{{- if hasPrefix "mac-" .host -}}
{{- $brewfile := includeTemplate "dot_Brewfile.tmpl" . }}
{{- $npm := list }}
{{- range regexFindAll "(?m)^\\s*npm '[^']+'" $brewfile -1 }}{{ $npm = append $npm (regexReplaceAll "^\\s*npm '([^']+)'" . "${1}") }}{{ end }}
{{- $uv := list }}
{{- range regexFindAll "(?m)^\\s*uv '[^']+'" $brewfile -1 }}{{ $uv = append $uv (regexReplaceAll "^\\s*uv '([^']+)'" . "${1}") }}{{ end }}
{{- $allow := includeTemplate "cooldown-allow.sh" (dict "allow" .cooldownAllow "npm" $npm "uv" $uv) | trim }}
# Homebrew: install what ~/.Brewfile lists and is missing (--no-upgrade: upgrades stay
# `brew upgrade`). `brew bundle check` takes seconds, so it runs when the Brewfile or the
# cooldown allowances change, and otherwise once a day to catch drift.
converge_brew_bundle() {
    eval "$(/opt/homebrew/bin/brew shellenv 2>/dev/null || /usr/local/bin/brew shellenv)"
{{- if $allow }}
    # Explicitly allowed fresh releases first (docs/cooldown.md), so brew bundle finds them
    # installed instead of failing on a package with no release past the cooldown yet.
    have npm || brew install node
    have uv || brew install uv
    {{ $allow | nindent 4 | trim }}
{{- end }}
    local key={{ list $brewfile $allow | toJson | sha256sum | quote }}
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
