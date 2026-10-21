{{- if hasPrefix "mac-" .host -}}
# Passwordless sudo for exactly the two `pmset disablesleep` commands used by the
# lid-sleep toggles (SwiftBar lid-caffeine plugin, Raycast toggle-lid-sleep). Asks for the
# admin password only when the file is missing or differs.
converge_lid_sleep_sudoers() {
    local dest=/etc/sudoers.d/lid-caffeine tmp cmd
    local entry='{{ .chezmoi.username }} ALL=(root) NOPASSWD: /usr/bin/pmset -a disablesleep 1, /usr/bin/pmset -a disablesleep 0'
    # The installed file is root-only (0440), so a user cannot read it back: compare its
    # contents when readable, else its size.
    if [ -r "$dest" ]; then
        [ "$(cat "$dest")" = "$entry" ] && return 0
    elif [ "$(stat -f %z "$dest" 2>/dev/null)" = "$((${#entry} + 1))" ]; then
        return 0
    fi
    tmp=$(mktemp)
    printf '%s\n' "$entry" >"$tmp"
    /usr/sbin/visudo -cf "$tmp" >/dev/null || { rm -f "$tmp"; return 1; }
    cmd="/usr/bin/install -m 0440 -o root -g wheel '$tmp' '$dest'"
    step "lid-sleep: installing $dest (admin password required)"
    if [ -t 0 ]; then
        sudo /bin/sh -c "$cmd"
    else
        # No terminal (e.g. run from an agent): use the macOS GUI password prompt.
        /usr/bin/osascript -e "do shell script \"$cmd\" with administrator privileges"
    fi
    local rc=$?
    rm -f "$tmp"
    return $rc
}
run converge_lid_sleep_sudoers
{{- end }}
