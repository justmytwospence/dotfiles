{{- if hasPrefix "mac-" .host -}}
# HerdrMenu (docs/plugins.md): build the pinned source (.chezmoiexternal.toml.tmpl) into
# ~/Applications/HerdrMenu.app when the pin changes or the app is missing, and restart a
# running copy.
converge_herdr_menu() {
    local src="$HOME/.local/share/herdr-menu" app="$HOME/Applications/HerdrMenu.app"
    local key={{ .herdrMenu.commit | quote }}
    if [ -d "$app" ]; then
        stamped herdr-menu "$key" && return 0
        # No stamp yet: the app is what the old onchange script built; adopt it.
        [ -f "$STATE/herdr-menu" ] || { stamp herdr-menu "$key"; return 0; }
    fi
    if ! xcrun --find swiftc >/dev/null 2>&1; then
        echo "herdr-menu: swiftc is missing; run xcode-select --install, then chezmoi apply again" >&2
        return 1
    fi
    step "herdr-menu: build"
    sh "$src/build.sh" || return 1
    if pkill -f "HerdrMenu.app/Contents/MacOS/HerdrMenu"; then
        sleep 1
        open "$app"
    fi
    stamp herdr-menu "$key"
}
run converge_herdr_menu
{{- end }}
