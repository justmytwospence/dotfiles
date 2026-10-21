{{- if hasPrefix "mac-" .host -}}
# Phone access (docs/phone-access.md): Paseo's daemon. paseo-setup is idempotent and
# restarts the daemon only when something changed; it runs when it or Paseo changes.
# Pairing needs the phone, so it prints the remaining steps.
converge_paseo() {
    local key
    key="$(digest "$HOME/.local/bin/paseo-setup") $(ls /opt/homebrew/Caskroom/paseo 2>/dev/null | tr '\n' ' ')"
    stamped paseo "$key" && return 0
    step "paseo-setup"
    "$HOME/.local/bin/paseo-setup" || return 1
    stamp paseo "$key"
}
run converge_paseo
{{- end }}
