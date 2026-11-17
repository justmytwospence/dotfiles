{{- if hasPrefix "mac-" .host -}}
# Phone access (docs/phone-access.md): Paseo's daemon. paseo-setup is idempotent and
# restarts the daemon only when something changed; the script reruns when it or Paseo changes.
# Pairing needs the phone, so it prints the remaining steps.
converge_paseo() {
    step "paseo-setup"
    "$HOME/.local/bin/paseo-setup" || return 1
}
run converge_paseo
{{- end }}
