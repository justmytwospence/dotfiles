{{- if ne .host "nuc" -}}
# zsh as the login shell: Homebrew's on macOS, the distro's everywhere else. A host
# already on some zsh (macOS's /bin/zsh, say) is left as it is. Rust's default toolchain
# on the Mac.
converge_login_shell() {
    # Containers (an AgentBox box's task) run without $USER.
    local user=${USER:-$(id -un)} current zsh_path
{{- if hasPrefix "mac-" .host }}
    current=$(dscl . -read "/Users/$user" UserShell | awk '{print $2}')
{{- else }}
    current=$(getent passwd "$user" | cut -d: -f7)
{{- end }}
    if [[ $(basename "$current") != zsh ]]; then
        step "login shell: zsh"
        zsh_path=$(command -v zsh) || return 1
        grep -qxF "$zsh_path" /etc/shells || echo "$zsh_path" | sudo tee -a /etc/shells >/dev/null || return 1
        # chsh authenticates as the user, which a passwordless account (an AgentBox box)
        # cannot do; with a terminal attached it would wait forever. Use passwordless
        # sudo where there is one; otherwise ask as usual.
        if sudo -n true 2>/dev/null; then
            sudo chsh -s "$zsh_path" "$user" || return 1
        else
            chsh -s "$zsh_path" || return 1
        fi
    fi
{{- if hasPrefix "mac-" .host }}
    if have rustup && ! grep -qs '^default_toolchain' "$HOME/.rustup/settings.toml"; then
        step "rustup default stable"
        rustup default stable || return 1
    fi
{{- end }}
}
run converge_login_shell
{{- end }}
