{{- if hasPrefix "mac-" .host -}}
# Send `.lan` machine names (nuc.lan) to the homelab Pi-hole at its stable address,
# 172.16.255.1, whatever owns the default resolver. Tailscale's MagicDNS takes over as the
# primary resolver whenever it runs and knows nothing of `.lan`, which hid the WireGuard
# tunnel's DNS. The address is reachable at home (router static route) and over WireGuard;
# elsewhere `.lan` names have no answer anyway. Only `lan` is scoped: scoping the homelab
# domain would also stop wg.<domain> resolving when the tunnel is down.
converge_lan_resolver() {
    local dest=/etc/resolver/lan tmp cmd
    local entry='nameserver 172.16.255.1'
    [ "$(cat "$dest" 2>/dev/null)" = "$entry" ] && return 0
    tmp=$(mktemp)
    printf '%s\n' "$entry" >"$tmp"
    cmd="/bin/mkdir -p /etc/resolver && /usr/bin/install -m 0644 -o root -g wheel '$tmp' '$dest'"
    step "lan-resolver: installing $dest (admin password required)"
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
run converge_lan_resolver
{{- end }}
