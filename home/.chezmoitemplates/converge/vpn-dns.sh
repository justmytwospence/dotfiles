{{- if hasPrefix "mac-" .host -}}
# DNS with WireGuard and Tailscale both up. Tailscale's DNS (accept-dns) makes MagicDNS the
# primary resolver, which forwards everything else to the Wi-Fi's DNS: .lan names stop
# resolving and *.<domain> gets the public IP, so LAN-only services 404 over the tunnel.
# So Tailscale's DNS stays off and the WireGuard tunnel's resolver (the homelab Pi-hole)
# is primary while it is up, the network's own when it is down. Scoped /etc/resolver files
# keep the rest: .lan to the Pi-hole at its stable address (reachable at home through the
# router's static route and over WireGuard), the tailnet's MagicDNS suffix to Tailscale.
resolver_file() {
    local dest=/etc/resolver/$1 entry="nameserver $2" tmp cmd rc
    [ "$(cat "$dest" 2>/dev/null)" = "$entry" ] && return 0
    tmp=$(mktemp)
    printf '%s\n' "$entry" >"$tmp"
    cmd="/bin/mkdir -p /etc/resolver && /usr/bin/install -m 0644 -o root -g wheel '$tmp' '$dest'"
    step "vpn-dns: installing $dest (admin password required)"
    if [ -t 0 ]; then
        sudo /bin/sh -c "$cmd"
    else
        # No terminal (e.g. run from an agent): use the macOS GUI password prompt.
        /usr/bin/osascript -e "do shell script \"$cmd\" with administrator privileges"
    fi
    rc=$?
    rm -f "$tmp"
    return $rc
}

converge_vpn_dns() {
    local ts suffix rc=0
    resolver_file lan 172.16.255.1 || rc=1
    ts=$(command -v tailscale) || return $rc
    # Not logged in or not running: nothing to set; `bin/converge vpn-dns` once it is.
    suffix=$("$ts" status --json 2>/dev/null | jq -r '.MagicDNSSuffix // empty' 2>/dev/null)
    [ -n "$suffix" ] || return $rc
    if "$ts" debug prefs 2>/dev/null | jq -e '.CorpDNS' >/dev/null; then
        step "vpn-dns: turning off Tailscale DNS (accept-dns)"
        "$ts" set --accept-dns=false || rc=1
    fi
    resolver_file "$suffix" 100.100.100.100 || rc=1
    return $rc
}
run converge_vpn_dns
{{- end }}
