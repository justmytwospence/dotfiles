{{- if hasPrefix "mac-" .host -}}
# Node on the Macs (.chezmoidata/node.json): nvm (from the Brewfile) has the latest
# installed release of node.major and its `default` alias points there, as the NUC's
# NodeSource major does. A missing major is installed; a default on another major is
# moved; nothing is upgraded within the major (that stays `nvm install <major>`).
# Global CLIs are pnpm's (macPnpm), installed into ~/.local/bin (globalBinDir), so they
# do not live inside one node version and survive the next major. Installed when missing.
converge_node() {
    local nvm_sh=
    for nvm_sh in "$HOME/.nvm/nvm.sh" /opt/homebrew/opt/nvm/nvm.sh; do [ -s "$nvm_sh" ] && break; nvm_sh=; done
    [ -n "$nvm_sh" ] || return 0
    export NVM_DIR="$HOME/.nvm"
    mkdir -p "$NVM_DIR"
    set +u
    . "$nvm_sh" >/dev/null 2>&1
    local rc=0 installed current
    installed=$(nvm version {{ .node.major }} 2>/dev/null)
    if [ "$installed" = "N/A" ] || [ -z "$installed" ]; then
        step "node {{ .node.major }} (nvm)"
        nvm install {{ .node.major }} >/dev/null || rc=1
    fi
    current=$(nvm version default 2>/dev/null)
    current=${current#v}
    if [ "$rc" = 0 ] && [ "${current%%.*}" != "{{ .node.major }}" ]; then
        step "nvm default: ${current:-none} -> {{ .node.major }}"
        nvm alias default {{ .node.major }} >/dev/null || rc=1
    fi
    nvm use --silent {{ .node.major }} >/dev/null 2>&1 || rc=1
    set -u
{{- range .node.macPnpm }}
    [ -e "$HOME/.local/bin/{{ .bin }}" ] || { step "pnpm {{ .pkg }}"; pnpm add -g {{ .pkg | quote }} || rc=1; }
{{- end }}
    return "$rc"
}
run converge_node
{{- end }}
