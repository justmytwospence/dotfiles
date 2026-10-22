{{- if hasPrefix "mac-" .host -}}
# Omnigent host (docs/phone-access.md): keep this Mac's host service on the installed
# omnigent. `omni host enable` writes the interpreter's versioned Cellar path into the
# launchd plist, so `brew upgrade omnigent` leaves the service on a deleted keg: the
# running daemon fails its lazy imports and the next start fails outright. Re-running
# enable rewrites the plist and restarts the host, interrupting any session on it, so it
# runs only when the plist is stale or the service is not loaded. It never signs in: a Mac
# that has not registered (`omni login`, then `omni host enable`) has no plist and is
# left alone. Through `zsh -c`, which reads ~/.zshenv, so the PATH enable records for
# the agents is the same however apply was started.
converge_omnigent_host() {
    local plist="$HOME/Library/LaunchAgents/ai.omnigent.host.plist" omni want have
    [ -f "$plist" ] || return 0
    omni=$(command -v omni) || return 0
    want=$(sed -n '1s/^#!//p' "$omni")
    if [ ! -x "$want" ]; then
        echo "omnigent-host: cannot tell omni's interpreter from $omni" >&2
        return 1
    fi
    have=$(plutil -extract ProgramArguments.0 raw -o - "$plist" 2>/dev/null)
    if [ "$have" = "$want" ] && launchctl print "gui/$(id -u)/ai.omnigent.host" >/dev/null 2>&1; then
        return 0
    fi
    step "omnigent-host: re-enable the host service on $("$omni" --version)"
    zsh -c 'exec "$0" host enable --non-interactive' "$omni" </dev/null || return 1
    have=$(plutil -extract ProgramArguments.0 raw -o - "$plist" 2>/dev/null)
    if [ "$have" != "$want" ]; then
        echo "omnigent-host: the service still runs ${have:-nothing}, not $want" >&2
        return 1
    fi
}
run converge_omnigent_host
{{- end }}
